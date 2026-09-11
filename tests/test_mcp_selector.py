from __future__ import annotations

import pytest

from mcp.registry import ToolMetadata
from mcp.selector import ToolSelectionError, ToolSelector


def test_selector_uses_llm_json_to_choose_tool_and_extract_parameters():
    captured = {}

    def fake_generate_json(messages):
        captured["prompt"] = messages[-1]["content"]
        return {
            "intent": "create_invoice",
            "tool_selected": "store_data",
            "confidence": 0.95,
            "parameters": {
                "data": {
                    "vendor": "ABC Traders",
                    "summary": {"total_amount": 25000},
                }
            },
            "selection_reason": "The user asked to create an invoice record.",
        }

    selector = ToolSelector(generate_json=fake_generate_json)

    selection = selector.select(
        user_input="Create invoice for Rs 25000 for ABC Traders",
        tools=[
            ToolMetadata(
                tool_name="store_data",
                description="Store invoice data",
                input_schema={"type": "object", "required": ["data"]},
            )
        ],
    )

    assert selection.intent == "create_invoice"
    assert selection.tool_selected == "store_data"
    assert selection.confidence == 0.95
    assert selection.parameters["data"]["vendor"] == "ABC Traders"
    assert "store_data" in captured["prompt"]
    assert "Return JSON only" in captured["prompt"]


def test_selector_rejects_unknown_or_inactive_tools():
    selector = ToolSelector(
        generate_json=lambda messages: {
            "intent": "invoice",
            "tool_selected": "missing_tool",
            "confidence": 0.9,
            "parameters": {},
            "selection_reason": "Bad selection",
        }
    )

    with pytest.raises(ToolSelectionError, match="not available"):
        selector.select(
            user_input="Store this invoice",
            tools=[
                ToolMetadata(
                    tool_name="store_data",
                    description="Store invoice data",
                    availability="active",
                )
            ],
        )


def test_selector_reports_missing_required_parameters():
    selector = ToolSelector(
        generate_json=lambda messages: {
            "intent": "translate",
            "tool_selected": "translate_text",
            "confidence": 0.92,
            "parameters": {"target_language": "hindi"},
            "selection_reason": "Translation request",
        }
    )

    with pytest.raises(ToolSelectionError, match="missing required parameters"):
        selector.select(
            user_input="Translate hello to Hindi",
            tools=[
                ToolMetadata(
                    tool_name="translate_text",
                    description="Translate text",
                    input_schema={
                        "type": "object",
                        "required": ["text", "target_language"],
                    },
                )
            ],
        )
