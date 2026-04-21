import json
import re
import sys
import urllib.error
import urllib.request
import unicodedata


OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3.2"
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
"""

MALAYALAM_SCRIPT_RANGE = ("\u0d00", "\u0d7f")
DEVANAGARI_SCRIPT_RANGE = ("\u0900", "\u097f")
MANGlish_HINTS = {
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
    text = user_input.strip()
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
    manglish_hits = sum(token in MANGlish_HINTS for token in tokens)
    english_hits = sum(
        token in {
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
        for token in tokens
    )

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


def build_language_instruction(messages):
    user_messages = [message["content"] for message in messages if message["role"] == "user"]
    if not user_messages:
        return None

    previous_language = None
    if len(user_messages) > 1:
        previous_language = detect_language(user_messages[-2])

    current_language = detect_language(user_messages[-1], previous_language=previous_language)

    return (
        "Language rule for this reply: respond in the same language and script as "
        f"the user's latest message. Detected language/style: {current_language}. "
        "If the latest message is mixed, follow the dominant language. "
        "If it is Manglish, reply in Manglish using English letters only. "
        "Do not translate unless the user explicitly asks."
    )


def prepare_messages_for_model(messages):
    language_instruction = build_language_instruction(messages)
    if not language_instruction:
        return messages

    prepared_messages = list(messages)
    insert_at = 1 if prepared_messages and prepared_messages[0]["role"] == "system" else 0
    prepared_messages.insert(
        insert_at,
        {"role": "system", "content": language_instruction},
    )
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
    if structured.get("answer", "").strip() and structured["answer"].strip() not in parts:
        parts.append(structured["answer"].strip())
    return "\n\n".join(part for part in parts if part).strip() or raw_text


def route_chat_request(
    user_prompt,
    uploaded_image=None,
    image_url=None,
    messages=None,
    model=DEFAULT_MODEL,
):
    cleaned_prompt = _default_user_prompt(user_prompt)
    previous_language = None
    if messages:
        previous_user_messages = [
            message["content"]
            for message in messages
            if message.get("role") == "user" and message.get("content")
        ]
        if previous_user_messages:
            previous_language = detect_language(previous_user_messages[-1])

    detected_language = detect_language(cleaned_prompt, previous_language=previous_language)

    if uploaded_image is not None or (image_url or "").strip():
        from vision_handler import (
            encode_uploaded_image_to_data_url,
            run_vision_action,
            validate_image_url,
        )

        try:
            image_data_url = (
                encode_uploaded_image_to_data_url(uploaded_image)
                if uploaded_image is not None
                else None
            )
            validated_image_url = (
                None if uploaded_image is not None else validate_image_url(image_url)
            )
        except ValueError as error:
            return {
                "ok": False,
                "mode": "vision",
                "reply": str(error),
                "meta": {
                    "task": None,
                    "source_type": "upload" if uploaded_image is not None else "url",
                    "detected_language": detected_language,
                },
            }

        vision_result = run_vision_action(
            cleaned_prompt,
            image_data_url=image_data_url,
            image_url=validated_image_url,
            detected_language=detected_language,
        )
        if not vision_result.get("ok"):
            return {
                "ok": False,
                "mode": "vision",
                "reply": vision_result.get(
                    "error",
                    "I couldn't analyze that image right now. Please try again.",
                ),
                "meta": {
                    "task": vision_result.get("task"),
                    "source_type": "upload" if uploaded_image is not None else "url",
                    "detected_language": detected_language,
                },
            }

        return {
            "ok": True,
            "mode": "vision",
            "reply": _format_vision_reply(vision_result),
            "meta": {
                "task": vision_result.get("task"),
                "source_type": "upload" if uploaded_image is not None else "url",
                "detected_language": detected_language,
                "structured": vision_result.get("structured", {}),
            },
        }

    if messages is not None:
        active_messages = list(messages) + [{"role": "user", "content": cleaned_prompt}]
    else:
        active_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": cleaned_prompt},
        ]

    try:
        reply = chat_with_ollama(active_messages, model=model)
    except RuntimeError as error:
        return {
            "ok": False,
            "mode": "text",
            "reply": str(error),
            "meta": {"detected_language": detected_language},
        }

    return {
        "ok": True,
        "mode": "text",
        "reply": reply,
        "meta": {"detected_language": detected_language},
    }


def chat_with_ollama(messages, model=DEFAULT_MODEL):
    prepared_messages = prepare_messages_for_model(messages)
    payload = {
        "model": model,
        "messages": prepared_messages,
        "stream": False,
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["message"]["content"].strip()
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama returned HTTP {error.code}. Details: {error_body}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            "Could not connect to Ollama. Make sure Ollama is installed and running "
            "on http://localhost:11434."
        ) from error


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL

    print(f"Starting chatbot with Ollama model: {model}")
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
            print(f"Tip: run 'ollama pull {model}' if the model is not available.")
            continue

        assistant_reply = result["reply"]
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": assistant_reply})
        print(f"{BOT_NAME}: {assistant_reply}\n")


if __name__ == "__main__":
    main()
