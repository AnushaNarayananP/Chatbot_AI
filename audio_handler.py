"""Audio transcription via the Gemini API.

Accepts an uploaded audio file (WAV, MP3, OGG, M4A, WEBM), base64-encodes its
contents, and sends the audio to the Gemini ``generateContent`` endpoint for
speech-to-text transcription.  The transcribed text is returned as a plain
string so the caller can feed it into the chat pipeline as a normal user
message.
"""

from __future__ import annotations

import base64
import os

from gemini_client import (
    GeminiError,
    extract_text_from_response,
    get_env_value,
    get_timeout_seconds,
    is_retryable_gemini_error,
    post_generate_content,
)


SUPPORTED_AUDIO_EXTENSIONS = {"wav", "mp3", "ogg", "m4a", "webm"}

_MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
}

_TRANSCRIPTION_PROMPT = (
    "Transcribe the following audio exactly as spoken. "
    "Return ONLY the transcription text — no commentary, no timestamps, "
    "no formatting, no markdown. If the audio is silent or unintelligible, "
    "reply with an empty string."
)

DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


def _resolve_model() -> str:
    return (
        get_env_value("GEMINI_VISION_MODEL", "").strip()
        or os.environ.get("GEMINI_TEXT_MODEL", "").strip()
        or DEFAULT_MODEL
    )


def _resolve_fallback_model(primary: str) -> str:
    fallback = (
        get_env_value("GEMINI_VISION_FALLBACK_MODEL", "").strip()
        or os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()
        or FALLBACK_MODEL
    )
    return "" if fallback == primary else fallback


def _audio_extension(filename: str) -> str:
    return (filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


def is_audio_file(filename: str) -> bool:
    """Return *True* if *filename* has a supported audio extension."""
    return _audio_extension(filename) in SUPPORTED_AUDIO_EXTENSIONS


def transcribe_audio(audio_file) -> str:
    """Transcribe an uploaded audio file to text via the Gemini API.

    Parameters
    ----------
    audio_file:
        A Streamlit ``UploadedFile`` (or any file-like object with ``.read()``
        and ``.name`` attributes).

    Returns
    -------
    str
        The transcribed text.  An empty string is returned when the audio
        could not be transcribed.

    Raises
    ------
    RuntimeError
        If the Gemini API request fails irrecoverably.
    """
    raw_bytes = audio_file.read()
    if not raw_bytes:
        raise RuntimeError("The uploaded audio file is empty.")

    ext = _audio_extension(getattr(audio_file, "name", "audio.wav"))
    mime_type = _MIME_TYPES.get(ext, "audio/wav")
    encoded = base64.standard_b64encode(raw_bytes).decode("ascii")

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": encoded}},
                    {"text": _TRANSCRIPTION_PROMPT},
                ],
            }
        ],
    }

    primary_model = _resolve_model()
    fallback_model = _resolve_fallback_model(primary_model)
    candidate_models = [primary_model]
    if fallback_model:
        candidate_models.append(fallback_model)

    timeout = get_timeout_seconds()
    last_error: Exception | None = None

    for index, model in enumerate(candidate_models):
        try:
            response = post_generate_content(model, payload, timeout=timeout)
            text = extract_text_from_response(response).strip()
            if text:
                return text

            last_error = RuntimeError(
                "Gemini returned an empty transcription for the audio."
            )
            if index == 0 and len(candidate_models) > 1:
                continue
            raise last_error

        except GeminiError as exc:
            last_error = exc
            if index == 0 and len(candidate_models) > 1 and is_retryable_gemini_error(exc):
                continue
            raise RuntimeError(str(exc)) from exc

    raise RuntimeError(str(last_error))
