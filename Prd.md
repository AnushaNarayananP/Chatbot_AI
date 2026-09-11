# FriendlyBot (Avi) — Product Requirements Document

## 1. Product Overview

**Product Name:** FriendlyBot (Avi)  
**Type:** AI-Powered Document Intelligence Chatbot  
**Platform:** Web (Streamlit)  
**Language:** Python 3.12+  

FriendlyBot is an AI-powered conversational assistant that combines friendly, emotionally aware chat with automated document processing. It handles invoice OCR, structured data extraction, translation, and mock ERP integration — all from a single chat interface.

---

## 2. Current Feature Set (Implemented ✅)

### 2.1 Conversational AI
- **Multi-provider LLM routing** — Google Gemini (primary) with OpenRouter (fallback) and automatic model failover
- **Warm, emotionally aware personality** — Casual, supportive tone ("Avi" persona) that adapts to user mood
- **Conversation memory** — Persistent chat history stored in `memory_store.json`
- **Configurable history window** — Adjustable context window (default: 8 messages)

### 2.2 Language Intelligence
- **Automatic language detection** — English, Hindi (Devanagari), Malayalam (script), and Manglish (Malayalam in Latin script)
- **Language-matched replies** — Bot responds in the same language/script as the user
- **Translation** — On-demand translation to any language via LLM with `translate` keyword trigger

### 2.3 Vision / OCR
- **Image upload & URL support** — Upload images directly or provide image URLs
- **Dual vision backend** — Gemini Vision (preferred) and OpenRouter vision models
- **Image preprocessing** — EXIF correction, cropping, resizing, contrast and sharpness enhancement via Pillow/PIL
- **Base64 data URL encoding** — Inline image payloads for vision API calls
- **OCR debug logging** — Full OCR output saved to `ocr_debug_latest.txt` for troubleshooting

### 2.4 Invoice Processing Pipeline
- **Structured JSON extraction** — Vendor, invoice number, date, currency, line items, subtotal, tax, total
- **Confidence scoring** — Extraction quality metrics per invoice
- **GST breakdown** — Tax component parsing for Indian invoices
- **Template/sample detection** — Blocks placeholder invoices ("Brand Name", "Lorem Ipsum", etc.)
- **Duplicate detection** — Strong (invoice number match) and fuzzy (vendor + date + total) duplicate checks
- **Auto-incrementing IDs** — `INV_10001`, `INV_10002`, etc.
- **Validation with clear reasons** — Returns `validation_reason` when invoices are rejected

### 2.5 Storage & ERP
- **JSON file database** — Invoice records in `invoice_database.json`
- **Mock ERP integration** — Simulated ERP push to `mock_erp_submissions.json`
- **End-to-end pipeline** — OCR → Extract → Validate → Store → ERP Push (fully automated)
- **Invoice & purchase tables** — Streamlit dataframe display of stored records

### 2.6 Pipeline Architecture
- **Rule-based intent classifier** — Keyword matching for OCR, translation, extraction, summarization, workflow, Q&A
- **Tool registry** — 6 registered tools: `extract_text_from_image`, `extract_invoice_data`, `translate_text`, `answer_question`, `store_data`, `push_invoice_to_erp`
- **Pipeline executor** — Deterministic tool chain execution based on intent + image presence
- **MCP orchestrator** — Experimental Model Context Protocol layer with LLM-based tool selection and optional remote tool discovery

### 2.7 UI (Streamlit)
- **Chat interface** — Message bubbles, image display, status indicators
- **Custom CSS styling** — Injected HTML/CSS for branded look (dark theme, custom composer, top bar)
- **Invoice database viewer** — Tabular display of all stored invoices and purchase items
- **File uploader** — Image upload widget in chat composer
- **Online status indicator** — Real-time bot availability display

### 2.8 Testing
- **11 test files** — ~4,800 lines of test code
- **Coverage areas** — Chatbot routing, pipeline behavior, storage tools, vision handler, vision tools, MCP discovery/orchestrator/selector, invoice extraction, ERP tools, UI helpers

---

## 3. Upcoming Features (Planned 🚧)

### 3.1 Authentication & User Management
| Item | Description | Priority |
|------|-------------|----------|
| User login/signup | Basic authentication system (email + password or OAuth) | High |
| Session management | Per-user chat sessions and invoice databases | High |
| Role-based access | Admin vs. standard user permissions for ERP actions | Medium |

### 3.2 Database Migration (JSON → SQL)
| Item | Description | Priority |
|------|-------------|----------|
| SQLite/PostgreSQL migration | Replace JSON file storage with a proper database | High |
| Schema design | Normalized tables for invoices, line items, users, sessions | High |
| Data migration script | One-time migration from existing JSON files | Medium |
| Connection pooling | Efficient database connections for concurrent users | Low |

### 3.3 Real ERP Integration
| Item | Description | Priority |
|------|-------------|----------|
| ERP API connector | Replace mock ERP with a real API integration (e.g., Tally, Zoho, SAP) | High |
| Webhook support | Receive push notifications from ERP on invoice status changes | Medium |
| Retry & error handling | Robust retry logic for failed ERP submissions | Medium |
| Audit trail | Log every ERP submission attempt with timestamps and status | Medium |

