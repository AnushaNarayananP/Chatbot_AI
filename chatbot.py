import json
import os
import re
import sys
import time
import unicodedata

from gemini_client import GeminiError, get_timeout_seconds as get_gemini_timeout_seconds
from gemini_client import post_generate_content
from openrouter_client import (
    OPENROUTER_ENDPOINT,
    OpenRouterError,
    format_user_facing_error,
    get_env_value,
    get_primary_timeout_seconds,
    get_timeout_seconds,
    post_chat_completion,
)
from pipeline.executor import execute_pipeline
from pipeline.models import PipelineRequest


DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_FALLBACK_MODEL = "meta-llama/llama-4-maverick"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash-lite"
DEFAULT_HISTORY_WINDOW = 8
BOT_NAME = "Avi"
SYSTEM_PROMPT = """
You are a warm, emotionally aware, casual AI companion.

Talk like a real friend having a natural conversation:
- sound relaxed, human, and approachable
- use simple everyday language instead of formal or corporate wording
- show a little personality, warmth, and emotional presence
- be encouraging, supportive, and easy to talk to
- keep replies conversational, not stiff or textbook-like
- avoid sounding like a robot, customer support agent, or encyclopedia
- do not overuse bullet points unless the user asks for them
- when the user shares something personal, respond with empathy first
- you can be playful or light when it fits, but do not be cheesy
- keep answers clear and helpful, but make them feel natural

Write like you are chatting with someone you know well:
kind, casual, emotionally intelligent, and genuine.
Only ask clarifying questions when they are actually needed.
Always reply in the exact same language and script as the user's message.
If the user writes in English, reply in English.
If the user writes in Manglish (Malayalam in English letters), reply in Manglish.
Never translate unless explicitly asked.
""".strip()

MALAYALAM_SCRIPT_RANGE = ("\u0d00", "\u0d7f")
DEVANAGARI_SCRIPT_RANGE = ("\u0900", "\u097f")
MANGLISH_HINTS = {
    "aanu",
    "alle",
    "entha",
    "enthu",
    "ente",
    "enikku",
    "njan",
    "ningal",
    "sheri",
    "vallare",
    "valare",
    "undo",
    "illa",
    "pakshe",
    "athu",
    "ivide",
    "evide",
    "veettil",
    "padikkan",
    "padikkanam",
    "sugham",
    "ishtam",
    "oru",
    "kure",
    "adhikam",
    "poyi",
    "varam",
    "cheyyam",
    "parayu",
    "thonnunnu",
}
ENGLISH_HINTS = {
    "the",
    "and",
    "is",
    "are",
    "have",
    "has",
    "i",
    "you",
    "my",
    "work",
    "homework",
    "today",
    "need",
    "help",
}


def _count_chars_in_range(text, start_char, end_char):
    return sum(start_char <= char <= end_char for char in text)


def _dominant_unicode_script(text):
    script_counts = {}
    for char in text:
        if not char.isalpha():
            continue
        try:
            script_name = unicodedata.name(char).split()[0]
        except ValueError:
            continue
        script_counts[script_name] = script_counts.get(script_name, 0) + 1

    if not script_counts:
        return None

    return max(script_counts, key=script_counts.get)


def detect_language(user_input, previous_language=None):
    text = (user_input or "").strip()
    if not text:
        return previous_language or "english"

    malayalam_chars = _count_chars_in_range(text, *MALAYALAM_SCRIPT_RANGE)
    devanagari_chars = _count_chars_in_range(text, *DEVANAGARI_SCRIPT_RANGE)
    latin_chars = sum(char.isascii() and char.isalpha() for char in text)

    if malayalam_chars:
        return "malayalam"
    if devanagari_chars:
        return "hindi"

    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    manglish_hits = sum(token in MANGLISH_HINTS for token in tokens)
    english_hits = sum(token in ENGLISH_HINTS for token in tokens)

    if latin_chars:
        if manglish_hits > english_hits:
            return "manglish"
        if english_hits > manglish_hits:
            return "english"

    dominant_script = _dominant_unicode_script(text)
    if dominant_script == "LATIN":
        if manglish_hits:
            return "manglish"
        return previous_language or "english"
    if dominant_script == "DEVANAGARI":
        return "hindi"
    if dominant_script == "MALAYALAM":
        return "malayalam"
    if dominant_script:
        return dominant_script.lower()

    return previous_language or "english"


def _extract_system_prompt(messages):
    for message in messages or []:
        if message.get("role") == "system" and message.get("content"):
            return message["content"]
    return SYSTEM_PROMPT


