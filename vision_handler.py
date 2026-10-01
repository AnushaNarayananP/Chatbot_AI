import base64
import re
import urllib.parse
from pathlib import Path

from openrouter_client import (
    OpenRouterError,
    format_user_facing_error,
    get_env_value,
    post_chat_completion,
)


MODEL_NAME = "google/gemini-2.5-flash"
FALLBACK_MODEL_NAME = "anthropic/claude-sonnet-4"
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".jfif", ".webp"}
EMPTY_OCR_ERROR = (
    "The OCR model returned no readable text. Try Gemini vision, "
    "a clearer image, or another vision model."
)


def is_supported_image_file(file_name: str) -> bool:
    return Path(file_name or "").suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def guess_mime_type(file_name: str) -> str:
    extension = Path(file_name or "").suffix.lower()
    if extension == ".png":
        return "image/png"
    if extension in {".jpg", ".jpeg", ".jfif"}:
        return "image/jpeg"
    if extension == ".webp":
        return "image/webp"
    return "application/octet-stream"


def encode_uploaded_image_to_data_url(uploaded_file) -> str:
    if uploaded_file is None:
        raise ValueError("No image file was provided.")
    if not is_supported_image_file(uploaded_file.name):
        raise ValueError(
            "Unsupported image type. Please upload a PNG, JPG, JPEG, JFIF, or WEBP image."
        )

    image_bytes = uploaded_file.getvalue()
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    mime_type = guess_mime_type(uploaded_file.name)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def validate_image_url(image_url: str) -> str:
    cleaned_url = (image_url or "").strip()
    if not cleaned_url:
        raise ValueError("Please provide a valid image URL.")

    parsed_url = urllib.parse.urlparse(cleaned_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("Image URL must start with http:// or https://")

    path_extension = Path(parsed_url.path).suffix.lower()
    if path_extension and path_extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(
            "Image URL must point to a PNG, JPG, JPEG, JFIF, or WEBP image."
        )

    return cleaned_url


def detect_vision_task(user_prompt: str) -> str:
    prompt = (user_prompt or "").strip().lower()
    if not prompt:
        return "analyze"

    ocr_keywords = {
        "extract text",
        "extract data",
        "extract details",
        "what is written",
        "read this",
        "bill",
        "invoice",
        "document",
        "receipt",
        "text in this image",
        "store data",
        "save data",
        "store invoice",
        "save invoice",
        "store invoice details",
        "save invoice details",
        "extract structured",
        "structured data",
        "ocr",
        "handwritten",
        "signboard",
    }
    caption_keywords = {
        "describe",
        "what is in this image",
        "what's in this image",
        "caption",
        "what do you see",
        "describe this image",
        "describe the image",
    }

    if any(keyword in prompt for keyword in ocr_keywords):
        return "ocr"
    if any(keyword in prompt for keyword in caption_keywords):
        return "caption"
    if "?" in prompt or prompt:
        return "qa"
    return "analyze"


def build_vision_instruction(user_prompt: str, detected_language: str, task: str) -> str:
    language_rule = (
        "Reply in the same language and script style as the user's prompt. "
        f"Detected language/style: {detected_language}. "
    )
    if detected_language == "manglish":
        language_rule += "Reply in Manglish using English letters only. "

    task_prompts = {
        "ocr": (
            "Extract all readable text from this image exactly as accurately as possible. "
            "If the image contains a document, receipt, invoice, bill, handwritten note, or sign, "
            "preserve line breaks when useful. Then provide a short summary. "
            "If it looks like a bill, invoice, or receipt, identify merchant/store name, date, "
            "total amount, and key line items only if clearly visible."
        ),
        "caption": (
            "Describe what is visible in this image clearly and naturally. "
            "Mention important objects, people, scene, and any visible text."
        ),
        "qa": (
            "Answer the user's question using only what can reasonably be inferred from the image. "
            "If the answer is uncertain, say so clearly."
        ),
        "analyze": (
            "Analyze this image and provide: "
            "1. a short description "
            "2. any visible text "
            "3. the most relevant answer to the user's intent."
        ),
    }
    task_instruction = task_prompts.get(task, task_prompts["analyze"])
    user_intent = (user_prompt or "").strip() or "Please analyze this image."
    invoice_requested = any(
        keyword in user_intent.lower()
        for keyword in (
            "invoice", "bill", "receipt", "store data", "save data",
            "extract data", "extract details", "extract", "structured data",
            "data", "store", "save",
        )
    )
    invoice_json_instruction = ""
    if invoice_requested:
        invoice_json_instruction = (
            " If this is an invoice, receipt, bill, or purchase order, "
            "after the readable text include one fenced JSON block "
            "with this exact shape: "
            '{"invoice_id":"","vendor":"","invoice_number":"","date":"","currency":"",'\
            '"items":[{"sr_no":0,"name":"","quantity":0,"rate":0.0,"total":0.0}],'
            '"summary":{"subtotal":0.0,"tax":0.0,"total_amount":0.0}}. '
            "Before the JSON, transcribe these fields verbatim when visible: "
            "Invoice No / Receipt # / Receipt No, Invoice Date / Receipt Date, "
            "each product/item row with description, quantity, unit price, and amount, "
            "Subtotal/Taxable Value, any tax (Sales Tax / IGST / CGST / SGST) amount, "
            "and Grand Total / Total. "
            "For vendor, use the company or person name at the top of the document "
            "(the seller/issuer, NOT the Bill To / Ship To recipient). "
            "For invoice_number, use the value printed next to Invoice No / Invoice Number / "
            "Receipt # / Receipt No; never use Challan No, E-Way Bill No, PAN, GSTIN, "
            "Transport ID, P.O.#, phone, or bank account fields. "
            "For date, use the Invoice Date or Receipt Date value. "
            "Transcribe the item table rows exactly, especially columns like "
            "QTY / Sr No, Description / Name of Product / Service, Unit Price / Rate, "
            "and Amount / Taxable Value. "
            "Use only values clearly visible in the document. Do not use address, PAN, GSTIN, "
            "phone, bank, or terms lines as item names. Put each product/service/labor row "
            "from the item table into items."
        )

    return (
        f"{language_rule}{task_instruction} "
        f"{invoice_json_instruction}"
        "Be concise, natural, and structured when helpful. "
        f"User prompt: {user_intent}"
    )


def call_openrouter_vision(
    user_prompt: str,
    image_data_url: str | None = None,
    image_url: str | None = None,
) -> dict:
    selected_image = image_data_url or image_url
    if not selected_image:
        return {"ok": False, "error": "No image was provided for vision analysis."}

    candidate_models = _resolve_openrouter_vision_models()
    first_model = candidate_models[0]
    last_error = None
    for selected_model in candidate_models:
        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": selected_image}},
                    ],
                }
            ],
        }

        try:
            response_dict = post_chat_completion(payload)
        except OpenRouterError as error:
            last_error = error
            if selected_model != candidate_models[-1] and _is_retryable_vision_error(error):
                continue
            return {"ok": False, "error": format_user_facing_error(str(error))}

        if not _openrouter_response_has_readable_content(response_dict):
            last_error = EMPTY_OCR_ERROR
            if selected_model != candidate_models[-1]:
                continue
            return {"ok": False, "error": EMPTY_OCR_ERROR}

        result = {
            "ok": True,
            "response": response_dict,
            "provider": "openrouter",
            "model": selected_model,
        }
        if selected_model != first_model:
            result["fallback_from"] = first_model
        return result

    return {"ok": False, "error": format_user_facing_error(str(last_error))}


