from __future__ import annotations

import re
from typing import Any

from tools import storage_tools


REQUIRED_FIELDS = ["vendor", "invoice_number", "date", "items", "amount"]


def extract_invoice_data(payload: Any) -> dict[str, Any]:
    raw_text = _payload_text(payload)
    normalized_text = _normalize_multilingual_invoice_labels(raw_text)
    source = _payload_dict(payload)
    source_candidate = {
        **source,
        "raw_text": normalized_text or raw_text,
        "extracted_text": normalized_text or raw_text,
    }

    invoice = storage_tools.normalize_invoice_record(source_candidate)
    if invoice is None and (normalized_text or raw_text):
        raw_invoice = storage_tools._build_invoice_from_ocr_text(normalized_text or raw_text)
        invoice = storage_tools.normalize_invoice_record(
            {
                **raw_invoice,
                "raw_text": normalized_text or raw_text,
                "extracted_text": normalized_text or raw_text,
            }
        )
    if invoice is None:
        invoice = {
            "invoice_id": "",
            "vendor": "",
            "invoice_number": "",
            "date": "",
            "currency": "",
            "items": [],
            "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 0.0},
        }

    gst = _extract_gst_breakdown(normalized_text or raw_text, invoice)
    validation = validate_invoice_extraction(invoice)
    field_confidence = _score_fields(invoice, validation, normalized_text or raw_text)
    confidence = _overall_confidence(field_confidence, validation, invoice)
    summary = invoice.get("summary") if isinstance(invoice.get("summary"), dict) else {}

    return {
        "type": "invoice",
        "vendor": invoice.get("vendor", ""),
        "invoice_number": invoice.get("invoice_number", ""),
        "date": invoice.get("date", ""),
        "currency": invoice.get("currency", ""),
        "amount": storage_tools._to_number(summary.get("total_amount")),
        "gst": gst,
        "items": invoice.get("items", []),
        "summary": {
            "subtotal": storage_tools._to_number(summary.get("subtotal")),
            "tax": storage_tools._to_number(summary.get("tax")),
            "total_amount": storage_tools._to_number(summary.get("total_amount")),
        },
        "confidence": confidence,
        "field_confidence": field_confidence,
        "validation": validation,
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "invoice": {
            "vendor": invoice.get("vendor", ""),
            "invoice_number": invoice.get("invoice_number", ""),
            "date": invoice.get("date", ""),
            "currency": invoice.get("currency", ""),
            "subtotal": storage_tools._to_number(summary.get("subtotal")),
            "tax": storage_tools._to_number(summary.get("tax")),
            "total_amount": storage_tools._to_number(summary.get("total_amount")),
        },
        "purchases": invoice.get("items", []),
    }


def validate_invoice_extraction(invoice: dict[str, Any] | None) -> dict[str, Any]:
    if invoice is None:
        return {
            "valid": False,
            "reason": "missing vendor, invoice_number, date, items, amount",
            "missing_fields": REQUIRED_FIELDS.copy(),
        }

    summary = invoice.get("summary") if isinstance(invoice.get("summary"), dict) else {}
    items = invoice.get("items") if isinstance(invoice.get("items"), list) else []
    missing_fields = []
    if not storage_tools._to_text(invoice.get("vendor")):
        missing_fields.append("vendor")
    if not storage_tools._to_text(invoice.get("invoice_number")):
        missing_fields.append("invoice_number")
    if not storage_tools._to_text(invoice.get("date")):
        missing_fields.append("date")
    if not any(storage_tools._is_purchase_item(storage_tools._normalize_item(item, index)) for index, item in enumerate(items, start=1)):
        missing_fields.append("items")
    if storage_tools._to_number(summary.get("total_amount")) <= 0:
        missing_fields.append("amount")

    if missing_fields:
        return {
            "valid": False,
            "reason": "missing " + ", ".join(missing_fields),
            "missing_fields": missing_fields,
        }

    storage_reason = storage_tools._invoice_validation_reason(invoice)
    if storage_reason:
        return {
            "valid": False,
            "reason": storage_reason,
            "missing_fields": [],
        }

    subtotal = storage_tools._to_number(summary.get("subtotal"))
    tax = storage_tools._to_number(summary.get("tax"))
    total = storage_tools._to_number(summary.get("total_amount"))
    if subtotal and tax and total and abs((subtotal + tax) - total) > max(1.0, total * 0.03):
        return {
            "valid": False,
            "reason": "subtotal plus tax does not match total_amount",
            "missing_fields": [],
        }

    return {"valid": True, "reason": "", "missing_fields": []}