def build_language_instruction(messages):
    user_messages = [
        message["content"]
        for message in messages
        if message.get("role") == "user" and message.get("content")
    ]
    if not user_messages:
        return None

    previous_language = None
    if len(user_messages) > 1:
        previous_language = detect_language(user_messages[-2])

    current_language = detect_language(
        user_messages[-1],
        previous_language=previous_language,
    )

    return (
        "Language rule for this reply: respond in the same language and script as "
        f"the user's latest message. Detected language/style: {current_language}. "
        "If the latest message is mixed, follow the dominant language. "
        "If it is Manglish, reply in Manglish using English letters only. "
        "Do not translate unless the user explicitly asks."
    )


def build_text_messages(messages, max_history_messages=DEFAULT_HISTORY_WINDOW):
    system_prompt = _extract_system_prompt(messages)
    recent_messages = [
        {"role": message["role"], "content": message["content"]}
        for message in messages
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    if max_history_messages > 0:
        recent_messages = recent_messages[-max_history_messages:]

    prepared_messages = [{"role": "system", "content": system_prompt}]
    language_instruction = build_language_instruction(recent_messages)
    if language_instruction:
        prepared_messages.append({"role": "system", "content": language_instruction})
    prepared_messages.extend(recent_messages)
    return prepared_messages


def _default_user_prompt(user_prompt):
    cleaned_prompt = (user_prompt or "").strip()
    if cleaned_prompt:
        return cleaned_prompt
    return "Analyze this image."


def _format_vision_reply(vision_result):
    task = vision_result.get("task")
    structured = vision_result.get("structured", {})
    raw_text = vision_result.get("raw_text", "").strip()

    if task == "ocr":
        extracted_text = structured.get("extracted_text", "").strip()
        summary = structured.get("summary", "").strip()
        parts = []
        if summary:
            parts.append(summary)
        if extracted_text:
            parts.append(f"Extracted text:\n{extracted_text}")
        return "\n\n".join(parts).strip() or raw_text

    if task == "caption":
        summary = structured.get("summary", "").strip()
        answer = structured.get("answer", "").strip()
        if summary and answer and summary != answer:
            return f"{answer}\n\nSummary: {summary}"
        return answer or summary or raw_text

    if task == "qa":
        return structured.get("answer", "").strip() or raw_text

    parts = []
    if structured.get("summary", "").strip():
        parts.append(structured["summary"].strip())
    if structured.get("extracted_text", "").strip():
        parts.append(f"Visible text:\n{structured['extracted_text'].strip()}")
    answer = structured.get("answer", "").strip()
    if answer and answer not in parts:
        parts.append(answer)
    return "\n\n".join(part for part in parts if part).strip() or raw_text


def get_default_text_model():
    gemini_model = os.environ.get("GEMINI_TEXT_MODEL", "").strip()
    if gemini_model:
        return gemini_model

    openrouter_model = get_env_value("OPENROUTER_TEXT_MODEL", DEFAULT_MODEL)
    if openrouter_model:
        return openrouter_model

    return DEFAULT_GEMINI_MODEL if os.environ.get("GEMINI_API_KEY", "").strip() else DEFAULT_MODEL


def _resolve_gemini_model(model):
    selected = (model or "").strip()
    if selected.startswith("gemini-"):
        return selected
    return os.environ.get("GEMINI_TEXT_MODEL", "").strip() or DEFAULT_GEMINI_MODEL


def _resolve_gemini_fallback_model(primary_model):
    selected = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip() or DEFAULT_GEMINI_FALLBACK_MODEL
    if selected == primary_model:
        return ""
    return selected


def _resolve_openrouter_model(model):
    selected = (model or "").strip()
    if selected and not selected.startswith("gemini-"):
        return selected
    return get_env_value("OPENROUTER_TEXT_MODEL", DEFAULT_MODEL)


def build_gemini_payload(messages):
    system_messages = []
    contents = []
    for message in build_text_messages(messages):
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_messages.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})

    payload = {"contents": contents}
    if system_messages:
        payload["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_messages)}]
        }
    return payload


def chat_with_gemini(messages, model=None):
    selected_model = _resolve_gemini_model(model)
    payload = build_gemini_payload(messages)
    fallback_model = _resolve_gemini_fallback_model(selected_model)
    candidate_models = [selected_model]
    if fallback_model:
        candidate_models.append(fallback_model)

    last_error = None
    for index, candidate_model in enumerate(candidate_models):
        try:
            response_dict = post_generate_content(
                candidate_model,
                payload,
                timeout=get_gemini_timeout_seconds(),
            )
            candidates = response_dict.get("candidates") or []
            if not candidates:
                last_error = RuntimeError("Gemini returned an empty response for text chat.")
                if index == 0 and len(candidate_models) > 1:
                    continue
                raise last_error

            parts = candidates[0].get("content", {}).get("parts") or []
            reply = "\n".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and part.get("text")
            ).strip()
            if reply:
                return reply

            last_error = RuntimeError("Gemini returned an empty message for text chat.")
            if index == 0 and len(candidate_models) > 1:
                continue
            raise last_error
        except GeminiError as error:
            last_error = error
            is_retryable_primary_error = (
                index == 0
                and len(candidate_models) > 1
                and (
                    "HTTP 503" in str(error)
                    or '"status": "UNAVAILABLE"' in str(error)
                    or "experiencing high demand" in str(error)
                    or "timed out" in str(error).lower()
                )
            )
            if not is_retryable_primary_error:
                raise RuntimeError(str(error)) from error

    raise RuntimeError(str(last_error))