def _resolve_openrouter_vision_models() -> list[str]:
    primary_model = get_env_value("OPENROUTER_VISION_MODEL", MODEL_NAME)
    fallback_models = _split_model_list(
        get_env_value("OPENROUTER_VISION_FALLBACK_MODEL", FALLBACK_MODEL_NAME)
    )
    models = [primary_model]
    for model in fallback_models:
        if model and model not in models:
            models.append(model)
    return models


def _split_model_list(value: str) -> list[str]:
    return [model.strip() for model in re.split(r"[,;]", value or "") if model.strip()]


def _openrouter_response_has_readable_content(response_dict: dict) -> bool:
    choices = response_dict.get("choices") or []
    if not choices:
        return False

    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        return any(
            isinstance(item, dict)
            and item.get("type") == "text"
            and str(item.get("text", "")).strip()
            for item in content
        )

    return bool(str(content or "").strip())


def _is_retryable_vision_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            '"code":429',
            '"code": 429',
            "temporarily rate-limited",
            "rate-limited upstream",
            "timed out",
            "no endpoints found",
            "temporarily unavailable",
            "overloaded",
        )
    )


def parse_vision_response(response_dict: dict) -> dict:
    if not response_dict.get("ok"):
        return {
            "ok": False,
            "task": None,
            "raw_text": "",
            "structured": {
                "summary": "",
                "extracted_text": "",
                "answer": "",
            },
            "error": response_dict.get("error", "Unknown vision error."),
        }

    provider_response = response_dict.get("response", {})
    choices = provider_response.get("choices") or []
    if not choices:
        return {
            "ok": False,
            "task": None,
            "raw_text": "",
            "structured": {
                "summary": "",
                "extracted_text": "",
                "answer": "",
            },
            "error": "OpenRouter returned an empty response.",
        }

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, list):
        raw_text = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    else:
        raw_text = "" if content is None else str(content).strip()

    if not raw_text:
        return {
            "ok": False,
            "task": None,
            "raw_text": "",
            "structured": {
                "summary": "",
                "extracted_text": "",
                "answer": "",
            },
            "error": "The vision model returned no readable content.",
        }

    return {
        "ok": True,
        "task": None,
        "raw_text": raw_text,
        "structured": {
            "summary": "",
            "extracted_text": "",
            "answer": "",
        },
        "error": None,
        "provider": response_dict.get("provider", "openrouter"),
        "model": response_dict.get("model", ""),
    }


