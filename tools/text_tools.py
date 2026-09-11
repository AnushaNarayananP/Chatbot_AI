from __future__ import annotations

import json
import re


def summarize_content(text: str) -> dict[str, str]:
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return {"summary": "", "source_text": ""}

    from chatbot import chat_with_text_provider

    prompt = (
        "Return JSON only with keys summary and key_points. "
        "summary must be a concise paragraph. key_points must be a list of short strings.\n\n"
        f"Text:\n{cleaned_text}"
    )
    response = chat_with_text_provider([{"role": "user", "content": prompt}])
    parsed = _parse_json_response(response)
    return {
        "summary": str(parsed.get("summary", "")).strip(),
        "key_points": parsed.get("key_points", []),
        "source_text": cleaned_text,
    }


def translate_text(text: str, target_language: str) -> dict[str, str]:
    cleaned_text = (text or "").strip()
    destination = (target_language or "english").strip()
    from chatbot import chat_with_text_provider

    prompt = (
        "Return JSON only with keys translated_text and target_language.\n"
        f"Target language: {destination}\n"
        f"Text:\n{cleaned_text}"
    )
    response = chat_with_text_provider([{"role": "user", "content": prompt}])
    parsed = _parse_json_response(response)
    return {
        "translated_text": str(parsed.get("translated_text", "")).strip(),
        "target_language": str(parsed.get("target_language", destination)).strip(),
        "source_text": cleaned_text,
    }


def answer_question(question: str, context_text: str = "") -> dict[str, str]:
    cleaned_question = (question or "").strip()
    from chatbot import chat_with_text_provider

    prompt = (
        "Answer the question clearly. Return JSON only with keys answer and confidence_note.\n"
        f"Question: {cleaned_question}\n"
        f"Context: {context_text.strip()}"
    )
    response = chat_with_text_provider([{"role": "user", "content": prompt}])
    parsed = _parse_json_response(response)
    return {
        "answer": str(parsed.get("answer", "")).strip(),
        "confidence_note": str(parsed.get("confidence_note", "")).strip(),
    }


def _parse_json_response(response: str) -> dict:
    cleaned_response = (response or "").strip()
    try:
        return json.loads(cleaned_response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned_response, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
