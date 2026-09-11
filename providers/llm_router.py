from __future__ import annotations

import json
import re
from typing import Any


def generate_json(messages: list[dict[str, str]], model: str | None = None) -> dict[str, Any]:
    """Request a structured JSON response from the configured text provider."""
    from chatbot import chat_with_text_provider

    response = chat_with_text_provider(messages, model=model)
    return parse_json_response(response)


def parse_json_response(response: str | dict[str, Any]) -> dict[str, Any]:
    """Parse direct, fenced, or embedded JSON object responses."""
    if isinstance(response, dict):
        return response

    text = str(response or "").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        fenced_match = re.search(
            r"```(?:json)?\s*(?P<body>\{.*?\})\s*```",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced_match:
            return json.loads(fenced_match.group("body"))
        embedded_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if embedded_match:
            return json.loads(embedded_match.group(0))
        raise ValueError("LLM response did not contain a JSON object.")

    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON response must be an object.")
    return parsed
