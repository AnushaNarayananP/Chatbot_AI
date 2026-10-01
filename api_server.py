"""FastAPI backend for FriendlyBot (Avi).

Thin REST wrapper around the existing Python modules so the React
frontend can communicate with the chatbot engine, invoice pipeline,
RAG document store, and audio transcription.

Run with:
    uvicorn api_server:app --reload --port 8000
"""

from __future__ import annotations

import base64
import io
import json
import os
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env before any other project imports that read env vars.
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from audio_handler import is_audio_file, transcribe_audio
from chatbot import BOT_NAME, SYSTEM_PROMPT, get_default_text_model, route_chat_request
from rag_engine import (
    clear_session_documents,
    delete_document,
    has_documents,
    ingest_document,
    is_rag_enabled,
    list_session_documents,
)
from tools.storage_tools import (
    build_invoice_table_rows,
    build_purchase_table_rows,
    initialize_invoice_database,
    load_invoice_database,
)

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="FriendlyBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        os.environ.get("RENDER_EXTERNAL_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAG_SESSION_ID = "rag_default_session"

INVOICE_TABLE_COLUMNS = [
    "invoice_id", "vendor", "invoice_number", "date",
    "currency", "subtotal", "tax", "total_amount",
]
PURCHASE_TABLE_COLUMNS = [
    "invoice_id", "sr_no", "name", "quantity", "rate", "total",
]

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup():
    initialize_invoice_database(reset=False)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    """Return current model info, RAG status, and feature flags."""
    return {
        "bot_name": BOT_NAME,
        "default_model": get_default_text_model(),
        "rag_enabled": is_rag_enabled(),
        "rag_active": has_documents(RAG_SESSION_ID),
        "system_prompt": SYSTEM_PROMPT,
    }


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def chat(
    prompt: str = Form(""),
    model: str = Form(""),
    messages: str = Form("[]"),
    image: UploadFile | None = File(None),
    image_url: str = Form(""),
):
    """Send a message → get a bot response.

    ``messages`` is a JSON-serialised list of prior conversation turns.
    ``image`` is an optional uploaded image file.
    """
    try:
        parsed_messages = json.loads(messages)
    except (json.JSONDecodeError, TypeError):
        parsed_messages = []

    # Ensure system prompt is present
    if not any(m.get("role") == "system" for m in parsed_messages):
        parsed_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    # Determine RAG session
    rag_session_id = None
    if is_rag_enabled() and has_documents(RAG_SESSION_ID):
        rag_session_id = RAG_SESSION_ID

    # Read uploaded image if provided
    uploaded_image = None
    if image and image.filename:
        uploaded_image = io.BytesIO(await image.read())
        uploaded_image.name = image.filename

    selected_model = model.strip() if model else get_default_text_model()

    try:
        result = route_chat_request(
            user_prompt=prompt,
            uploaded_image=uploaded_image,
            image_url=image_url.strip() if image_url else None,
            messages=parsed_messages,
            model=selected_model,
            rag_session_id=rag_session_id,
        )
        return JSONResponse(content=result)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "reply": f"Backend error: {exc}",
                "meta": {},
            },
        )


# ---------------------------------------------------------------------------
# Audio Transcription + Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat/audio")
async def chat_audio(
    audio: UploadFile = File(...),
    prompt: str = Form(""),
    model: str = Form(""),
    messages: str = Form("[]"),
):
    """Upload audio → transcribe → route through chat pipeline."""
    try:
        parsed_messages = json.loads(messages)
    except (json.JSONDecodeError, TypeError):
        parsed_messages = []

    if not any(m.get("role") == "system" for m in parsed_messages):
        parsed_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    # Transcribe audio
    audio_bytes = await audio.read()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = audio.filename or "recording.wav"

    try:
        transcript = transcribe_audio(audio_file)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "reply": f"Audio transcription failed: {exc}",
                "meta": {},
                "transcript": "",
            },
        )

    # Combine typed text with transcript
    combined_prompt = prompt.strip()
    if combined_prompt and transcript:
        combined_prompt = f"{combined_prompt}\n\n{transcript}"
    elif transcript:
        combined_prompt = transcript

    rag_session_id = None
    if is_rag_enabled() and has_documents(RAG_SESSION_ID):
        rag_session_id = RAG_SESSION_ID

    selected_model = model.strip() if model else get_default_text_model()

    try:
        result = route_chat_request(
            user_prompt=combined_prompt,
            messages=parsed_messages,
            model=selected_model,
            rag_session_id=rag_session_id,
        )
        result["transcript"] = transcript
        return JSONResponse(content=result)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "reply": f"Backend error: {exc}",
                "meta": {},
                "transcript": transcript,
            },
        )


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@app.get("/api/invoices")
def get_invoices():
    """Return all stored invoices and purchase line items."""
    database = load_invoice_database()

    invoice_rows = build_invoice_table_rows(database)
    invoices = [
        {col: row.get(col, "") for col in INVOICE_TABLE_COLUMNS}
        for row in invoice_rows
    ]

    purchase_rows = build_purchase_table_rows(database)
    purchases = [
        {col: row.get(col, "") for col in PURCHASE_TABLE_COLUMNS}
        for row in purchase_rows
    ]

    # Also return raw database for richer invoice data (items, etc.)
    raw_invoices = database.get("invoices", [])

    return {
        "invoices": invoices,
        "purchases": purchases,
        "raw_invoices": raw_invoices,
    }


@app.post("/api/invoices/reset")
def reset_invoices():
    """Reset the invoice database."""
    initialize_invoice_database(reset=True)
    return {"ok": True, "message": "Invoice database reset."}


# ---------------------------------------------------------------------------
# RAG Documents
# ---------------------------------------------------------------------------

@app.get("/api/rag/documents")
def get_rag_documents():
    """List ingested RAG documents."""
    if not is_rag_enabled():
        return {"documents": [], "enabled": False}

    try:
        docs = list_session_documents(RAG_SESSION_ID)
    except Exception:
        docs = []

    return {"documents": docs, "enabled": True}


@app.post("/api/rag/upload")
async def upload_rag_document(file: UploadFile = File(...)):
    """Upload & ingest a document into the RAG vector store."""
    if not is_rag_enabled():
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "RAG is disabled."},
        )

    if not file.filename:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "No file provided."},
        )

    max_size = 20 * 1024 * 1024  # 20 MB
    contents = await file.read()
    if len(contents) > max_size:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": f"{file.filename} exceeds 20 MB limit."},
        )

    file_data = io.BytesIO(contents)
    file_data.name = file.filename

    try:
        result = ingest_document(file_data, file.filename, RAG_SESSION_ID)
        return {"ok": True, **result}
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": f"Failed to ingest: {exc}"},
        )


@app.delete("/api/rag/documents/{doc_id}")
def delete_rag_document(doc_id: str):
    """Delete a RAG document by its ID."""
    deleted = delete_document(RAG_SESSION_ID, doc_id)
    return {"ok": deleted, "doc_id": doc_id}


@app.post("/api/rag/clear")
def clear_rag_documents():
    """Clear all RAG documents."""
    cleared = clear_session_documents(RAG_SESSION_ID)
    return {"ok": cleared}


# ---------------------------------------------------------------------------
# Serve React Frontend (production)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        file_path = FRONTEND_DIR / full_path
        if full_path and file_path.is_file():
            from fastapi.responses import FileResponse

            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
