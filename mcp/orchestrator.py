from __future__ import annotations

from typing import Any, Callable

from mcp.discovery import MCPDiscovery
from mcp.registry import ToolMetadata
from mcp.selector import ToolSelection, ToolSelectionError, ToolSelector
from pipeline.models import PipelineRequest, PipelineResponse, ToolCall


SelectorCallable = Callable[[PipelineRequest, list[ToolMetadata]], ToolSelection]


class MCPOrchestrator:
    """Coordinates LLM selection and single-tool execution for Phase 4."""

    def __init__(
        self,
        tools: list[ToolMetadata] | None = None,
        selector: ToolSelector | SelectorCallable | None = None,
        discovery: MCPDiscovery | None = None,
    ) -> None:
        self.discovery = discovery
        self.tools = tools
        self.selector = selector or ToolSelector()

    def handle(self, request: PipelineRequest) -> PipelineResponse:
        tools = self._available_tools()
        try:
            selection = self._select_tool(request, tools)
        except ToolSelectionError as error:
            return _selection_error_response(request, error)

        if selection.missing_parameters:
            return _missing_parameters_response(request, selection)

        tool_call = ToolCall(
            name=selection.tool_selected,
            arguments=selection.parameters,
        )
        try:
            output = _execute_local_tool(selection.tool_selected, selection.parameters)
            tool_call.status = "completed"
            tool_call.output = output
        except Exception as error:
            tool_call.status = "failed"
            tool_call.error = str(error)
            return PipelineResponse(
                ok=False,
                intent=selection.intent,
                mode="vision" if request.has_image else "text",
                reply=str(error),
                tool_calls=[tool_call],
                structured_data={selection.tool_selected: {}},
                meta={
                    "mcp_orchestrated": True,
                    "tool_selected": selection.tool_selected,
                    "selection_reason": selection.selection_reason,
                    "confidence": selection.confidence,
                    "error_category": "tool_failure",
                },
            )

        return PipelineResponse(
            ok=True,
            intent=selection.intent,
            mode="vision" if request.has_image else "text",
            reply=_reply_from_output(output),
            tool_calls=[tool_call],
            structured_data={selection.tool_selected: output},
            meta={
                "mcp_orchestrated": True,
                "tool_selected": selection.tool_selected,
                "selection_reason": selection.selection_reason,
                "confidence": selection.confidence,
            },
        )

    def _available_tools(self) -> list[ToolMetadata]:
        if self.tools is not None:
            return self.tools
        discovery = self.discovery or MCPDiscovery()
        return discovery.discover_tools(refresh=False).tools

    def _select_tool(
        self,
        request: PipelineRequest,
        tools: list[ToolMetadata],
    ) -> ToolSelection:
        if isinstance(self.selector, ToolSelector):
            context = {
                "has_image": request.has_image,
                "detected_language": request.detected_language,
                "mode": "vision" if request.has_image else "text",
            }
            if request.rag_session_id:
                context["has_rag_documents"] = True
                context["rag_session_id"] = request.rag_session_id
            selection = self.selector.select(
                user_input=request.prompt,
                tools=tools,
                context=context,
            )
            # Inject session_id for RAG tool calls so the tool can query
            # the correct ChromaDB collection.
            if (
                selection.tool_selected == "rag_answer_question"
                and request.rag_session_id
            ):
                selection.parameters.setdefault("question", request.prompt)
                selection.parameters["session_id"] = request.rag_session_id
            return selection
        return self.selector(request, tools)


def _execute_local_tool(tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    from pipeline.registry import get_tool

    tool = get_tool(tool_name)
    output = tool(**parameters)
    return output if isinstance(output, dict) else {"result": output}


def _reply_from_output(output: dict[str, Any]) -> str:
    for key in ("answer", "translated_text", "summary", "message", "extracted_text"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if output.get("stored") and output.get("record_id"):
        return f"Tool completed successfully. Record ID: {output['record_id']}."
    if output.get("status") and output.get("erp_id"):
        return f"Tool completed successfully. ERP ID: {output['erp_id']}."
    return "Tool completed successfully."


def _selection_error_response(
    request: PipelineRequest,
    error: ToolSelectionError,
) -> PipelineResponse:
    return PipelineResponse(
        ok=False,
        intent="tool_selection",
        mode="vision" if request.has_image else "text",
        reply=str(error),
        tool_calls=[],
        structured_data={},
        meta={
            "mcp_orchestrated": True,
            "error_category": "tool_selection",
        },
    )


def _missing_parameters_response(
    request: PipelineRequest,
    selection: ToolSelection,
) -> PipelineResponse:
    missing = ", ".join(selection.missing_parameters)
    return PipelineResponse(
        ok=False,
        intent=selection.intent,
        mode="vision" if request.has_image else "text",
        reply=f"I need these details before I can continue: {missing}.",
        tool_calls=[],
        structured_data={},
        meta={
            "mcp_orchestrated": True,
            "tool_selected": selection.tool_selected,
            "selection_reason": selection.selection_reason,
            "confidence": selection.confidence,
            "error_category": "missing_parameters",
            "missing_parameters": selection.missing_parameters,
        },
    )
