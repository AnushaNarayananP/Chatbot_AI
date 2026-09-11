from __future__ import annotations

from pipeline.classifier import classify_request
from pipeline.memory import append_conversation_turn
from pipeline.models import IntentType, PipelineRequest, PipelineResponse, ToolCall
from pipeline.registry import get_tool


def execute_pipeline(request: PipelineRequest) -> PipelineResponse:
    classification = classify_request(request)
    tool_calls = _build_tool_plan(request, classification.intent, classification.target_language)

    context = {
        "prompt": request.prompt,
        "uploaded_image": request.uploaded_image,
        "image_url": request.image_url,
        "detected_language": request.detected_language,
        "current_text": request.prompt.strip(),
        "structured_data": {},
        "stored_record": None,
        "rag_session_id": request.rag_session_id,
    }

    for tool_call in tool_calls:
        try:
            output = _execute_tool_call(tool_call, context)
            tool_call.status = "completed"
            tool_call.output = output
        except Exception as error:
            tool_call.status = "failed"
            tool_call.error = str(error)
            return PipelineResponse(
                ok=False,
                intent=classification.intent.value,
                mode="vision" if request.has_image else "text",
                reply=str(error),
                tool_calls=tool_calls,
                structured_data=context["structured_data"],
                meta={
                    "source_type": classification.source_type,
                    "confidence": classification.confidence,
                    "target_language": classification.target_language,
                    "reason": classification.reason,
                },
            )

    reply = _build_final_reply(classification.intent, context)
    response = PipelineResponse(
        ok=True,
        intent=classification.intent.value,
        mode="vision" if request.has_image else "text",
        reply=reply,
        tool_calls=tool_calls,
        structured_data=context["structured_data"],
        meta={
            "source_type": classification.source_type,
            "confidence": classification.confidence,
            "target_language": classification.target_language,
            "reason": classification.reason,
            "stored_record": context["stored_record"],
        },
    )
    append_conversation_turn(
        {
            "prompt": request.prompt,
            "intent": classification.intent.value,
            "reply": reply,
            "structured_data": context["structured_data"],
        }
    )
    return response


def _build_tool_plan(
    request: PipelineRequest,
    intent: IntentType,
    target_language: str | None,
) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []
    if request.has_image:
        tool_calls.append(
            ToolCall(
                name="extract_text_from_image",
                arguments={"prompt": request.prompt},
            )
        )

    if intent == IntentType.TRANSLATION:
        tool_calls.append(
            ToolCall(
                name="translate_text",
                arguments={"target_language": target_language or "english"},
            )
        )
    elif intent == IntentType.WORKFLOW_TRIGGER:
        if request.has_image:
            tool_calls.append(ToolCall(name="extract_invoice_data", arguments={}))
            tool_calls.append(ToolCall(name="store_data", arguments={}))
            tool_calls.append(ToolCall(name="push_invoice_to_erp", arguments={}))
        else:
            tool_calls.append(ToolCall(name="store_data", arguments={}))
    elif intent in {
        IntentType.DATA_EXTRACTION,
    }:
        if request.has_image:
            tool_calls.append(ToolCall(name="extract_invoice_data", arguments={}))
            tool_calls.append(ToolCall(name="store_data", arguments={}))
            tool_calls.append(ToolCall(name="push_invoice_to_erp", arguments={}))
        else:
            tool_calls.append(ToolCall(name="answer_question", arguments={}))
    elif intent in {
        IntentType.QA,
        IntentType.SUMMARIZATION,
    }:
        tool_calls.append(ToolCall(name="answer_question", arguments={}))
    elif intent == IntentType.RAG_QA:
        tool_calls.append(ToolCall(name="rag_answer_question", arguments={}))

    return tool_calls


