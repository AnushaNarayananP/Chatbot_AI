from __future__ import annotations

import re

from pipeline.models import ClassificationResult, IntentType, PipelineRequest


TRANSLATE_PATTERN = re.compile(
    r"\btranslate\b(?:.*?\bto\b\s+(?P<language>[a-zA-Z\s-]+))?",
    flags=re.IGNORECASE,
)


def classify_request(request: PipelineRequest) -> ClassificationResult:
    prompt = (request.prompt or "").strip().lower()
    has_image = request.has_image

    if _looks_like_workflow_trigger(prompt):
        return ClassificationResult(
            intent=IntentType.WORKFLOW_TRIGGER,
            confidence=0.92,
            source_type="image" if has_image else "text",
            reason="Prompt asks to save, store, process, or persist results.",
        )

    target_language = _extract_target_language(prompt)
    if target_language:
        return ClassificationResult(
            intent=IntentType.TRANSLATION,
            confidence=0.95,
            source_type="image" if has_image else "text",
            target_language=target_language,
            reason="Prompt explicitly requests translation.",
        )

    if _looks_like_data_extraction(prompt):
        # With an image, do normal invoice extraction; otherwise prefer RAG if
        # documents have been uploaded so the user's PDF context is used.
        if not has_image and _has_rag_documents(request):
            return ClassificationResult(
                intent=IntentType.RAG_QA,
                confidence=0.92,
                source_type="documents",
                reason="Session has uploaded documents; routing data question to RAG.",
            )
        return ClassificationResult(
            intent=IntentType.DATA_EXTRACTION,
            confidence=0.9,
            source_type="image" if has_image else "text",
            reason="Prompt mentions invoice, receipt, fields, or structured extraction.",
        )

    if _looks_like_summarization(prompt):
        # If RAG documents exist, route summarization through RAG too
        if _has_rag_documents(request):
            return ClassificationResult(
                intent=IntentType.RAG_QA,
                confidence=0.92,
                source_type="documents",
                reason="Session has uploaded documents; routing summarization to RAG.",
            )
        return ClassificationResult(
            intent=IntentType.SUMMARIZATION,
            confidence=0.88,
            source_type="image" if has_image else "text",
            reason="Prompt requests a summary or condensed explanation.",
        )

    if has_image and _looks_like_ocr(prompt):
        return ClassificationResult(
            intent=IntentType.OCR,
            confidence=0.93,
            source_type="image",
            reason="Prompt asks to read or extract text from the image.",
        )

    if has_image and not prompt:
        return ClassificationResult(
            intent=IntentType.OCR,
            confidence=0.75,
            source_type="image",
            reason="Image-only request defaults to text extraction first.",
        )

    if has_image:
        return ClassificationResult(
            intent=IntentType.QA,
            confidence=0.7,
            source_type="image",
            reason="Image request without explicit extraction defaults to image question answering.",
        )

    # RAG — if the session has uploaded documents, route to RAG QA
    if _has_rag_documents(request):
        return ClassificationResult(
            intent=IntentType.RAG_QA,
            confidence=0.9,
            source_type="documents",
            reason="Session has uploaded documents; routing to RAG question answering.",
        )

    return ClassificationResult(
        intent=IntentType.QA,
        confidence=0.8,
        source_type="text",
        reason="Default text interaction is question answering.",
    )


def _has_rag_documents(request: PipelineRequest) -> bool:
    """Check whether the current session has any ingested RAG documents.

    The *rag_session_id* attribute is only set on the request when the UI
    has confirmed that documents exist in session state, so its presence
    is a reliable signal without needing to re-query ChromaDB (which can
    fail due to concurrent access or Rust-binding issues).
    """
    session_id = getattr(request, "rag_session_id", None)
    return bool(session_id)


def _extract_target_language(prompt: str) -> str | None:
    match = TRANSLATE_PATTERN.search(prompt)
    if not match:
        return None

    target_language = (match.group("language") or "").strip(" .!?")
    return target_language or "english"


def _looks_like_ocr(prompt: str) -> bool:
    keywords = (
        "extract text",
        "read this",
        "ocr",
        "what is written",
        "text from image",
        "scan this",
    )
    return any(keyword in prompt for keyword in keywords)


def _looks_like_summarization(prompt: str) -> bool:
    keywords = ("summarize", "summary", "short version", "condense", "tl;dr")
    return any(keyword in prompt for keyword in keywords)


def _looks_like_data_extraction(prompt: str) -> bool:
    keywords = (
        "extract data",
        "structured data",
        "invoice",
        "receipt",
        "bill",
        "amount",
        "vendor",
        "date",
        "line items",
        "fields",
    )
    return any(keyword in prompt for keyword in keywords)


def _looks_like_workflow_trigger(prompt: str) -> bool:
    keywords = ("store", "save", "persist", "process and store", "archive")
    return any(keyword in prompt for keyword in keywords)
