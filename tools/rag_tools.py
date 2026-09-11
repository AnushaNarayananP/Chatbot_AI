"""RAG tools — Answer questions using retrieved document context."""

from __future__ import annotations

import json
import re


def rag_answer_question(
    question: str,
    session_id: str,
    top_k: int | None = None,
) -> dict[str, object]:
    """Retrieve relevant chunks and answer *question* with document citations.

    Returns a dict with keys ``answer``, ``sources``, and ``chunks_used``.
    """
    from rag_engine import build_rag_context, query_documents

    chunks = query_documents(question, session_id, top_k=top_k)
    if not chunks:
        return {
            "answer": (
                "I couldn't find any relevant information in your uploaded documents "
                "to answer that question. Could you try rephrasing, or make sure the "
                "relevant document has been uploaded?"
            ),
            "sources": [],
            "chunks_used": 0,
        }

    rag_context = build_rag_context(chunks)
    sources = list({chunk["filename"] for chunk in chunks})

    from chatbot import chat_with_text_provider

    source_names = ", ".join(f'"{s}"' for s in sources) if sources else "the uploaded document"

    prompt = (
        "You are a helpful assistant that answers questions based on the user's uploaded documents.\n\n"
        "IMPORTANT RULES:\n"
        "- The document excerpts below come from the user's uploaded files. When the user says "
        "'this pdf', 'this document', 'this file', or 'this test', they are referring to THESE uploaded documents.\n"
        "- When the user asks for 'titles', 'sub titles', 'subtitles', 'headings', or 'sections', "
        "they mean the section headings, numbered items, or topic titles WITHIN the document — NOT video subtitles.\n"
        "- Use ONLY the provided document excerpts to answer. If the answer isn't in the excerpts, "
        "say so honestly — do not make up information.\n"
        "- When referencing information, cite the source document name in brackets like [Source: filename.pdf].\n"
        "- Keep your answer clear, direct, and well-structured.\n\n"
        f"The user has uploaded: {source_names}\n\n"
        f"{rag_context}\n"
        f"Question: {question}\n"
    )

    # Retry with backoff for transient API errors (503 / UNAVAILABLE).
    import time

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            response = chat_with_text_provider([{"role": "user", "content": prompt}])
            answer = _clean_response(response)
            return {
                "answer": answer,
                "sources": sources,
                "chunks_used": len(chunks),
            }
        except RuntimeError as exc:
            last_error = exc
            err_text = str(exc)
            is_transient = any(s in err_text for s in ("503", "UNAVAILABLE", "high demand", "overloaded"))
            if not is_transient or attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # 1s, 2s backoff

    raise last_error  # unreachable, but keeps type-checkers happy


def _clean_response(response: str) -> str:
    """Strip markdown code fences if the LLM wraps the answer."""
    cleaned = (response or "").strip()
    # Remove ```json ... ``` wrappers that some models add.
    fence_match = re.fullmatch(
        r"```(?:json)?\s*(?P<body>.*?)\s*```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fence_match:
        inner = fence_match.group("body").strip()
        try:
            parsed = json.loads(inner)
            return str(parsed.get("answer", inner)).strip()
        except (json.JSONDecodeError, AttributeError):
            return inner
    return cleaned
