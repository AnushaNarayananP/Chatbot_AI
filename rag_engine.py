"""RAG Engine — Document ingestion, embedding, storage, and retrieval.

Supports PDF, TXT, DOCX, and Markdown files.  Uses the Gemini Embedding
API (``text-embedding-004``) for vector generation and ChromaDB for
local, file-based vector storage.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 100
_DEFAULT_TOP_K = 5
_EMBEDDING_MODEL = "gemini-embedding-001"
_CHROMA_PERSIST_DIR = Path(__file__).resolve().parent / "rag_chroma"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def get_chunk_size() -> int:
    return max(_env_int("RAG_CHUNK_SIZE", _DEFAULT_CHUNK_SIZE), 100)


def get_chunk_overlap() -> int:
    return max(_env_int("RAG_CHUNK_OVERLAP", _DEFAULT_CHUNK_OVERLAP), 0)


def get_top_k() -> int:
    return max(_env_int("RAG_TOP_K", _DEFAULT_TOP_K), 1)


def is_rag_enabled() -> bool:
    return os.environ.get("ENABLE_RAG", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------

def parse_document(file_data: Any, filename: str) -> str:
    """Extract plain text from an uploaded file.

    *file_data* is expected to be a Streamlit ``UploadedFile`` (which
    behaves like a ``BytesIO``).  *filename* is used to determine the
    parser by extension.
    """
    extension = Path(filename).suffix.lower()
    raw_bytes: bytes = (
        file_data.read()
        if hasattr(file_data, "read")
        else file_data
    )
    # Reset position for Streamlit UploadedFile objects so they can be
    # re-read later if needed.
    if hasattr(file_data, "seek"):
        file_data.seek(0)

    if extension == ".pdf":
        return _parse_pdf(raw_bytes)
    if extension in {".txt", ".md", ".markdown"}:
        return raw_bytes.decode("utf-8", errors="replace")
    if extension in {".docx",}:
        return _parse_docx(raw_bytes)

    raise ValueError(f"Unsupported document type: {extension}")


def _parse_pdf(raw_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw_bytes))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def _parse_docx(raw_bytes: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(raw_bytes))
    paragraphs: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split *text* into overlapping chunks of roughly *chunk_size* tokens.

    Uses a simple whitespace tokeniser.  Each chunk overlaps with the
    previous by *chunk_overlap* tokens to preserve context across
    boundaries.
    """
    if chunk_size is None:
        chunk_size = get_chunk_size()
    if chunk_overlap is None:
        chunk_overlap = get_chunk_overlap()

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        if end >= len(words):
            break
        start = end - chunk_overlap

    return chunks


# ---------------------------------------------------------------------------
# Gemini Embedding API
# ---------------------------------------------------------------------------

def _get_embedding_url() -> str:
    from gemini_client import get_env_value

    api_key = get_env_value("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY — required for RAG embeddings.")
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_EMBEDDING_MODEL}:embedContent?key={api_key}"
    )