### 3.4 Advanced Document Processing
| Item | Description | Priority |
|------|-------------|----------|
| Multi-page document support | Handle PDFs and multi-page scanned invoices | High |
| Batch upload | Process multiple invoices in a single upload | High |
| Receipt support | Extend extraction to non-invoice receipts (retail, travel, etc.) | Medium |
| Handwritten text OCR | Improved OCR for handwritten notes and annotations | Medium |
| Document type classification | Auto-detect document type (invoice, receipt, purchase order, etc.) | Low |

### 3.5 RAG (Retrieval-Augmented Generation)
| Item | Description | Priority |
|------|-------------|----------|
| Vector database integration | Store document embeddings for semantic search (e.g., ChromaDB, Pinecone) | High |
| Document chunking | Split large documents into retrievable chunks | High |
| Contextual Q&A | Answer questions about previously uploaded invoices using RAG | Medium |
| Reranking | Improve retrieval quality with cross-encoder reranking | Low |

### 3.6 Analytics & Dashboard
| Item | Description | Priority |
|------|-------------|----------|
| Spending dashboard | Visual charts of invoice totals by vendor, month, category | High |
| Duplicate report | Summary of detected duplicates and rejection reasons | Medium |
| Usage analytics | Track API calls, response times, model usage per provider | Medium |
| Export to CSV/Excel | Download invoice data in spreadsheet formats | Medium |

### 3.7 Deployment & Infrastructure
| Item | Description | Priority |
|------|-------------|----------|
| Docker containerization | Dockerfile + docker-compose for reproducible deployments | High |
| Cloud deployment | Deploy to Streamlit Cloud, Render, AWS, or GCP | High |
| Environment configuration | Separate dev/staging/production configs | Medium |
| CI/CD pipeline | GitHub Actions for automated testing and deployment | Medium |
| Health monitoring | Uptime checks, error alerting, and performance monitoring | Low |

### 3.8 Enhanced Conversational Features
| Item | Description | Priority |
|------|-------------|----------|
| Streaming responses | Token-by-token streaming for faster perceived response times | High |
| Voice input/output | Speech-to-text input and text-to-speech responses | Medium |
| Multi-turn context for tools | Carry tool results across conversation turns | Medium |
| Conversation export | Download/share chat transcripts | Low |
| Typing indicators | Show "Avi is typing..." animations during processing | Low |

### 3.9 Improved Intent Classification
| Item | Description | Priority |
|------|-------------|----------|
| LLM-based classifier | Replace keyword matching with LLM-driven intent classification | High |
| Confidence thresholds | Fallback to user confirmation when intent confidence is low | Medium |
| Multi-intent support | Handle prompts with multiple intents (e.g., "extract and translate this invoice") | Medium |
| Custom intent registration | Allow users/admins to define new intents via config | Low |

### 3.10 Security & Compliance
| Item | Description | Priority |
|------|-------------|----------|
| API key vault | Store API keys in a secure vault instead of `.env` files | High |
| Data encryption at rest | Encrypt stored invoice data and personal information | Medium |
| GDPR compliance | Data deletion requests, data export, consent tracking | Medium |
| Rate limiting | Prevent abuse of LLM API calls | Medium |
| Input sanitization | Guard against prompt injection and malicious inputs | Medium |

---

## 4. Technical Debt & Improvements

| Item | Description | Priority |
|------|-------------|----------|
| Clean up pytest cache dirs | Remove ~300+ orphaned `pytest-cache-files-*` directories | High |
| Add `pyproject.toml` | Modern Python project configuration replacing/augmenting `requirements.txt` | Medium |
| Type hints coverage | Add comprehensive type annotations across all modules | Medium |
| Logging framework | Replace print/debug statements with structured logging (e.g., `logging` module) | Medium |
| Error handling standardization | Consistent error response format across all tools | Medium |
| API client refactor | Unify Gemini and OpenRouter clients behind a common interface | Low |

---

## 5. Success Metrics

| Metric | Target |
|--------|--------|
| Invoice extraction accuracy | ≥ 95% on standard printed invoices |
| OCR text extraction quality | ≥ 90% character accuracy |
| Duplicate detection precision | ≥ 99% (no false positives blocking real invoices) |
| Response latency (text Q&A) | < 3 seconds (p95) |
| Response latency (invoice pipeline) | < 10 seconds (p95) |
| Test coverage | ≥ 80% line coverage |
| Uptime (after deployment) | ≥ 99.5% |

---

## 6. Tech Stack

| Layer | Current | Planned |
|-------|---------|---------|
| **Frontend** | Streamlit + custom CSS | Streamlit (short-term), React/Next.js (long-term) |
| **Backend** | Python, stdlib HTTP clients | Python + FastAPI (for API layer) |
| **AI/LLM** | Google Gemini + OpenRouter | Same + embeddings pipeline |
| **Vision/OCR** | Gemini Vision + OpenRouter Vision + Pillow | Same + PDF processing |
| **Storage** | JSON files | SQLite → PostgreSQL |
| **Search** | None | Vector DB (ChromaDB / Pinecone) |
| **Deployment** | Local Streamlit | Docker + Cloud hosting |
| **CI/CD** | None | GitHub Actions |
| **Monitoring** | None | Application monitoring + alerting |

---

## 7. Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol — a standard for LLM tool discovery and selection |
| **OCR** | Optical Character Recognition — extracting text from images |
| **ERP** | Enterprise Resource Planning — business management software |
| **RAG** | Retrieval-Augmented Generation — enhancing LLM responses with retrieved context |
| **GST** | Goods and Services Tax — Indian tax system |
| **Manglish** | Malayalam language written in Latin/English script |

---

*Last updated: 2026-08-12*
