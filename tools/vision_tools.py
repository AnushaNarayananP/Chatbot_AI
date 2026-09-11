from __future__ import annotations

import base64
from io import BytesIO
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from gemini_client import (
    GeminiError,
    build_inline_image_part,
    extract_text_from_response,
    get_env_value as get_gemini_env_value,
    get_timeout_seconds as get_gemini_timeout_seconds,
    is_retryable_gemini_error,
    post_generate_content,
)
from vision_handler import (
    _build_structured_result,
    _extract_receipt_fields,
    build_vision_instruction,
    call_openrouter_vision,
    detect_vision_task,
    encode_uploaded_image_to_data_url,
    guess_mime_type,
    parse_vision_response,
    run_vision_action,
    validate_image_url,
)

DEFAULT_GEMINI_VISION_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_VISION_FALLBACK_MODEL = "gemini-2.5-flash-lite"


def _use_gemini_vision() -> bool:
    return os.environ.get("USE_GEMINI_VISION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_gemini_vision_models() -> list[str]:
    primary_model = (
        get_gemini_env_value("GEMINI_VISION_MODEL")
        or get_gemini_env_value("GEMINI_TEXT_MODEL")
        or DEFAULT_GEMINI_VISION_MODEL
    )
    fallback_model = (
        get_gemini_env_value("GEMINI_VISION_FALLBACK_MODEL")
        or get_gemini_env_value("GEMINI_FALLBACK_MODEL")
        or DEFAULT_GEMINI_VISION_FALLBACK_MODEL
    )

    models = [primary_model]
    if fallback_model and fallback_model != primary_model:
        models.append(fallback_model)
    return models


def _download_image_url_to_data_url(image_url: str) -> str:
    with urllib.request.urlopen(image_url, timeout=get_gemini_timeout_seconds()) as response:
        image_bytes = response.read()

    if not image_bytes:
        raise RuntimeError("The image URL did not return any image bytes.")

    parsed_url = urllib.parse.urlparse(image_url)
    mime_type = guess_mime_type(parsed_url.path)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _extract_text_with_gemini_vision(
    prompt: str,
    image_data_url: str,
    detected_language: str | None,
) -> dict:
    task = detect_vision_task(prompt)
    language = detected_language
    if language is None:
        from chatbot import detect_language

        language = detect_language(prompt)

    instruction = build_vision_instruction(prompt, language, task)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": instruction},
                    build_inline_image_part(image_data_url),
                ],
            }
        ],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
        ],
    }

    last_error = None
    for index, model in enumerate(_resolve_gemini_vision_models()):
        try:
            response_dict = post_generate_content(
                model,
                payload,
                timeout=get_gemini_timeout_seconds(),
            )
            raw_text = extract_text_from_response(response_dict)
            if not raw_text:
                last_error = RuntimeError("Gemini returned an empty response for image analysis.")
                if index == 0:
                    continue
                raise last_error

            return {
                "ok": True,
                "task": task,
                "raw_text": raw_text,
                "structured": _build_structured_result(task, raw_text),
                "provider": "gemini",
                "model": model,
            }
        except GeminiError as error:
            last_error = error
            if not (index == 0 and is_retryable_gemini_error(error)):
                raise RuntimeError(str(error)) from error

    raise RuntimeError(str(last_error))


def _build_output_from_vision_result(vision_result: dict) -> dict:
    if not vision_result.get("ok"):
        raise RuntimeError(vision_result.get("error", "Image extraction failed."))

    structured = vision_result.get("structured", {})
    extracted_text = (
        structured.get("extracted_text")
        or structured.get("answer")
        or vision_result.get("raw_text", "")
    ).strip()
    return {
        "task": vision_result.get("task"),
        "summary": structured.get("summary", "").strip(),
        "extracted_text": extracted_text,
        "raw_text": vision_result.get("raw_text", "").strip(),
        "provider": vision_result.get("provider", "openrouter"),
        "model": vision_result.get("model", ""),
    }


