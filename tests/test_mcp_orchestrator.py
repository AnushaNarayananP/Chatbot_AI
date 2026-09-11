from __future__ import annotations

from mcp.orchestrator import MCPOrchestrator
from mcp.registry import ToolMetadata
from mcp.selector import ToolSelection
from pipeline.models import PipelineRequest


def test_orchestrator_executes_llm_selected_local_tool(monkeypatch):
    monkeypatch.setattr(
        "pipeline.registry.get_tool",
        lambda name: lambda **kwargs: {
            "answer": f"Answered {kwargs['question']}",
            "confidence_note": "selected by mcp",
        },
    )

    orchestrator = MCPOrchestrator(
        tools=[
            ToolMetadata(
                tool_name="answer_question",
                description="Answer a question",
                input_schema={"type": "object", "required": ["question"]},
            )
        ],
        selector=lambda request, tools: ToolSelection(
            intent="qa",
            tool_selected="answer_question",
            confidence=0.91,
            parameters={"question": request.prompt},
            selection_reason="Best available QA tool",
        ),
    )

    response = orchestrator.handle(PipelineRequest(prompt="What is MCP?"))

    assert response.ok is True
    assert response.intent == "qa"
    assert response.reply == "Answered What is MCP?"
    assert response.tool_calls[0].name == "answer_question"
    assert response.tool_calls[0].arguments == {"question": "What is MCP?"}
    assert response.meta["mcp_orchestrated"] is True
    assert response.meta["selection_reason"] == "Best available QA tool"


def test_orchestrator_returns_clarification_when_selector_reports_missing_parameters():
    orchestrator = MCPOrchestrator(
        tools=[
            ToolMetadata(
                tool_name="translate_text",
                description="Translate text",
                input_schema={"type": "object", "required": ["text", "target_language"]},
            )
        ],
        selector=lambda request, tools: ToolSelection(
            intent="translate",
            tool_selected="translate_text",
            confidence=0.8,
            parameters={},
            selection_reason="Translation request",
            missing_parameters=["text", "target_language"],
        ),
    )

    response = orchestrator.handle(PipelineRequest(prompt="Translate this"))

    assert response.ok is False
    assert response.intent == "translate"
    assert response.reply == "I need these details before I can continue: text, target_language."
    assert response.meta["error_category"] == "missing_parameters"
