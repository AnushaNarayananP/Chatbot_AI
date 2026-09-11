"""Quick diagnostic: test Gemini vision API with a sample image."""
import base64
import json
import os
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).with_name(".env")
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from gemini_client import post_generate_content, build_inline_image_part, extract_text_from_response

# Use a small test: create a simple text image or use a URL
# Let's test with the same safety settings
def test_with_safety_settings():
    # Create a tiny test image with text (1x1 white pixel)
    import struct, zlib
    def make_png(w=2, h=2):
        raw = b""
        for _ in range(h):
            raw += b"\x00" + b"\xff\xff\xff" * w
        def chunk(ctype, data):
            c = ctype + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        return (b"\x89PNG\r\n\x1a\n" +
                chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw)) +
                chunk(b"IEND", b""))
    
    png_bytes = make_png()
    encoded = base64.b64encode(png_bytes).decode("utf-8")
    data_url = f"data:image/png;base64,{encoded}"
    
    model = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    
    # Test 1: Without safety settings
    print(f"=== Test 1: Model={model}, NO safety settings ===")
    payload1 = {
        "contents": [{"role": "user", "parts": [
            {"text": "What do you see in this image? Reply with any text."},
            build_inline_image_part(data_url),
        ]}]
    }
    try:
        resp1 = post_generate_content(model, payload1, timeout=30)
        text1 = extract_text_from_response(resp1)
        print(f"Response text length: {len(text1)}")
        print(f"Text: {text1[:200]}")
        print(f"Candidates count: {len(resp1.get('candidates', []))}")
        if resp1.get("promptFeedback"):
            print(f"promptFeedback: {json.dumps(resp1['promptFeedback'], indent=2)}")
        if resp1.get("candidates"):
            c = resp1["candidates"][0]
            print(f"finishReason: {c.get('finishReason')}")
            if c.get("safetyRatings"):
                print(f"safetyRatings: {json.dumps(c['safetyRatings'], indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 2: With safety settings (including CIVIC_INTEGRITY)
    print(f"\n=== Test 2: Model={model}, WITH all safety settings ===")
    payload2 = {
        "contents": [{"role": "user", "parts": [
            {"text": "What do you see in this image? Reply with any text."},
            build_inline_image_part(data_url),
        ]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
        ],
    }
    try:
        resp2 = post_generate_content(model, payload2, timeout=30)
        text2 = extract_text_from_response(resp2)
        print(f"Response text length: {len(text2)}")
        print(f"Text: {text2[:200]}")
        print(f"Candidates count: {len(resp2.get('candidates', []))}")
        if resp2.get("promptFeedback"):
            print(f"promptFeedback: {json.dumps(resp2['promptFeedback'], indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 3: Without CIVIC_INTEGRITY
    print(f"\n=== Test 3: Model={model}, WITHOUT CIVIC_INTEGRITY ===")
    payload3 = {
        "contents": [{"role": "user", "parts": [
            {"text": "What do you see in this image? Reply with any text."},
            build_inline_image_part(data_url),
        ]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }
    try:
        resp3 = post_generate_content(model, payload3, timeout=30)
        text3 = extract_text_from_response(resp3)
        print(f"Response text length: {len(text3)}")
        print(f"Text: {text3[:200]}")
        print(f"Candidates count: {len(resp3.get('candidates', []))}")
        if resp3.get("promptFeedback"):
            print(f"promptFeedback: {json.dumps(resp3['promptFeedback'], indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_with_safety_settings()