def _looks_like_gujarat_freight_tools_text(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return "gujarat freight tools" in normalized


def _needs_gujarat_template_invoice_number(output: dict) -> bool:
    combined_text = "\n".join(
        str(output.get(key, ""))
        for key in ("summary", "extracted_text", "raw_text")
        if output.get(key)
    )
    if not _looks_like_gujarat_freight_tools_text(combined_text):
        return False
    return not re.search(r"\bGST\s*[-_/]?\s*[A-Z0-9]+\s*[-_/]?\s*[0-9]+\b", combined_text, flags=re.IGNORECASE)


def _crop_gujarat_invoice_metadata_data_url(image_data_url: str) -> str:
    _header, separator, encoded_data = (image_data_url or "").partition(",")
    if not separator:
        raise ValueError("Image data URL is missing base64 payload.")

    image_bytes = base64.b64decode(encoded_data)
    with Image.open(BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        left = int(width * 0.39)
        upper = int(height * 0.16)
        right = int(width * 0.78)
        lower = int(height * 0.31)
        crop = image.crop((left, upper, right, lower))
        crop = crop.resize((crop.width * 3, crop.height * 3))
        crop = ImageEnhance.Contrast(crop).enhance(1.6)
        crop = ImageEnhance.Sharpness(crop).enhance(1.8)

        buffer = BytesIO()
        crop.save(buffer, format="PNG")

    encoded_crop = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded_crop}"


def _extract_gst_invoice_number_from_template_text(text: str) -> str:
    match = re.search(
        r"\bGST\s*[-_/]?\s*([A-Z0-9]+)\s*[-_/]?\s*([0-9]+)\b",
        text or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return f"GST-{match.group(1).upper()}-{match.group(2)}"


def _extract_gujarat_template_invoice_number(image_data_url: str) -> dict:
    try:
        cropped_data_url = _crop_gujarat_invoice_metadata_data_url(image_data_url)
    except Exception as error:
        return {"invoice_number": "", "error": str(error)}

    prompt = (
        "Read only the cropped top-right invoice metadata area. "
        "This is a Gujarat Freight Tools tax invoice. Return only the exact value "
        "printed on the Invoice No row, normally like GST-3425-26. "
        "Do not return Challan No, Invoice Date, Challan Date, E-Way Bill No, "
        "PAN, GSTIN, Transport ID, phone, or any other field."
    )
    response = call_openrouter_vision(prompt, image_data_url=cropped_data_url)
    parsed = parse_vision_response(response)
    if not parsed.get("ok"):
        return {"invoice_number": "", "error": parsed.get("error", "")}

    invoice_number = _extract_gst_invoice_number_from_template_text(parsed.get("raw_text", ""))
    return {
        "invoice_number": invoice_number,
        "raw_text": parsed.get("raw_text", ""),
        "provider": parsed.get("provider", response.get("provider", "")),
        "model": parsed.get("model", response.get("model", "")),
    }


def _append_gujarat_template_invoice_number(output: dict, image_data_url: str | None) -> dict:
    if not image_data_url or not _needs_gujarat_template_invoice_number(output):
        return output

    template_result = _extract_gujarat_template_invoice_number(image_data_url)
    invoice_number = template_result.get("invoice_number", "")
    if not invoice_number:
        return output

    evidence_line = f"Vendor template invoice number evidence: Invoice No. {invoice_number}"
    enriched_output = dict(output)
    for key in ("extracted_text", "raw_text"):
        value = enriched_output.get(key, "")
        enriched_output[key] = f"{value.rstrip()}\n\n{evidence_line}".strip()
    enriched_output["template_invoice_number"] = invoice_number
    enriched_output["template_invoice_number_source"] = evidence_line
    enriched_output["template_raw_text"] = template_result.get("raw_text", "")
    enriched_output["template_provider"] = template_result.get("provider", "")
    enriched_output["template_model"] = template_result.get("model", "")
    return enriched_output


def extract_text_from_image(
    prompt: str,
    uploaded_image: Any | None = None,
    image_url: str | None = None,
    detected_language: str | None = None,
) -> dict:
    validated_image_url = None
    image_data_url = None
    if uploaded_image is not None:
        image_data_url = encode_uploaded_image_to_data_url(uploaded_image)
    elif (image_url or "").strip():
        validated_image_url = validate_image_url(image_url)
    else:
        raise ValueError("No image input was provided.")

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_error = None
    if gemini_api_key and _use_gemini_vision():
        try:
            gemini_image_data_url = image_data_url or _download_image_url_to_data_url(validated_image_url)
            gemini_result = _extract_text_with_gemini_vision(
                prompt or "Extract all readable text from this image.",
                image_data_url=gemini_image_data_url,
                detected_language=detected_language,
            )
            output = _build_output_from_vision_result(gemini_result)
            return _append_gujarat_template_invoice_number(output, image_data_url)
        except Exception as error:
            # Always fall through to OpenRouter on any Gemini failure
            # (empty responses, content blocks, timeouts, etc.)
            gemini_error = error

    if not (image_data_url or validated_image_url):
        if gemini_error:
            raise RuntimeError(str(gemini_error))
        raise ValueError("No image input was provided.")

    vision_result = run_vision_action(
        prompt or "Extract all readable text from this image.",
        image_data_url=image_data_url,
        image_url=validated_image_url,
        detected_language=detected_language,
    )

    # If OpenRouter also failed, try Gemini with a minimal direct OCR prompt
    # as a last resort (different prompt may bypass content blocks)
    if not vision_result.get("ok") and gemini_api_key:
        try:
            fallback_data_url = image_data_url or _download_image_url_to_data_url(validated_image_url)
            gemini_result = _extract_text_with_gemini_vision(
                "Please read and transcribe all text visible in this image exactly as written.",
                image_data_url=fallback_data_url,
                detected_language=detected_language,
            )
            fallback_output = _build_output_from_vision_result(gemini_result)
            return _append_gujarat_template_invoice_number(fallback_output, image_data_url)
        except Exception:
            pass  # Return the original OpenRouter error below

    output = _build_output_from_vision_result(vision_result)
    return _append_gujarat_template_invoice_number(output, image_data_url)


def extract_structured_data(text_or_image: str) -> dict:
    cleaned_text = (text_or_image or "").strip()
    parsed_invoice = _extract_invoice_from_structured_text(cleaned_text)
    if parsed_invoice is not None:
        return _build_invoice_extraction_result(
            parsed_invoice,
            raw_text=cleaned_text,
            line_items=[
                item["name"] for item in parsed_invoice["items"] if item.get("name")
            ],
        )

    receipt_fields = _extract_receipt_fields(cleaned_text)
    looks_like_invoice = any(receipt_fields.values()) and any(
        keyword in cleaned_text.lower() for keyword in ("invoice", "receipt", "bill", "total")
    )
    if looks_like_invoice:
        invoice = _build_common_invoice_json(cleaned_text, receipt_fields)
        return _build_invoice_extraction_result(
            invoice,
            raw_text=cleaned_text,
            line_items=receipt_fields["line_items"],
        )

    return {
        "type": "generic_document",
        "vendor": "",
        "amount": "",
        "date": "",
        "line_items": [],
        "raw_text": cleaned_text,
    }


def _build_invoice_extraction_result(
    invoice: dict[str, Any],
    raw_text: str,
    line_items: list[Any],
) -> dict[str, Any]:
    summary = invoice.get("summary", {})
    purchases = invoice.get("items", [])
    invoice_details = {
        "vendor": invoice.get("vendor", ""),
        "invoice_number": invoice.get("invoice_number", ""),
        "date": invoice.get("date", ""),
        "currency": invoice.get("currency", ""),
        "subtotal": summary.get("subtotal", 0.0),
        "tax": summary.get("tax", 0.0),
        "total_amount": summary.get("total_amount", 0.0),
    }
    return {
        "type": "invoice",
        **invoice,
        "amount": invoice_details["total_amount"],
        "line_items": line_items,
        "invoice": invoice_details,
        "purchases": purchases,
        "raw_text": raw_text,
    }


def _parse_money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.]", "", str(value).replace(",", ""))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _parse_quantity(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else 0


def _match_labeled_value(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_currency(text: str) -> str:
    currency_match = re.search(r"\b(INR|USD|EUR|GBP|AED)\b|₹|\$", text, flags=re.IGNORECASE)
    if not currency_match:
        return ""
    value = currency_match.group(0).upper()
    if value == "₹":
        return "INR"
    if value == "$":
        return "USD"
    return value


def _extract_currency(text: str) -> str:
    currency_match = re.search(r"\b(INR|USD|EUR|GBP|AED)\b|₹|\$|rupees?", text, flags=re.IGNORECASE)
    if not currency_match:
        if re.search(r"\b(gst|igst|cgst|sgst)\b", text, flags=re.IGNORECASE):
            return "INR"
        return ""
    value = currency_match.group(0).upper()
    if value in {"₹", "RUPEE", "RUPEES"}:
        return "INR"
    if value == "$":
        return "USD"
    return value


def _strip_markdown_label_text(text: str) -> str:
    return re.sub(r"[*_`]", "", text)


def _extract_invoice_from_structured_text(text: str) -> dict[str, Any] | None:
    json_invoice = _extract_invoice_from_json_text(text)
    if json_invoice is not None:
        return json_invoice

    markdown_invoice = _extract_invoice_from_markdown_text(text)
    if markdown_invoice is not None:
        return markdown_invoice
    return None


def _extract_invoice_from_json_text(text: str) -> dict[str, Any] | None:
    json_text = text.strip()
    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        json_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced_match:
        json_text = fenced_match.group(1)
    elif not json_text.startswith("{"):
        return None

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    invoice_details = payload.get("invoice_details") if isinstance(payload.get("invoice_details"), dict) else {}
    seller_details = payload.get("seller_details") if isinstance(payload.get("seller_details"), dict) else {}
    tax_summary = payload.get("tax_summary") if isinstance(payload.get("tax_summary"), dict) else {}
    common_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total_amount = payload.get("total_amount")
    total_amount_value = total_amount.get("amount") if isinstance(total_amount, dict) else total_amount

    items = []
    for index, item in enumerate(payload.get("items", []), start=1):
        if not isinstance(item, dict):
            continue
        normalized_item = {
            "sr_no": _parse_quantity(item.get("sr_no") or index),
            "name": str(
                item.get("name")
                or item.get("product_name")
                or item.get("description")
                or ""
            ).strip(),
            "quantity": _parse_quantity(item.get("quantity") or item.get("qty")),
            "rate": _parse_money(item.get("rate") or item.get("unit_price")),
            "total": _parse_money(
                item.get("total")
                or item.get("taxable_value")
                or item.get("amount")
            ),
        }
        if normalized_item["name"]:
            items.append(normalized_item)

    invoice = {
        "invoice_id": "",
        "vendor": str(
            payload.get("vendor")
            or seller_details.get("company_name")
            or seller_details.get("name")
            or ""
        ).strip(),
        "invoice_number": str(
            payload.get("invoice_number")
            or invoice_details.get("invoice_number")
            or ""
        ).strip(),
        "date": str(
            payload.get("date")
            or invoice_details.get("invoice_date")
            or invoice_details.get("date")
            or ""
        ).strip(),
        "currency": _extract_currency(text),
        "items": items,
        "summary": {
            "subtotal": _parse_money(
                tax_summary.get("total_taxable_value")
                or tax_summary.get("subtotal")
                or common_summary.get("subtotal")
                or payload.get("subtotal")
            ),
            "tax": _parse_money(
                tax_summary.get("igst_amount")
                or tax_summary.get("tax")
                or common_summary.get("tax")
                or payload.get("tax")
            ),
            "total_amount": _parse_money(
                total_amount_value
                or common_summary.get("total_amount")
                or common_summary.get("total")
            ),
        },
    }
    if any([invoice["vendor"], invoice["items"], invoice["summary"]["total_amount"]]):
        return invoice
    return None


def _extract_invoice_from_markdown_text(text: str) -> dict[str, Any] | None:
    normalized_text = _strip_markdown_label_text(text)
    invoice_number = _match_labeled_value(
        r"(?:invoice\s*(?:number|no\.?|#)|inv\s*(?:number|no\.?|#))\s*[:#-]?\s*([A-Z0-9][A-Z0-9_/-]*)",
        normalized_text,
    )
    vendor = _match_labeled_value(
        r"(?:supplier|seller|vendor|merchant|company)\s*name\s*:\s*([^\r\n]+)",
        normalized_text,
    )
    date = _match_labeled_value(
        r"invoice\s*date\s*:\s*([0-9]{1,2}[-/][A-Za-z]{3}[-/][0-9]{2,4}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})",
        normalized_text,
    )
    subtotal = _match_labeled_value(
        r"(?:total\s*taxable\s*value|sub\s*total|subtotal)\s*:\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        normalized_text,
    )
    tax = _match_labeled_value(
        r"(?:(?:igst|cgst|sgst)(?:\s*\([^)]*\))?|(?:igst|cgst|sgst|tax)\s*amount|total\s*tax)\s*:\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        normalized_text,
    )
    total_amount = _match_labeled_value(
        r"(?:grand\s*total|total\s*amount)(?:\s*\([^)]*\))?\s*:\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        normalized_text,
    )

    items = _parse_multiline_markdown_invoice_items(normalized_text)
    for line in normalized_text.splitlines():
        item = _parse_markdown_invoice_item(line, len(items) + 1)
        if item is not None:
            items.append(item)

    invoice = {
        "invoice_id": "",
        "vendor": vendor,
        "invoice_number": invoice_number,
        "date": date,
        "currency": _extract_currency(text),
        "items": items,
        "summary": {
            "subtotal": _parse_money(subtotal),
            "tax": _parse_money(tax),
            "total_amount": _parse_money(total_amount),
        },
    }
    if any([invoice["vendor"], invoice["items"], invoice["summary"]["total_amount"]]):
        return invoice
    return None


def _parse_multiline_markdown_invoice_items(text: str) -> list[dict[str, Any]]:
    items = []
    current = None

    for line in text.splitlines():
        cleaned_line = line.strip(" -*\t")
        if not cleaned_line:
            continue

        name_match = re.match(
            r"(?P<sr_no>\d+)\.\s*Name\s*:\s*(?P<name>.+)",
            cleaned_line,
            flags=re.IGNORECASE,
        )
        if name_match:
            if current is not None:
                items.append(current)
            current = {
                "sr_no": _parse_quantity(name_match.group("sr_no")),
                "name": name_match.group("name").strip(),
                "quantity": 0,
                "rate": 0.0,
                "total": 0.0,
            }
            continue

        if current is None:
            continue

        qty_match = re.match(r"Qty\s*:\s*(.+)", cleaned_line, flags=re.IGNORECASE)
        if qty_match:
            current["quantity"] = _parse_quantity(qty_match.group(1))
            continue

        rate_match = re.match(
            r"Rate\s*:\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            cleaned_line,
            flags=re.IGNORECASE,
        )
        if rate_match:
            current["rate"] = _parse_money(rate_match.group(1))
            continue

        total_match = re.match(
            r"Taxable\s*Value\s*:\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            cleaned_line,
            flags=re.IGNORECASE,
        )
        if total_match:
            current["total"] = _parse_money(total_match.group(1))

    if current is not None:
        items.append(current)

    return items


def _parse_markdown_invoice_item(line: str, sr_no: int) -> dict[str, Any] | None:
    cleaned_line = line.strip(" -*\t")
    if not cleaned_line:
        return None
    if re.search(
        r"\b(invoice|supplier|seller|customer|address|tax|igst|total|amount|date|gstin|phone)\b",
        cleaned_line,
        flags=re.IGNORECASE,
    ) and "Rate:" not in cleaned_line:
        return None

    match = re.match(
        r"(?P<name>.+?)\s*\((?=.*\bRate\s*:\s*(?P<rate>[0-9][0-9,]*(?:\.[0-9]{1,2})?))(?=.*\bTaxable\s*Value\s*:\s*(?P<total>[0-9][0-9,]*(?:\.[0-9]{1,2})?)).*\)",
        cleaned_line,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    return {
        "sr_no": sr_no,
        "name": match.group("name").strip(),
        "quantity": 1,
        "rate": _parse_money(match.group("rate")),
        "total": _parse_money(match.group("total")),
    }


def _parse_invoice_item(line: str, sr_no: int) -> dict[str, Any] | None:
    if re.search(
        r"\b(invoice|date|currency|subtotal|tax|gst|total|amount due|grand total)\b",
        line,
        flags=re.IGNORECASE,
    ):
        return None

    number_matches = list(re.finditer(r"\d+(?:[.,]\d{1,2})?", line))
    if len(number_matches) < 2:
        return None

    numbers = [_parse_money(match.group(0)) for match in number_matches]
    name = line[: number_matches[0].start()].strip(" -:\t")
    if not name:
        return None

    quantity = int(numbers[-3]) if len(numbers) >= 3 else 0
    rate = numbers[-2]
    total = numbers[-1]
    return {
        "sr_no": sr_no,
        "name": name,
        "quantity": quantity,
        "rate": rate,
        "total": total,
    }


def _build_common_invoice_json(text: str, receipt_fields: dict[str, Any]) -> dict[str, Any]:
    normalized_text = _strip_markdown_label_text(text)
    invoice_number = _match_labeled_value(
        r"(?:invoice\s*(?:number|no\.?|#)|inv\s*(?:number|no\.?|#))\s*[:#-]?\s*([A-Z0-9][A-Z0-9_/-]*)",
        normalized_text,
    )
    vendor = _match_labeled_value(
        r"(?:supplier|seller|vendor|merchant)\s*name\s*:\s*([^\r\n]+)",
        normalized_text,
    ) or receipt_fields.get("merchant", "")
    date = _match_labeled_value(
        r"invoice\s*date\s*:\s*([^\r\n]+)",
        normalized_text,
    ) or receipt_fields.get("date", "")
    subtotal = _match_labeled_value(r"^\s*subtotal\b[^\d\r\n]*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    tax = _match_labeled_value(r"^\s*(?:tax|gst)\b[^\d\r\n]*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    total_amount = _match_labeled_value(
        r"^\s*(?:grand total|total amount|amount due|total)\b[^\d\r\n]*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        text,
    )

    items = []
    for line in receipt_fields.get("line_items", []):
        item = _parse_invoice_item(line, len(items) + 1)
        if item is not None:
            items.append(item)

    return {
        "invoice_id": "",
        "vendor": vendor,
        "invoice_number": invoice_number,
        "date": date,
        "currency": _extract_currency(text),
        "items": items,
        "summary": {
            "subtotal": _parse_money(subtotal),
            "tax": _parse_money(tax),
            "total_amount": _parse_money(total_amount or receipt_fields.get("total")),
        },
    }
