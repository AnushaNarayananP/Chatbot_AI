# FriendlyBot (Avi)

An AI-powered document intelligence chatbot that combines conversational Q&A with automated invoice processing, OCR, translation, and mock ERP integration — built with Python, Streamlit, Google Gemini, and OpenRouter.

## Features

- **Multi-provider LLM routing** — Gemini (primary) + OpenRouter (fallback) with automatic model failover
- **OCR / Vision processing** — Extract text from images via Gemini Vision and OpenRouter vision models
- **Invoice data extraction** — Structured JSON extraction with confidence scoring, GST breakdown, and validation
- **Duplicate detection** — Strong (invoice number match) and fuzzy (vendor + date + total) duplicate detection
- **Mock ERP integration** — End-to-end invoice processing pipeline: OCR → Extract → Store → ERP Push
- **Translation** — Translate text to any language via LLM
- **Language detection** — Automatic detection of English, Hindi, Malayalam, and Manglish with language-matched replies
- **MCP orchestrator** — Experimental Model Context Protocol layer with LLM-based tool selection

## Quick Start

### Prerequisites

- Python 3.12+
- API keys for [Google Gemini](https://aistudio.google.com/apikey) and/or [OpenRouter](https://openrouter.ai/settings/keys)

### Setup

```bash
# Clone the repository
git clone https://github.com/AnushaNarayananP/Chatbot_AI.git
cd chatbot

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys
```

### Run

```bash
streamlit run user_interface.py
```

The app will open at [http://localhost:8501](http://localhost:8501).

### Run Tests

```bash
pytest tests/ -v --tb=short
```

## How to Use — Tool Trigger Guide

The chatbot uses **keyword matching** on your prompt + whether an image is present to determine which tools to run.

### Keyword Cheat Sheet

| To Trigger...          | Use These Keywords                                                        |
|------------------------|---------------------------------------------------------------------------|
| **OCR**                | `extract text`, `read this`, `ocr`, `what is written`, `scan this` + image |
| **Invoice Extraction** | `extract data`, `invoice`, `receipt`, `bill`, `amount`, `vendor` + image   |
| **Translation**        | `translate` (+ optionally `to <language>`)                                 |
| **Q&A**                | Any normal question (no special keywords)                                  |
| **Store**              | `store`, `save`, `persist`, `process and store`, `archive`                 |
| **ERP Push**           | Automatic after successful store with an invoice image                      |

### Example Inputs

| Input                                          | What Happens                                              |
|------------------------------------------------|-----------------------------------------------------------|
| `What is machine learning?`                    | Q&A — answers using the LLM                               |
| `Translate this to Hindi`                      | Translation — translates text to Hindi                     |
| *(upload image, leave prompt empty)*           | OCR — extracts all readable text                           |
| `Extract data from this invoice` + image       | Invoice extraction → store → ERP push                      |
| `Store this invoice` + image                   | Full workflow: OCR → extract → store → ERP push            |
| `Translate this image to Malayalam` + image    | OCR first, then translates extracted text                   |

### Tool Execution Chains

```
Image uploaded?
├── Yes → OCR runs first, then:
│   ├── Translation intent    → translate_text
│   ├── Data Extraction       → extract_invoice → store → ERP push
│   ├── Workflow Trigger      → extract_invoice → store → ERP push
│   └── Q&A                   → answer_question
└── No →
    ├── Translation intent    → translate_text
    ├── Workflow Trigger      → store_data
    ├── Summarization         → answer_question
    └── Q&A (default)         → answer_question
```

## Project Structure

```
chatbot/
├── chatbot.py                # Core router, LLM chat, language detection
├── user_interface.py         # Streamlit web UI
├── gemini_client.py          # Gemini API client
├── openrouter_client.py      # OpenRouter API client
├── vision_handler.py         # OpenRouter vision pipeline
├── pipeline/
│   ├── classifier.py         # Intent classification (keyword matching)
│   ├── executor.py           # Tool chain execution engine
│   ├── models.py             # Dataclasses (PipelineRequest, PipelineResponse, etc.)
│   ├── memory.py             # Conversation persistence
│   └── registry.py           # Tool function registry
├── providers/
│   └── llm_router.py         # JSON generation via LLM
├── tools/
│   ├── vision_tools.py       # OCR + structured data parsing
│   ├── invoice_tools.py      # Invoice extraction + validation + confidence
│   ├── storage_tools.py      # Invoice DB CRUD + duplicate detection
│   ├── text_tools.py         # Translation, Q&A, summarization
│   └── erp_tools.py          # Mock ERP submission
├── mcp/
│   ├── discovery.py          # MCP tool discovery
│   ├── orchestrator.py       # MCP request handling
│   ├── selector.py           # LLM-driven tool selection
│   └── registry.py           # Tool metadata registry
└── tests/                    # 11 test files, ~4,800 LOC
```

## Configuration

All configuration is managed via `.env`. See [`.env.example`](.env.example) for all available keys.

| Key | Description | Default |
|-----|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | *(required)* |
| `OPENROUTER_API_KEY` | OpenRouter API key | *(required)* |
| `USE_GEMINI_VISION` | Use Gemini for vision/OCR | `true` |
| `GEMINI_TEXT_MODEL` | Primary Gemini text model | `gemini-2.5-flash` |
| `ENABLE_MCP_ORCHESTRATOR` | Enable MCP tool selection | `true` |
| `ALLOW_SAMPLE_INVOICES` | Allow template/sample invoices | `true` |

## License

MIT
