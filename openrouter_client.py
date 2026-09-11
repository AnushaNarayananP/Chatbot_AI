import json
import os
import http.client
import urllib.error
import urllib.request
from pathlib import Path


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_RETRY_COUNT = 2


class OpenRouterError(RuntimeError):
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
        import streamlit as st
        for key, value in st.secrets.items():
            if isinstance(value, str) and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_env_file()


def get_env_value(name, default=""):
    return os.environ.get(name, default).strip()


def get_timeout_seconds(default=DEFAULT_TIMEOUT_SECONDS):
    raw_value = get_env_value("OPENROUTER_TIMEOUT_SECONDS", str(default))
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return max(parsed, 1)


def get_primary_timeout_seconds(default=8):
    raw_value = get_env_value("OPENROUTER_PRIMARY_TIMEOUT_SECONDS", str(default))
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return max(parsed, 1)


def get_retry_count(default=DEFAULT_RETRY_COUNT):
    raw_value = get_env_value("OPENROUTER_RETRY_COUNT", str(default))
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return max(parsed, 1)


def extract_error_details(error_message):
    if "Details:" not in error_message:
        return {}

    _, _, raw_details = error_message.partition("Details:")
    raw_details = raw_details.strip()
    if not raw_details:
        return {}

    try:
        parsed = json.loads(raw_details)
    except json.JSONDecodeError:
        return {}

    error_payload = parsed.get("error", {})
    metadata = error_payload.get("metadata", {})
    return {
        "code": error_payload.get("code"),
        "message": error_payload.get("message", ""),
        "raw": metadata.get("raw", ""),
        "provider_name": metadata.get("provider_name", ""),
    }


def format_user_facing_error(error_message):
    lowered_message = (error_message or "").lower()
    if "getaddrinfo failed" in lowered_message or "name or service not known" in lowered_message:
        return (
            "Could not reach OpenRouter. Check your internet connection, DNS/VPN/proxy settings, "
            "or try again later."
        )
    if "timed out" in lowered_message:
        return "OpenRouter did not respond in time. Please retry shortly."

    details = extract_error_details(error_message)
    if details.get("code") == 429:
        provider_name = details.get("provider_name") or "the upstream provider"
        raw_message = details.get("raw") or "The selected model is temporarily rate-limited."
        return f"{raw_message} Please retry shortly or switch to another model. Provider: {provider_name}."
    if details.get("code") == 404:
        raw_message = details.get("raw") or details.get("message") or "The selected model isn't available."
        if raw_message.startswith("No endpoints found for"):
            raw_message = "The selected model isn't available on OpenRouter right now."
        return f"{raw_message} Please switch to another model."

    return error_message


def build_headers():
    api_key = get_env_value("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("Missing OPENROUTER_API_KEY in environment.")

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": get_env_value("OPENROUTER_SITE_URL", "http://localhost:8501"),
        "X-Title": get_env_value("OPENROUTER_APP_NAME", "FriendlyBot"),
    }


def post_chat_completion(payload, timeout=None):
    request = urllib.request.Request(
        OPENROUTER_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=build_headers(),
        method="POST",
    )

    request_timeout = get_timeout_seconds() if timeout is None else timeout
    last_incomplete_read = None
    for attempt in range(get_retry_count()):
        try:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                body = response.read().decode("utf-8")
            break
        except http.client.IncompleteRead as error:
            last_incomplete_read = error
            if attempt + 1 >= get_retry_count():
                raise OpenRouterError(
                    "OpenRouter response ended before the full body was read. "
                    f"Details: {error}"
                ) from error
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise OpenRouterError(
                f"OpenRouter returned HTTP {error.code}. Details: {body}"
            ) from error
        except urllib.error.URLError as error:
            raise OpenRouterError(
                f"OpenRouter request failed. Details: {error.reason}"
            ) from error
    else:
        raise OpenRouterError(
            "OpenRouter response ended before the full body was read. "
            f"Details: {last_incomplete_read}"
        )

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise OpenRouterError("OpenRouter returned invalid JSON.") from error
