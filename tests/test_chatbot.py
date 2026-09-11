import json
import http.client
from unittest.mock import Mock

import pytest

import chatbot
import gemini_client
import openrouter_client
from pipeline.models import PipelineResponse


def test_detect_language_handles_supported_inputs():
    assert chatbot.detect_language("hello, how are you?") == "english"
    assert chatbot.detect_language("sugham alle") == "manglish"
    assert chatbot.detect_language("ഹലോ സുഖമാണോ") == "malayalam"
    assert chatbot.detect_language("नमस्ते आप कैसे हो") == "hindi"


def test_build_text_messages_trims_history_and_keeps_system_prompt():
    messages = [{"role": "system", "content": chatbot.SYSTEM_PROMPT}]
    for index in range(12):
        messages.append({"role": "user", "content": f"user-{index}"})
        messages.append({"role": "assistant", "content": f"assistant-{index}"})

    prepared = chatbot.build_text_messages(messages, max_history_messages=6)

    assert prepared[0]["role"] == "system"
    assert prepared[0]["content"] == chatbot.SYSTEM_PROMPT
    assert prepared[1]["role"] == "system"
    assert "Detected language/style" in prepared[1]["content"]
    assert [message["content"] for message in prepared[2:]] == [
        "user-9",
        "assistant-9",
        "user-10",
        "assistant-10",
        "user-11",
        "assistant-11",
    ]


