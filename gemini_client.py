import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT_SECONDS = 20


class GeminiError(RuntimeError):
    pass


def _load_env_file():
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    # Streamlit Community Cloud: inject st.secrets into os.environ so that
    # every downstream os.environ.get() / get_env_value() call works without
    # a .env file.  Only runs when Streamlit is available.
    try:
        import streamlit as st  # noqa: F811
        for key, value in st.secrets.items():
            if isinstance(value, str) and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_env_file()


def get_env_value(name, default=""):
    return os.environ.get(name, default).strip()


def get_timeout_seconds(default=DEFAULT_TIMEOUT_SECONDS):
    raw_value = get_env_value("GEMINI_TIMEOUT_SECONDS", str(default))
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return max(parsed, 1)


def build_generate_content_url(model):
    api_key = get_env_value("GEMINI_API_KEY")
    if not api_key:
        raise GeminiError("Missing GEMINI_API_KEY in environment.")

    quoted_model = urllib.parse.quote(model, safe="")
    return f"{GEMINI_ENDPOINT}/{quoted_model}:generateContent?key={api_key}"


def post_generate_content(model, payload, timeout=None):
    request = urllib.request.Request(
        build_generate_content_url(model),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=get_timeout_seconds() if timeout is None else timeout,
        ) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise GeminiError(f"Gemini returned HTTP {error.code}. Details: {body}") from error
    except urllib.error.URLError as error:
        raise GeminiError(f"Gemini request failed. Details: {error.reason}") from error

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise GeminiError("Gemini returned invalid JSON.") from error


def build_inline_image_part(image_data_url):
    header, separator, encoded_data = (image_data_url or "").partition(",")
    if not separator or ";base64" not in header:
        raise GeminiError("Invalid image data URL for Gemini vision request.")

    mime_type = header.split(":", 1)[-1].split(";", 1)[0].strip() or "application/octet-stream"
    if not encoded_data.strip():
        raise GeminiError("Image data URL is missing encoded image bytes.")

    return {
        "inline_data": {
            "mime_type": mime_type,
            "data": encoded_data.strip(),
        }
    }


def extract_text_from_response(response_dict):
    candidates = response_dict.get("candidates") or []
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts") or []
    return "\n".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()


def is_retryable_gemini_error(error):
    message = str(error)
    normalized_message = message.lower()
    return (
        "http 503" in normalized_message
        or '"status": "unavailable"' in normalized_message
        or "experiencing high demand" in normalized_message
        or "timed out" in normalized_message
        or "empty response" in normalized_message
    )