def _payload_dict(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _payload_text(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("extracted_text", "raw_text", "normalized_text", "summary"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    return str(payload or "").strip()


def _normalize_multilingual_invoice_labels(text: str) -> str:
    normalized = text or ""
    replacements = {
        "विक्रेता नाम": "Vendor Name",
        "विक्रेता": "Vendor",
        "बिल संख्या": "Invoice No.",
        "चालान संख्या": "Invoice No.",
        "इनवॉइस संख्या": "Invoice No.",
        "दिनांक": "Date",
        "वस्तु विवरण मात्रा दर कुल": "Item Description Qty Rate Total",
        "वस्तु विवरण": "Item Description",
        "मात्रा": "Qty",
        "दर": "Rate",
        "कुल राशि": "Total Amount",
        "कुल": "Total",
        "आईजीएसटी": "IGST",
        "सीजीएसटी": "CGST",
        "एसजीएसटी": "SGST",
        "ജി.എസ്.ടി": "GST",
        "തുക": "Total Amount",
        "തീയതി": "Date",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _extract_gst_breakdown(text: str, invoice: dict[str, Any]) -> dict[str, float]:
    normalized_text = _normalize_multilingual_invoice_labels(text)
    igst = _match_tax_amount(normalized_text, "igst")
    cgst = _match_tax_amount(normalized_text, "cgst")
    sgst = _match_tax_amount(normalized_text, "sgst")
    summary = invoice.get("summary") if isinstance(invoice.get("summary"), dict) else {}
    summary_tax = storage_tools._to_number(summary.get("tax"))
    total = round(igst + cgst + sgst, 2)
    if not total:
        total = summary_tax
    if total and not any([igst, cgst, sgst]):
        igst = total if re.search(r"\bigst\b", normalized_text, re.IGNORECASE) else 0.0
    return {
        "igst": round(igst, 2),
        "cgst": round(cgst, 2),
        "sgst": round(sgst, 2),
        "total": round(total, 2),
    }


def _match_tax_amount(text: str, label: str) -> float:
    match = re.search(
        rf"\b{label}\b(?:\s*\([^)]*\))?\D{{0,30}}([0-9][0-9,]*(?:\.[0-9]{{1,2}})?)",
        text,
        flags=re.IGNORECASE,
    )
    return storage_tools._to_number(match.group(1)) if match else 0.0


def _score_fields(
    invoice: dict[str, Any],
    validation: dict[str, Any],
    text: str,
) -> dict[str, float]:
    summary = invoice.get("summary") if isinstance(invoice.get("summary"), dict) else {}
    items = invoice.get("items") if isinstance(invoice.get("items"), list) else []
    scores = {
        "vendor": 0.95 if invoice.get("vendor") else 0.0,
        "invoice_number": 0.95 if invoice.get("invoice_number") else 0.0,
        "date": 0.9 if invoice.get("date") else 0.0,
        "amount": 0.95 if storage_tools._to_number(summary.get("total_amount")) > 0 else 0.0,
        "gst": 0.9 if _extract_gst_breakdown(text, invoice)["total"] > 0 else 0.45,
        "items": 0.95 if items else 0.0,
    }
    if not validation.get("valid"):
        for field in validation.get("missing_fields", []):
            if field in scores:
                scores[field] = 0.0
    return scores


def _overall_confidence(
    field_confidence: dict[str, float],
    validation: dict[str, Any],
    invoice: dict[str, Any],
) -> float:
    if not field_confidence:
        return 0.0
    weighted = (
        field_confidence["vendor"]
        + field_confidence["invoice_number"]
        + field_confidence["date"]
        + field_confidence["amount"]
        + field_confidence["items"]
        + field_confidence["gst"] * 0.5
    ) / 5.5
    if validation.get("valid"):
        weighted += 0.05
    else:
        weighted -= 0.15

    summary = invoice.get("summary") if isinstance(invoice.get("summary"), dict) else {}
    subtotal = storage_tools._to_number(summary.get("subtotal"))
    tax = storage_tools._to_number(summary.get("tax"))
    total = storage_tools._to_number(summary.get("total_amount"))
    if subtotal and tax and total and abs((subtotal + tax) - total) <= max(1.0, total * 0.03):
        weighted += 0.03

    return round(max(0.0, min(0.99, weighted)), 2)