def _execute_tool_call(tool_call: ToolCall, context: dict) -> dict:
    tool = get_tool(tool_call.name)

    if tool_call.name == "extract_text_from_image":
        output = tool(
            prompt=context["prompt"],
            uploaded_image=context["uploaded_image"],
            image_url=context["image_url"],
            detected_language=context["detected_language"],
        )
        context["current_text"] = output.get("extracted_text", "")
        context["structured_data"]["ocr"] = output
        return output

    if tool_call.name == "translate_text":
        output = tool(context["current_text"], tool_call.arguments["target_language"])
        context["structured_data"]["translation"] = output
        return output

    if tool_call.name == "extract_invoice_data":
        payload = context["structured_data"].get("ocr") or context.get("current_text", "")
        output = tool(payload)
        context["structured_data"]["invoice_extraction"] = output
        context["structured_data"]["validation"] = output.get("validation", {})
        context["current_text"] = output.get("normalized_text") or output.get("raw_text") or context["current_text"]
        return output

    if tool_call.name == "store_data":
        invoice_extraction = context["structured_data"].get("invoice_extraction")
        if isinstance(invoice_extraction, dict):
            validation = invoice_extraction.get("validation", {})
            if not validation.get("valid"):
                raw_invoice_text = (
                    invoice_extraction.get("raw_text")
                    or invoice_extraction.get("normalized_text")
                    or ""
                ).strip()
                if not raw_invoice_text or raw_invoice_text.lower() == "none":
                    output = {
                        "stored": False,
                        "duplicate": False,
                        "message": "OCR did not return readable invoice text. Please retry the image or use a clearer image.",
                        "validation_reason": "empty OCR text",
                        "normalized_invoice": None,
                        "database_file": "chatbot.db",
                    }
                    context["stored_record"] = output
                    context["structured_data"]["storage"] = output
                    return output
                output = {
                    "stored": False,
                    "duplicate": False,
                    "message": "Invalid invoice structure",
                    "validation_reason": validation.get("reason", "invoice validation failed"),
                    "normalized_invoice": invoice_extraction,
                    "database_file": "chatbot.db",
                }
                context["stored_record"] = output
                context["structured_data"]["storage"] = output
                return output
            payload = invoice_extraction
        else:
            payload = context["structured_data"].get("ocr") or context.get("current_text", "")
        if isinstance(payload, dict) and not _has_usable_ocr_text(payload):
            if "invoice_number" not in payload:
                output = {
                    "stored": False,
                    "duplicate": False,
                    "message": "OCR did not return readable invoice text. Please retry the image or use a clearer image.",
                    "validation_reason": "empty OCR text",
                    "normalized_invoice": None,
                    "database_file": "chatbot.db",
                }
                context["stored_record"] = output
                context["structured_data"]["storage"] = output
                return output
        output = _store_with_ocr_text_retry(tool, payload)
        context["stored_record"] = output
        context["structured_data"]["storage"] = output
        return output

    if tool_call.name == "push_invoice_to_erp":
        storage = context["structured_data"].get("storage", {})
        if not storage.get("stored") or storage.get("duplicate"):
            return {
                "status": "skipped",
                "reason": storage.get("duplicate_reason")
                or storage.get("validation_reason")
                or "invoice was not stored",
            }

        invoice_payload = context["structured_data"].get("invoice_extraction", {})
        if storage.get("record_id") and isinstance(invoice_payload, dict):
            invoice_payload = {**invoice_payload, "invoice_id": storage["record_id"]}
        output = tool(invoice_payload)
        context["structured_data"]["erp"] = output
        return output

    if tool_call.name == "answer_question":
        output = tool(context["prompt"], context.get("current_text", ""))
        context["structured_data"]["answer"] = output
        return output

    if tool_call.name == "rag_answer_question":
        session_id = context.get("rag_session_id", "")
        output = tool(context["prompt"], session_id)
        context["structured_data"]["rag_answer"] = output
        return output

    raise ValueError(f"Unknown tool: {tool_call.name}")


