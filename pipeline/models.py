from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class IntentType(str, Enum):
    QA = "qa"
    RAG_QA = "rag_qa"
    OCR = "ocr"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    DATA_EXTRACTION = "data_extraction"
    WORKFLOW_TRIGGER = "workflow_trigger"


@dataclass
class PipelineRequest:
    prompt: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    uploaded_image: Any | None = None
    image_url: str | None = None
    model: str | None = None
    detected_language: str | None = None
    rag_session_id: str | None = None

    @property
    def has_image(self) -> bool:
        return self.uploaded_image is not None or bool((self.image_url or "").strip())


@dataclass
class ClassificationResult:
    intent: IntentType
    confidence: float
    source_type: str
    target_language: str | None = None
    reason: str = ""


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    status: str = "pending"
    output: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineResponse:
    ok: bool
    intent: str
    mode: str
    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    structured_data: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "intent": self.intent,
            "mode": self.mode,
            "reply": self.reply,
            "tool_calls": [tool_call.to_dict() for tool_call in self.tool_calls],
            "structured_data": self.structured_data,
            "meta": self.meta,
        }