def chat_with_openrouter(messages, model=None):
    api_key = get_env_value("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY in environment.")

    selected_model = _resolve_openrouter_model(model)
    prepared_messages = build_text_messages(messages)
    fallback_model = get_env_value("OPENROUTER_TEXT_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
    candidate_models = [selected_model]
    if fallback_model and fallback_model != selected_model:
        candidate_models.append(fallback_model)

    last_error = None
    response_dict = None
    default_timeout_seconds = get_timeout_seconds()
    primary_timeout_seconds = get_primary_timeout_seconds()
    for index, candidate_model in enumerate(candidate_models):
        payload = {
            "model": candidate_model,
            "messages": prepared_messages,
        }
        request_timeout = (
            primary_timeout_seconds
            if index == 0 and len(candidate_models) > 1
            else default_timeout_seconds
        )
        try:
            response_dict = post_chat_completion(payload, timeout=request_timeout)
            choices = response_dict.get("choices") or []
            if choices:
                break
            last_error = OpenRouterError("OpenRouter returned an empty response for text chat.")
            if index == 0 and len(candidate_models) > 1:
                continue
            raise RuntimeError(str(last_error))
        except OpenRouterError as error:
            last_error = error
            is_primary_model = candidate_model == selected_model
            is_retryable_primary_error = (
                is_primary_model
                and (
                    "HTTP 429" in str(error)
                    or "timed out" in str(error).lower()
                )
                and len(candidate_models) > 1
            )
            if not is_retryable_primary_error:
                raise RuntimeError(format_user_facing_error(str(error))) from error

    if response_dict is None:
        raise RuntimeError(format_user_facing_error(str(last_error)))

    choices = response_dict.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned an empty response for text chat.")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        reply = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    else:
        reply = str(content).strip()

    if not reply:
        raise RuntimeError("OpenRouter returned an empty message for text chat.")

    return reply


def chat_with_text_provider(messages, model=None):
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_api_key:
        return chat_with_gemini(messages, model=model)

    return chat_with_openrouter(messages, model=model)


def use_mcp_orchestrator():
    return os.environ.get("ENABLE_MCP_ORCHESTRATOR", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def route_chat_request(
    user_prompt,
    uploaded_image=None,
    image_url=None,
    messages=None,
    model=DEFAULT_MODEL,
    rag_session_id=None,
):
    cleaned_prompt = _default_user_prompt(user_prompt)
    started_at = time.perf_counter()
    previous_language = None
    if messages:
        previous_user_messages = [
            message["content"]
            for message in messages
            if message.get("role") == "user" and message.get("content")
        ]
        if previous_user_messages:
            previous_language = detect_language(previous_user_messages[-1])

    detected_language = detect_language(
        cleaned_prompt,
        previous_language=previous_language,
    )

    pipeline_request = PipelineRequest(
        prompt=cleaned_prompt,
        messages=list(messages or []),
        uploaded_image=uploaded_image,
        image_url=image_url,
        model=model,
        detected_language=detected_language,
        rag_session_id=rag_session_id,
    )

    pipeline_response = None
    if use_mcp_orchestrator() and not pipeline_request.has_image and not rag_session_id:
        try:
            from mcp.orchestrator import MCPOrchestrator

            pipeline_response = MCPOrchestrator().handle(pipeline_request)
        except Exception:
            pipeline_response = None

    if pipeline_response is None:
        pipeline_response = execute_pipeline(pipeline_request)
    response_dict = pipeline_response.to_dict()
    response_dict["meta"] = {
        **response_dict.get("meta", {}),
        "detected_language": detected_language,
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
    response_dict["reply"] = format_user_facing_error(response_dict["reply"])
    return response_dict


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else get_default_text_model()

    print(f"Starting chatbot with OpenRouter model: {model}")
    print("Type 'exit' or 'quit' to stop.\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nChat ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Chat ended.")
            break

        result = route_chat_request(user_input, messages=messages, model=model)
        if not result["ok"]:
            print(f"Error: {result['reply']}")
            continue

        assistant_reply = result["reply"]
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": assistant_reply})
        print(f"{BOT_NAME}: {assistant_reply}\n")


if __name__ == "__main__":
    main()