def _has_usable_ocr_text(payload: dict) -> bool:
    for key in ("extracted_text", "raw_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip() and value.strip().lower() != "none":
            return True
    return False


def _store_with_ocr_text_retry(tool, payload) -> dict:
    output = tool(payload)
    if output.get("stored") or output.get("duplicate") or not isinstance(payload, dict):
        return output

    for key in ("extracted_text", "raw_text"):
        text_payload = payload.get(key)
        if not isinstance(text_payload, str) or not text_payload.strip():
            continue

        retry_output = tool(text_payload)
        if retry_output.get("stored") or retry_output.get("duplicate"):
            retry_output["retried_from"] = f"ocr.{key}"
            retry_output["first_attempt"] = output
            return retry_output

    return output


def _build_final_reply(intent: IntentType, context: dict) -> str:
    structured_data = context["structured_data"]
    if intent == IntentType.OCR:
        ocr_result = structured_data.get("ocr", {})
        return ocr_result.get("extracted_text", "") or ocr_result.get("summary", "")

    if intent == IntentType.SUMMARIZATION:
        answer = structured_data.get("answer", {})
        return answer.get("answer", "") or context["prompt"]

    if intent == IntentType.TRANSLATION:
        translation = structured_data.get("translation", {})
        return translation.get("translated_text", "")

    if intent == IntentType.DATA_EXTRACTION:
        invoice = structured_data.get("invoice_extraction")
        storage = structured_data.get("storage", {})
        erp = structured_data.get("erp")
        if isinstance(invoice, dict):
            validation = invoice.get("validation", {})
            if not validation.get("valid"):
                return f"Invalid invoice structure\nReason: {validation.get('reason', 'invoice validation failed')}"
            if storage.get("duplicate"):
                return _build_duplicate_reply(storage)
            if storage.get("stored") and erp:
                return (
                    f"Invoice stored successfully with ID {storage.get('record_id', 'unknown')} "
                    f"and pushed to mock ERP as {erp.get('erp_id', 'unknown')}."
                )
        answer = structured_data.get("answer", {})
        return answer.get("answer", "") or context["prompt"]

    if intent == IntentType.WORKFLOW_TRIGGER:
        storage = structured_data.get("storage", {})
        if storage.get("duplicate"):
            return _build_duplicate_reply(storage)
        erp = structured_data.get("erp")
        if storage.get("stored") and erp:
            return (
                f"Invoice stored successfully with ID {storage.get('record_id', 'unknown')} "
                f"and pushed to mock ERP as {erp.get('erp_id', 'unknown')}."
            )
        if storage.get("stored"):
            return f"Invoice stored successfully with ID {storage.get('record_id', 'unknown')}."
        message = storage.get(
            "message",
            "Could not create a valid invoice record from the extracted text.",
        )
        if storage.get("validation_reason") and storage.get("validation_reason") != "empty OCR text":
            return f"{message}\nReason: {storage['validation_reason']}"
        return message

    if intent == IntentType.RAG_QA:
        rag_answer = structured_data.get("rag_answer", {})
        answer_text = rag_answer.get("answer", "")
        sources = rag_answer.get("sources", [])
        if answer_text:
            if sources:
                source_note = ", ".join(sources)
                return f"{answer_text}\n\n📄 *Sources: {source_note}*"
            return answer_text
        return context["prompt"]

    answer = structured_data.get("answer", {})
    return answer.get("answer", "") or context["prompt"]


def _build_duplicate_reply(storage: dict) -> str:
    existing_invoice = storage.get("existing_invoice", {})
    lines = [storage.get("message", "Duplicate invoice detected. This invoice was not stored.")]
    if storage.get("duplicate_reason"):
        lines.append(f"Reason: {storage['duplicate_reason']}")
    if existing_invoice.get("invoice_id"):
        lines.append(f"Existing invoice ID: {existing_invoice['invoice_id']}")
    if existing_invoice.get("invoice_number"):
        lines.append(f"Existing invoice number: {existing_invoice['invoice_number']}")
    return "\n".join(lines)
