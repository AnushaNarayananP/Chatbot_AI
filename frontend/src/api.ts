/**
 * API client for the FriendlyBot FastAPI backend.
 *
 * All functions talk to http://localhost:8000/api/*
 */

const API_BASE = "/api";

// ---------------------------------------------------------------------------
// Types (kept in sync with types.ts)
// ---------------------------------------------------------------------------

export interface ChatResponse {
  ok: boolean;
  reply: string;
  meta: Record<string, unknown>;
  intent?: string;
  tool_calls?: string[];
  structured_data?: Record<string, unknown>;
  transcript?: string;
}

export interface InvoiceRow {
  invoice_id: string;
  vendor: string;
  invoice_number: string;
  date: string;
  currency: string;
  subtotal: number;
  tax: number;
  total_amount: number;
}

export interface PurchaseRow {
  invoice_id: string;
  sr_no: number;
  name: string;
  quantity: number;
  rate: number;
  total: number;
}

export interface RawInvoice {
  invoice_id: string;
  vendor: string;
  invoice_number: string;
  date: string;
  currency: string;
  items: Array<{
    sr_no: number;
    name: string;
    quantity: number;
    rate: number;
    total: number;
  }>;
  summary: {
    subtotal: number;
    tax: number;
    total_amount: number;
  };
}

export interface InvoicesResponse {
  invoices: InvoiceRow[];
  purchases: PurchaseRow[];
  raw_invoices: RawInvoice[];
}

export interface RagDocument {
  doc_id: string;
  filename: string;
  num_chunks: number;
  chunk_count?: number;
}

export interface ConfigResponse {
  bot_name: string;
  default_model: string;
  rag_enabled: boolean;
  rag_active: boolean;
  system_prompt: string;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error(`Config fetch failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export async function sendChatMessage(params: {
  prompt: string;
  model: string;
  messages: Array<{ role: string; content: string }>;
  image?: File | null;
  imageUrl?: string;
}): Promise<ChatResponse> {
  const form = new FormData();
  form.append("prompt", params.prompt);
  form.append("model", params.model);
  form.append("messages", JSON.stringify(params.messages));
  if (params.image) {
    form.append("image", params.image);
  }
  if (params.imageUrl) {
    form.append("image_url", params.imageUrl);
  }

  const res = await fetch(`${API_BASE}/chat`, { method: "POST", body: form });
  return res.json();
}

export async function sendAudioChat(params: {
  audio: Blob;
  filename: string;
  prompt: string;
  model: string;
  messages: Array<{ role: string; content: string }>;
}): Promise<ChatResponse> {
  const form = new FormData();
  form.append("audio", params.audio, params.filename);
  form.append("prompt", params.prompt);
  form.append("model", params.model);
  form.append("messages", JSON.stringify(params.messages));

  const res = await fetch(`${API_BASE}/chat/audio`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Invoices
// ---------------------------------------------------------------------------

export async function fetchInvoices(): Promise<InvoicesResponse> {
  const res = await fetch(`${API_BASE}/invoices`);
  if (!res.ok) throw new Error(`Invoices fetch failed: ${res.status}`);
  return res.json();
}

export async function resetInvoices(): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/invoices/reset`, { method: "POST" });
  return res.json();
}

// ---------------------------------------------------------------------------
// RAG Documents
// ---------------------------------------------------------------------------

export async function fetchRagDocuments(): Promise<{
  documents: RagDocument[];
  enabled: boolean;
}> {
  const res = await fetch(`${API_BASE}/rag/documents`);
  if (!res.ok) throw new Error(`RAG docs fetch failed: ${res.status}`);
  return res.json();
}

export async function uploadRagDocument(
  file: File
): Promise<{ ok: boolean; doc_id?: string; filename?: string; num_chunks?: number; error?: string }> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/rag/upload`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export async function deleteRagDocument(
  docId: string
): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/rag/documents/${docId}`, {
    method: "DELETE",
  });
  return res.json();
}

export async function clearRagDocuments(): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/rag/clear`, { method: "POST" });
  return res.json();
}