def test_chat_with_openrouter_uses_env_model_and_headers(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_TEXT_MODEL", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("OPENROUTER_TEXT_FALLBACK_MODEL", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("OPENROUTER_SITE_URL", "http://localhost:8501")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "FriendlyBot")
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "9")

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": "Gemma reply"}},
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(openrouter_client.urllib.request, "urlopen", fake_urlopen)

    reply = chatbot.chat_with_openrouter(
        [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
    )

    assert reply == "Gemma reply"
    assert captured["url"] == chatbot.OPENROUTER_ENDPOINT
    assert captured["timeout"] == 9
    assert captured["payload"]["model"] == "google/gemma-4-31b-it:free"
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_openrouter_post_chat_completion_retries_after_incomplete_read(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = []

    class FakeResponse:
        def __init__(self, should_fail=False):
            self.should_fail = should_fail

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            if self.should_fail:
                raise http.client.IncompleteRead(b'{"choices":', 2222)
            return json.dumps(
                {"choices": [{"message": {"content": "Recovered"}}]}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append(timeout)
        return FakeResponse(should_fail=len(calls) == 1)

    monkeypatch.setattr(openrouter_client.urllib.request, "urlopen", fake_urlopen)

    result = openrouter_client.post_chat_completion(
        {"model": "test/model", "messages": []},
        timeout=5,
    )

    assert result["choices"][0]["message"]["content"] == "Recovered"
    assert calls == [5, 5]


def test_openrouter_post_chat_completion_reports_incomplete_read_after_retries(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_RETRY_COUNT", "2")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            raise http.client.IncompleteRead(b'{"choices":', 2222)

    monkeypatch.setattr(
        openrouter_client.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse(),
    )

    with pytest.raises(openrouter_client.OpenRouterError, match="full body was read"):
        openrouter_client.post_chat_completion(
            {"model": "test/model", "messages": []},
            timeout=5,
        )


def test_chat_with_openrouter_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        chatbot.chat_with_openrouter(
            [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
        )


def test_route_chat_request_text_only_uses_text_client(monkeypatch):
    monkeypatch.setattr(chatbot, "use_mcp_orchestrator", lambda: False)
    execute_mock = Mock(
        return_value=PipelineResponse(
            ok=True,
            intent="qa",
            mode="text",
            reply="Fast reply",
            tool_calls=[],
            structured_data={},
            meta={},
        )
    )
    monkeypatch.setattr(chatbot, "execute_pipeline", execute_mock)

    result = chatbot.route_chat_request(
        "Hello there",
        messages=[{"role": "system", "content": chatbot.SYSTEM_PROMPT}],
        model="google/gemma-4-31b-it:free",
    )

    assert result["ok"] is True
    assert result["mode"] == "text"
    assert result["reply"] == "Fast reply"
    assert result["intent"] == "qa"
    execute_mock.assert_called_once()


def test_route_chat_request_can_use_mcp_orchestrator_when_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_MCP_ORCHESTRATOR", "true")
    execute_mock = Mock(side_effect=AssertionError("legacy pipeline should not run"))
    monkeypatch.setattr(chatbot, "execute_pipeline", execute_mock)

    class FakeOrchestrator:
        def handle(self, request):
            return PipelineResponse(
                ok=True,
                intent="qa",
                mode="text",
                reply=f"MCP answered: {request.prompt}",
                tool_calls=[],
                structured_data={},
                meta={
                    "mcp_orchestrated": True,
                    "tool_selected": "answer_question",
                },
            )

    monkeypatch.setattr("mcp.orchestrator.MCPOrchestrator", FakeOrchestrator)

    result = chatbot.route_chat_request(
        "What is MCP?",
        messages=[{"role": "system", "content": chatbot.SYSTEM_PROMPT}],
    )

    assert result["ok"] is True
    assert result["reply"] == "MCP answered: What is MCP?"
    assert result["meta"]["mcp_orchestrated"] is True
    assert result["meta"]["tool_selected"] == "answer_question"
    execute_mock.assert_not_called()


def test_route_chat_request_keeps_image_requests_on_existing_pipeline_when_mcp_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_MCP_ORCHESTRATOR", "true")
    orchestrator_calls = []

    class FakeOrchestrator:
        def __init__(self):
            orchestrator_calls.append("created")

        def handle(self, request):
            raise AssertionError("image requests should not enter Phase 4 MCP orchestration")

    monkeypatch.setattr("mcp.orchestrator.MCPOrchestrator", FakeOrchestrator)
    execute_mock = Mock(
        return_value=PipelineResponse(
            ok=True,
            intent="ocr",
            mode="vision",
            reply="Existing image pipeline",
            tool_calls=[],
            structured_data={},
            meta={},
        )
    )
    monkeypatch.setattr(chatbot, "execute_pipeline", execute_mock)

    result = chatbot.route_chat_request(
        "Store this invoice",
        uploaded_image=object(),
        messages=[{"role": "system", "content": chatbot.SYSTEM_PROMPT}],
    )

    assert result["ok"] is True
    assert result["reply"] == "Existing image pipeline"
    execute_mock.assert_called_once()
    assert orchestrator_calls == []


def test_chat_with_gemini_uses_env_model_and_parses_reply(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash-lite")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "11")

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "Gemini reply"},
                                ]
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(gemini_client.urllib.request, "urlopen", fake_urlopen)

    reply = chatbot.chat_with_gemini(
        [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
    )

    assert reply == "Gemini reply"
    assert "gemini-2.0-flash-lite:generateContent" in captured["url"]
    assert "key=gemini-test-key" in captured["url"]
    assert captured["timeout"] == 11
    assert captured["payload"]["contents"][-1]["parts"][0]["text"] == "Hello"


def test_chat_with_text_provider_raises_gemini_error_when_gemini_is_configured(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    gemini_mock = Mock(side_effect=RuntimeError("Gemini unavailable"))
    openrouter_mock = Mock(return_value="OpenRouter fallback reply")
    monkeypatch.setattr(chatbot, "chat_with_gemini", gemini_mock)
    monkeypatch.setattr(chatbot, "chat_with_openrouter", openrouter_mock)

    with pytest.raises(RuntimeError, match="Gemini unavailable"):
        chatbot.chat_with_text_provider(
            [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
        )

    gemini_mock.assert_called_once()
    openrouter_mock.assert_not_called()


def test_chat_with_gemini_falls_back_to_secondary_gemini_model_on_transient_503(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

    calls = []

    def fake_post_generate_content(model, payload, timeout=None):
        calls.append(model)
        if model == "gemini-2.5-flash-lite":
            raise chatbot.GeminiError(
                'Gemini returned HTTP 503. Details: { "error": { "code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE" } }'
            )
        return {
            "candidates": [
                {"content": {"parts": [{"text": "Gemini fallback reply"}]}}
            ]
        }

    monkeypatch.setattr(chatbot, "post_generate_content", fake_post_generate_content)

    reply = chatbot.chat_with_gemini(
        [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
    )

    assert reply == "Gemini fallback reply"
    assert calls == ["gemini-2.5-flash-lite", "gemini-2.5-flash"]


def test_chat_with_openrouter_falls_back_after_rate_limit(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_TEXT_MODEL", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("OPENROUTER_TEXT_FALLBACK_MODEL", "openrouter/free")

    calls = []

    def fake_post_chat_completion(payload, timeout=None):
        calls.append(payload["model"])
        if payload["model"] == "google/gemma-4-31b-it:free":
            raise chatbot.OpenRouterError(
                "OpenRouter returned HTTP 429. Details: "
                '{"error":{"message":"Provider returned error","code":429,'
                '"metadata":{"raw":"google/gemma-4-31b-it:free is temporarily rate-limited upstream.",'
                '"provider_name":"Google AI Studio"}}}'
            )
        return {"choices": [{"message": {"content": "Fallback reply"}}]}

    monkeypatch.setattr(chatbot, "post_chat_completion", fake_post_chat_completion)

    reply = chatbot.chat_with_openrouter(
        [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
    )

    assert reply == "Fallback reply"
    assert calls == [
        "google/gemma-4-31b-it:free",
        "openrouter/free",
    ]


def test_chat_with_openrouter_falls_back_after_primary_timeout(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_TEXT_MODEL", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("OPENROUTER_TEXT_FALLBACK_MODEL", "openrouter/free")
    monkeypatch.setenv("OPENROUTER_PRIMARY_TIMEOUT_SECONDS", "6")
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "20")

    calls = []
    timeouts = []

    def fake_post_chat_completion(payload, timeout=None):
        calls.append(payload["model"])
        timeouts.append(timeout)
        if payload["model"] == "google/gemma-4-31b-it:free":
            raise chatbot.OpenRouterError("OpenRouter request failed. Details: timed out")
        return {"choices": [{"message": {"content": "Fast fallback reply"}}]}

    monkeypatch.setattr(chatbot, "post_chat_completion", fake_post_chat_completion)

    reply = chatbot.chat_with_openrouter(
        [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
    )

    assert reply == "Fast fallback reply"
    assert calls == ["google/gemma-4-31b-it:free", "openrouter/free"]
    assert timeouts == [6, 20]


def test_chat_with_openrouter_falls_back_after_empty_primary_response(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_TEXT_MODEL", "openrouter/free")
    monkeypatch.setenv("OPENROUTER_TEXT_FALLBACK_MODEL", "meta-llama/llama-3.2-3b-instruct:free")

    calls = []

    def fake_post_chat_completion(payload, timeout=None):
        calls.append(payload["model"])
        if payload["model"] == "openrouter/free":
            return {"choices": []}
        return {"choices": [{"message": {"content": "Recovered reply"}}]}

    monkeypatch.setattr(chatbot, "post_chat_completion", fake_post_chat_completion)

    reply = chatbot.chat_with_openrouter(
        [{"role": "system", "content": chatbot.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
    )

    assert reply == "Recovered reply"
    assert calls == ["openrouter/free", "meta-llama/llama-3.2-3b-instruct:free"]


def test_route_chat_request_returns_clean_rate_limit_message(monkeypatch):
    monkeypatch.setattr(
        chatbot,
        "chat_with_text_provider",
        Mock(
            side_effect=RuntimeError(
                "OpenRouter returned HTTP 429. Details: "
                '{"error":{"message":"Provider returned error","code":429,'
                '"metadata":{"raw":"google/gemma-4-31b-it:free is temporarily rate-limited upstream.",'
                '"provider_name":"Google AI Studio"}}}'
            )
        ),
    )

    result = chatbot.route_chat_request(
        "Hello there",
        messages=[{"role": "system", "content": chatbot.SYSTEM_PROMPT}],
        model="google/gemma-4-31b-it:free",
    )

    assert result["ok"] is False
    assert result["mode"] == "text"
    assert "temporarily rate-limited" in result["reply"]
    assert "Please retry shortly" in result["reply"]
    assert "HTTP 429" not in result["reply"]


def test_route_chat_request_returns_clean_model_not_found_message(monkeypatch):
    monkeypatch.setattr(
        chatbot,
        "chat_with_text_provider",
        Mock(
            side_effect=RuntimeError(
                'OpenRouter returned HTTP 404. Details: {"error":{"message":"No endpoints found for bad/model:free.","code":404}}'
            )
        ),
    )

    result = chatbot.route_chat_request(
        "Hello there",
        messages=[{"role": "system", "content": chatbot.SYSTEM_PROMPT}],
        model="bad/model:free",
    )

    assert result["ok"] is False
    assert result["mode"] == "text"
    assert "isn't available" in result["reply"]
    assert "switch to another model" in result["reply"]
    assert "HTTP 404" not in result["reply"]
