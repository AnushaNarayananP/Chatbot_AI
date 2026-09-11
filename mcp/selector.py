from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Callable

from mcp.registry import ToolMetadata


GenerateJson = Callable[[list[dict[str, str]]], dict[str, Any] | str]


class ToolSelectionError(RuntimeError):
    """Raised when an LLM tool selection is invalid or incomplete."""


@dataclass
class ToolSelection:
    """Structured LLM decision for a tool call."""

    intent: str
    tool_selected: str
    confidence: float
    parameters: dict[str, Any] = field(default_factory=dict)
    selection_reason: str = ""
    missing_parameters: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolSelection":
        if not isinstance(data, dict):
            raise ToolSelectionError("Tool selection must be a JSON object.")
        return cls(
            intent=str(data.get("intent") or "").strip(),
            tool_selected=str(data.get("tool_selected") or data.get("tool") or "").strip(),
            confidence=_clamp_confidence(data.get("confidence")),
            parameters=data.get("parameters") if isinstance(data.get("parameters"), dict) else {},
            selection_reason=str(data.get("selection_reason") or data.get("reason") or "").strip(),
            missing_parameters=_string_list(data.get("missing_parameters")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolSelector:
    """LLM-backed selector that chooses among discovered tool metadata."""

    def __init__(self, generate_json: GenerateJson | None = None) -> None:
        self._generate_json = generate_json

    def select(
        self,
        user_input: str,
        tools: list[ToolMetadata],
        context: dict[str, Any] | None = None,
    ) -> ToolSelection:
        active_tools = [tool for tool in tools if tool.availability == "active"]
        if not active_tools:
            raise ToolSelectionError("No active tools are available.")

        response = self._call_llm(user_input, active_tools, context or {})
        selection = ToolSelection.from_dict(response)
        self._validate_selection(selection, active_tools)
        return selection

    def _call_llm(
        self,
        user_input: str,
        tools: list[ToolMetadata],
        context: dict[str, Any],
    ) -> dict[str, Any] | str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an autonomous MCP tool selector. Choose exactly one active tool "
                    "based only on the user's intent and the tool metadata."
                ),
            },
            {
                "role": "user",
                "content": _build_selection_prompt(user_input, tools, context),
            },
        ]
        if self._generate_json is not None:
            return self._generate_json(messages)

        from providers.llm_router import generate_json

        return generate_json(messages)

    def _validate_selection(
        self,
        selection: ToolSelection,
        active_tools: list[ToolMetadata],
    ) -> None:
        tools_by_name = {tool.tool_name: tool for tool in active_tools}
        if selection.tool_selected not in tools_by_name:
            raise ToolSelectionError(f"Selected tool '{selection.tool_selected}' is not available.")
        if selection.missing_parameters:
            return

        required = tools_by_name[selection.tool_selected].input_schema.get("required", [])
        missing = [
            parameter
            for parameter in required
            if parameter not in selection.parameters or selection.parameters.get(parameter) in (None, "")
        ]
        if missing:
            raise ToolSelectionError(
                "Selected tool is missing required parameters: " + ", ".join(missing)
            )


def _build_selection_prompt(
    user_input: str,
    tools: list[ToolMetadata],
    context: dict[str, Any],
) -> str:
    tool_payload = [tool.to_dict() for tool in tools]
    context_payload = {
        key: value
        for key, value in context.items()
        if key in {"has_image", "detected_language", "mode", "recent_summary", "has_rag_documents"}
    }
    return (
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "intent": "",\n'
        '  "tool_selected": "",\n'
        '  "confidence": 0.0,\n'
        '  "parameters": {},\n'
        '  "selection_reason": "",\n'
        '  "missing_parameters": []\n'
        "}\n\n"
        "Rules:\n"
        "- Select only one active tool from the provided metadata.\n"
        "- Extract parameters that match the selected tool input_schema.\n"
        "- If required parameters are missing, set missing_parameters instead of inventing values.\n"
        "- Use confidence from 0 to 1.\n\n"
        f"User input:\n{user_input}\n\n"
        f"Context:\n{json.dumps(context_payload, ensure_ascii=True)}\n\n"
        f"Tools:\n{json.dumps(tool_payload, ensure_ascii=True)}"
    )


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, confidence)), 4)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
