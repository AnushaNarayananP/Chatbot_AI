import vision_handler
from openrouter_client import OpenRouterError
from vision_handler import (
    build_vision_instruction,
    call_openrouter_vision,
    detect_vision_task,
    parse_vision_response,
)


def test_detect_vision_task_treats_store_data_as_ocr():
    assert detect_vision_task("store data") == "ocr"
    assert detect_vision_task("save invoice details") == "ocr"


def test_invoice_ocr_instruction_requests_common_invoice_json():
    instruction = build_vision_instruction(
        "store data from this invoice",
        detected_language="english",
        task="ocr",
    )

    assert '"invoice_id"' in instruction
    assert '"items"' in instruction
    assert "Do not use address, PAN, GSTIN" in instruction
    assert "Transcribe the invoice item table rows" in instruction
    assert "Name of Product / Service" in instruction


def test_parse_vision_response_treats_none_content_as_empty():
    parsed = parse_vision_response(
        {
            "ok": True,
            "response": {"choices": [{"message": {"content": None}}]},
        }
    )

    assert parsed["ok"] is False
    assert parsed["raw_text"] == ""
    assert parsed["error"] == "The vision model returned no readable content."


def test_call_openrouter_vision_uses_qianfan_ocr_by_default(monkeypatch):
    captured = {}

    def fake_post_chat_completion(payload):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "Invoice No. GST-3425-26"}}]}

    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    monkeypatch.setattr(vision_handler, "post_chat_completion", fake_post_chat_completion)

    result = call_openrouter_vision("read this", image_data_url="data:image/png;base64,abc")

    assert result["ok"] is True
    assert result["model"] == "baidu/qianfan-ocr-fast:free"
    assert captured["payload"]["model"] == "baidu/qianfan-ocr-fast:free"


def test_call_openrouter_vision_falls_back_after_rate_limit(monkeypatch):
    calls = []

    def fake_post_chat_completion(payload):
        calls.append(payload["model"])
        if payload["model"] == "baidu/qianfan-ocr-fast:free":
            raise OpenRouterError(
                'OpenRouter returned HTTP 429. Details: {"error":{"code":429,'
                '"metadata":{"provider_name":"Baidu","raw":"temporarily rate-limited upstream"}}}'
            )
        return {"choices": [{"message": {"content": "Invoice No. GST-3425-26"}}]}

    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_VISION_FALLBACK_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
    monkeypatch.setattr(vision_handler, "post_chat_completion", fake_post_chat_completion)

    result = call_openrouter_vision("read this", image_data_url="data:image/png;base64,abc")

    assert result["ok"] is True
    assert result["model"] == "nvidia/nemotron-nano-12b-v2-vl:free"
    assert result["fallback_from"] == "baidu/qianfan-ocr-fast:free"
    assert calls == [
        "baidu/qianfan-ocr-fast:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
    ]


def test_call_openrouter_vision_falls_back_after_empty_choices(monkeypatch):
    calls = []

    def fake_post_chat_completion(payload):
        calls.append(payload["model"])
        if payload["model"] == "baidu/qianfan-ocr-fast:free":
            return {"choices": []}
        return {"choices": [{"message": {"content": "Invoice No. GST-3425-26"}}]}

    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_VISION_FALLBACK_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
    monkeypatch.setattr(vision_handler, "post_chat_completion", fake_post_chat_completion)

    result = call_openrouter_vision("read this", image_data_url="data:image/png;base64,abc")

    assert result["ok"] is True
    assert result["model"] == "nvidia/nemotron-nano-12b-v2-vl:free"
    assert result["fallback_from"] == "baidu/qianfan-ocr-fast:free"
    assert calls == [
        "baidu/qianfan-ocr-fast:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
    ]


def test_call_openrouter_vision_falls_back_after_empty_content(monkeypatch):
    calls = []

    def fake_post_chat_completion(payload):
        calls.append(payload["model"])
        if payload["model"] == "baidu/qianfan-ocr-fast:free":
            return {"choices": [{"message": {"content": ""}}]}
        return {"choices": [{"message": {"content": "Invoice No. GST-3425-26"}}]}

    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_VISION_FALLBACK_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
    monkeypatch.setattr(vision_handler, "post_chat_completion", fake_post_chat_completion)

    result = call_openrouter_vision("read this", image_data_url="data:image/png;base64,abc")

    assert result["ok"] is True
    assert result["model"] == "nvidia/nemotron-nano-12b-v2-vl:free"
    assert result["fallback_from"] == "baidu/qianfan-ocr-fast:free"
    assert calls == [
        "baidu/qianfan-ocr-fast:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
    ]


def test_call_openrouter_vision_returns_clear_error_when_all_models_are_empty(monkeypatch):
    calls = []

    def fake_post_chat_completion(payload):
        calls.append(payload["model"])
        return {"choices": []}

    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_VISION_FALLBACK_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
    monkeypatch.setattr(vision_handler, "post_chat_completion", fake_post_chat_completion)

    result = call_openrouter_vision("read this", image_data_url="data:image/png;base64,abc")

    assert result == {
        "ok": False,
        "error": (
            "The OCR model returned no readable text. Try Gemini vision, "
            "a clearer image, or another vision model."
        ),
    }
    assert calls == [
        "baidu/qianfan-ocr-fast:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
    ]


def test_call_openrouter_vision_formats_dns_failure(monkeypatch):
    def fake_post_chat_completion(payload):
        raise OpenRouterError("OpenRouter request failed. Details: [Errno 11001] getaddrinfo failed")

    monkeypatch.setattr(vision_handler, "post_chat_completion", fake_post_chat_completion)

    result = call_openrouter_vision("read this", image_data_url="data:image/png;base64,abc")

    assert result["ok"] is False
    assert result["error"] == (
        "Could not reach OpenRouter. Check your internet connection, DNS/VPN/proxy settings, "
        "or try again later."
    )