def generate_embedding(text: str) -> list[float]:
    """Return a dense vector embedding for *text* via the Gemini API."""
    import json
    import urllib.request

    url = _get_embedding_url()
    payload = {
        "model": f"models/{_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["embedding"]["values"]


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Return embeddings for a batch of texts via the Gemini batchEmbedContents API."""
    import json
    import urllib.request

    from gemini_client import get_env_value

    api_key = get_env_value("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY — required for RAG embeddings.")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_EMBEDDING_MODEL}:batchEmbedContents?key={api_key}"
    )
    requests_payload = [
        {
            "model": f"models/{_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": t}]},
        }
        for t in texts
    ]
    payload = {"requests": requests_payload}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    return [item["values"] for item in body["embeddings"]]


# ---------------------------------------------------------------------------
# ChromaDB vector store
# ---------------------------------------------------------------------------

def _get_chroma_client():
    import chromadb
    import shutil
    import logging

    _CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return chromadb.PersistentClient(path=str(_CHROMA_PERSIST_DIR))
    except Exception as exc:
        # ChromaDB Rust bindings can panic if persisted data is corrupt or
        # was written by an incompatible version.  Wipe and retry once.
        logging.warning(
            "ChromaDB failed to load persisted data (%s). "
            "Removing corrupt store at %s and retrying.",
            exc,
            _CHROMA_PERSIST_DIR,
        )
        shutil.rmtree(_CHROMA_PERSIST_DIR, ignore_errors=True)
        _CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(_CHROMA_PERSIST_DIR))


def _collection_name(session_id: str) -> str:
    """Sanitise session ID into a valid ChromaDB collection name."""
    sanitised = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
    if not sanitised or not sanitised[0].isalpha():
        sanitised = "s_" + sanitised
    return sanitised[:63]


def _get_or_create_collection(session_id: str):
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=_collection_name(session_id),
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_document(
    file_data: Any,
    filename: str,
    session_id: str,
) -> dict[str, Any]:
    """Parse, chunk, embed, and store a document.

    Returns a summary dict with document name, number of chunks, and
    document ID.
    """
    text = parse_document(file_data, filename)
    if not text.strip():
        raise ValueError(f"Document '{filename}' contains no extractable text.")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"Document '{filename}' produced no text chunks.")

    doc_id = hashlib.sha256(f"{session_id}:{filename}".encode()).hexdigest()[:16]
    collection = _get_or_create_collection(session_id)

    # Remove previous version of the same document if re-uploaded.
    existing = collection.get(where={"doc_id": doc_id})
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])

    # Batch embed all chunks.
    _BATCH_SIZE = 100
    all_embeddings: list[list[float]] = []
    for batch_start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[batch_start:batch_start + _BATCH_SIZE]
        all_embeddings.extend(generate_embeddings_batch(batch))

    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"doc_id": doc_id, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.add(
        ids=ids,
        embeddings=all_embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    return {
        "doc_id": doc_id,
        "filename": filename,
        "num_chunks": len(chunks),
        "status": "ingested",
    }


def query_documents(
    query: str,
    session_id: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve the most relevant chunks for *query*.

    Returns a list of dicts with keys: ``text``, ``filename``,
    ``chunk_index``, ``score``.
    """
    if top_k is None:
        top_k = get_top_k()

    collection = _get_or_create_collection(session_id)
    if collection.count() == 0:
        return []

    query_embedding = generate_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
    )

    hits: list[dict[str, Any]] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for text, metadata, distance in zip(documents, metadatas, distances):
        hits.append({
            "text": text,
            "filename": metadata.get("filename", "unknown"),
            "chunk_index": metadata.get("chunk_index", -1),
            "score": round(1.0 - distance, 4),  # cosine similarity
        })
    return hits


def build_rag_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a context block for the LLM prompt."""
    if not chunks:
        return ""

    parts: list[str] = [
        "The following excerpts were retrieved from the user's uploaded documents. "
        "Use them to answer the question. Cite the source document name when referencing information.\n"
    ]
    for i, chunk in enumerate(chunks, 1):
        filename = chunk.get("filename", "unknown")
        chunk_index = chunk.get("chunk_index", "?")
        score = chunk.get("score", 0)
        parts.append(
            f"--- [Source {i}: {filename} (chunk {chunk_index}, relevance {score})] ---\n"
            f"{chunk['text']}\n"
        )
    return "\n".join(parts)


def list_session_documents(session_id: str) -> list[dict[str, Any]]:
    """Return a list of documents currently stored for the session."""
    collection = _get_or_create_collection(session_id)
    if collection.count() == 0:
        return []

    all_data = collection.get(include=["metadatas"])
    seen: dict[str, dict] = {}
    for metadata in all_data.get("metadatas", []):
        doc_id = metadata.get("doc_id", "")
        if doc_id not in seen:
            seen[doc_id] = {
                "doc_id": doc_id,
                "filename": metadata.get("filename", "unknown"),
                "chunk_count": 0,
            }
        seen[doc_id]["chunk_count"] += 1
    # Add num_chunks alias for UI compatibility.
    for doc in seen.values():
        doc["num_chunks"] = doc["chunk_count"]
    return list(seen.values())


def delete_document(session_id: str, doc_id: str) -> bool:
    """Remove a specific document from the session store."""
    collection = _get_or_create_collection(session_id)
    existing = collection.get(where={"doc_id": doc_id})
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])
        return True
    return False


def clear_session_documents(session_id: str) -> bool:
    """Remove all documents for a session."""
    try:
        client = _get_chroma_client()
        col_name = _collection_name(session_id)
        client.delete_collection(col_name)
        return True
    except Exception:
        return False


def has_documents(session_id: str) -> bool:
    """Return True if the session has any ingested documents."""
    try:
        collection = _get_or_create_collection(session_id)
        return collection.count() > 0
    except Exception:
        return False
