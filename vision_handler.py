import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "nvidia/nemotron-nano-12b-v2-vl:free"
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _load_env_file():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def is_supported_image_file(file_name: str) -> bool:
    return Path(file_name or "").suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def guess_mime_type(file_name: str) -> str:
    extension = Path(file_name or "").suffix.lower()
    if extension == ".png":
        return "image/png"
    if extension in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if extension == ".webp":
        return "image/webp"
    return "application/octet-stream"


def encode_uploaded_image_to_data_url(uploaded_file) -> str:
    if uploaded_file is None:
        raise ValueError("No image file was provided.")
    if not is_supported_image_file(uploaded_file.name):
        raise ValueError(
            "Unsupported image type. Please upload a PNG, JPG, JPEG, or WEBP image."
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
            "Image URL must point to a PNG, JPG, JPEG, or WEBP image."
        )

    return cleaned_url


def detect_vision_task(user_prompt: str) -> str:
    prompt = (user_prompt or "").strip().lower()
    if not prompt:
        return "analyze"

    ocr_keywords = {
        "extract text",
        "what is written",
        "read this",
        "bill",
        "invoice",
        "document",
        "receipt",
        "text in this image",
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
    user_intent = (user_prompt or "").strip()
    if not user_intent:
        user_intent = "Please analyze this image."

    return (
        f"{language_rule}{task_instruction} "
        "Be concise, natural, and structured when helpful. "
        f"User prompt: {user_intent}"
    )


def call_openrouter_vision(
    user_prompt: str,
    image_data_url: str | None = None,
    image_url: str | None = None,
) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "Missing OPENROUTER_API_KEY in environment."}

    selected_image = image_data_url or image_url
    if not selected_image:
        return {"ok": False, "error": "No image was provided for vision analysis."}

    payload = {
        "model": os.environ.get("OPENROUTER_VISION_MODEL", MODEL_NAME),
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

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", "http://localhost:8501"),
        "X-Title": os.environ.get("OPENROUTER_APP_NAME", "FriendlyBot"),
    }

    request = urllib.request.Request(
        OPENROUTER_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "error": f"OpenRouter returned HTTP {error.code}. Details: {body}",
        }
    except urllib.error.URLError as error:
        return {
            "ok": False,
            "error": f"OpenRouter request failed. Details: {error.reason}",
        }

    try:
        response_dict = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error": "OpenRouter returned invalid JSON."}

    return {"ok": True, "response": response_dict}


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
        raw_text = str(content).strip()

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
        if re.search(r"\d", line) and not re.search(r"total|amount due", line, re.IGNORECASE):
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
        structured["summary"] = " | ".join(summary_parts) if summary_parts else raw_text[:240]
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
        from chatbot import detect_language  # Local import to avoid circular import at module load

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