def _extract_receipt_fields(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merchant = lines[0] if lines else ""

    date_match = re.search(
        r"(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b)",
        text,
        flags=re.IGNORECASE,
    )
    total_match = re.search(
        r"(total|grand total|amount due)[^\d]*([0-9]+(?:[.,][0-9]{2})?)",
        text,
        flags=re.IGNORECASE,
    )

    line_items = []
    for line in lines:
        if re.search(r"\d", line) and not re.search(
            r"total|amount due",
            line,
            re.IGNORECASE,
        ):
            line_items.append(line)
        if len(line_items) >= 5:
            break

    return {
        "merchant": merchant,
        "date": date_match.group(1) if date_match else "",
        "total": total_match.group(2) if total_match else "",
        "line_items": line_items,
    }


def _build_structured_result(task: str, raw_text: str) -> dict:
    structured = {
        "summary": "",
        "extracted_text": "",
        "answer": "",
    }

    if task == "ocr":
        receipt_fields = _extract_receipt_fields(raw_text)
        summary_parts = []
        if receipt_fields["merchant"]:
            summary_parts.append(f"Merchant: {receipt_fields['merchant']}")
        if receipt_fields["date"]:
            summary_parts.append(f"Date: {receipt_fields['date']}")
        if receipt_fields["total"]:
            summary_parts.append(f"Total: {receipt_fields['total']}")
        if receipt_fields["line_items"]:
            summary_parts.append(
                "Key items: " + "; ".join(receipt_fields["line_items"][:3])
            )

        structured["extracted_text"] = raw_text
        structured["summary"] = (
            " | ".join(summary_parts) if summary_parts else raw_text[:240]
        )
        structured["answer"] = structured["summary"]
        return structured

    if task == "caption":
        structured["summary"] = raw_text
        structured["answer"] = raw_text
        return structured

    if task == "qa":
        structured["answer"] = raw_text
        structured["summary"] = raw_text[:240]
        return structured

    structured["summary"] = raw_text[:240]
    structured["extracted_text"] = raw_text
    structured["answer"] = raw_text
    return structured


def run_vision_action(
    user_prompt: str,
    image_data_url: str | None = None,
    image_url: str | None = None,
    detected_language: str | None = None,
) -> dict:
    task = detect_vision_task(user_prompt)
    if detected_language is None:
        from chatbot import detect_language

        detected_language = detect_language(user_prompt)

    instruction = build_vision_instruction(user_prompt, detected_language, task)
    response = call_openrouter_vision(
        instruction,
        image_data_url=image_data_url,
        image_url=image_url,
    )
    parsed = parse_vision_response(response)
    parsed["task"] = task

    if not parsed["ok"]:
        return parsed

    parsed["structured"] = _build_structured_result(task, parsed["raw_text"])
    return parsed
