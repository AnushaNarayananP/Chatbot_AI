import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Plus, Search, Trash2, Database, FileText, Upload,
  Paperclip, Mic, MicOff, Send, Copy, Check, ThumbsUp, ThumbsDown,
  Volume2, RefreshCw, ChevronDown, ChevronRight, Settings, ExternalLink,
  Eye, FileCheck, Layers, Cpu, ShieldCheck, Sparkles, AlertCircle,
  FileCode, X, ArrowUpRight, CheckCircle2, Clock, Globe, ArrowRight,
  TrendingUp, Download, Table, BookOpen, HardDrive, HelpCircle, Loader2
} from 'lucide-react';
import {
  sendChatMessage,
  sendAudioChat,
  fetchInvoices,
  fetchRagDocuments,
  uploadRagDocument,
  deleteRagDocument,
  clearRagDocuments,
  fetchConfig,
  type ChatResponse,
  type RagDocument,
  type InvoicesResponse,
  type RawInvoice,
} from './api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  attachments?: Array<{ name: string; size: string; type: string }>;
  meta?: Record<string, any>;
}

interface ChatSession {
  id: string;
  title: string;
  timeCategory: string;
  messages: ChatMessage[];
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  // Navigation & Sessions
  const [chats, setChats] = useState<ChatSession[]>([
    {
      id: 'session-1',
      title: 'New conversation',
      timeCategory: 'Today',
      messages: [
        {
          id: 'm-init-1',
          role: 'assistant',
          content:
            "Hello there! I'm **Avi**, your document intelligence companion. You can upload invoices, ask questions about your uploaded PDFs, request translations, or test ERP sync. How can I help your workflow today?",
          meta: { latency: 0 },
        },
      ],
    },
  ]);

  const [activeChatId, setActiveChatId] = useState('session-1');
  const [model, setModel] = useState('gemini-2.5-flash');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);

  // Composer State
  const [inputPrompt, setInputPrompt] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Features Drawers & Modals
  const [erpModalOpen, setErpModalOpen] = useState(false);
  const [ragDrawerOpen, setRagDrawerOpen] = useState(false);
  const [invoicesData, setInvoicesData] = useState<InvoicesResponse | null>(null);
  const [ragDocs, setRagDocs] = useState<RagDocument[]>([]);
  const [ragEnabled, setRagEnabled] = useState(true);
  const [debugOcrModal, setDebugOcrModal] = useState<any>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [ragUploading, setRagUploading] = useState(false);

  // Audio recording
  const [audioTimer, setAudioTimer] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ragFileInputRef = useRef<HTMLInputElement>(null);

  const activeChat = chats.find((c) => c.id === activeChatId) || chats[0];

  // -------------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------------

  useEffect(() => {
    loadInvoices();
    loadRagDocs();
  }, []);

  const loadInvoices = async () => {
    try {
      const data = await fetchInvoices();
      setInvoicesData(data);
    } catch (e) {
      console.error('Failed to load invoices:', e);
    }
  };

  const loadRagDocs = async () => {
    try {
      const data = await fetchRagDocuments();
      setRagDocs(data.documents);
      setRagEnabled(data.enabled);
    } catch (e) {
      console.error('Failed to load RAG docs:', e);
    }
  };

  // -------------------------------------------------------------------------
  // Auto-scroll
  // -------------------------------------------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChat?.messages, isSubmitting]);

  // Audio timer
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isRecording) {
      interval = setInterval(() => setAudioTimer((t) => t + 1), 1000);
    } else {
      setAudioTimer(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputPrompt(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSpeechSimulation = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text.replace(/[*#_`]/g, ''));
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  };

  const createNewChat = () => {
    const newId = `session-${Date.now()}`;
    const newChat: ChatSession = {
      id: newId,
      title: 'New conversation',
      timeCategory: 'Today',
      messages: [
        {
          id: `m-${Date.now()}`,
          role: 'assistant',
          content:
            "Hi, I'm **Avi**! I can parse multi-format invoices with OCR, extract GST and line items, sync directly with your ERP, or query your internal documents with RAG. Try uploading an invoice or typing a question in Hindi, Malayalam, Manglish, or English!",
          meta: { latency: 0 },
        },
      ],
    };
    setChats([newChat, ...chats]);
    setActiveChatId(newId);
  };

  const deleteChat = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const remaining = chats.filter((c) => c.id !== id);
    if (remaining.length === 0) {
      createNewChat();
    } else {
      setChats(remaining);
      if (activeChatId === id) {
        setActiveChatId(remaining[0].id);
      }
    }
  };

  // -------------------------------------------------------------------------
  // File handling
  // -------------------------------------------------------------------------

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setAttachedFiles((prev) => [...prev, ...files]);
    e.target.value = '';
  };

  const removeAttachment = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const getFileType = (file: File) => {
    if (file.type.includes('image')) return 'image';
    // JFIF files may have an empty or unrecognized MIME type in some browsers
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext === 'jfif') return 'image';
    if (file.type.includes('pdf')) return 'pdf';
    if (file.type.includes('audio')) return 'audio';
    return 'document';
  };

  // -------------------------------------------------------------------------
  // Audio recording (real MediaRecorder)
  // -------------------------------------------------------------------------

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (audioBlob.size > 0) {
          await submitAudioMessage(audioBlob);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const submitAudioMessage = async (audioBlob: Blob) => {
    setIsSubmitting(true);

    // Build messages for context
    const apiMessages = buildApiMessages();

    // Add user message placeholder
    const userMsgId = `u-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: inputPrompt || '[🎤 Voice message]',
      attachments: [{ name: 'voice_recording.webm', size: `${(audioBlob.size / 1024).toFixed(1)} KB`, type: 'audio' }],
    };

    updateChatMessages(userMessage);
    const currentPrompt = inputPrompt;
    setInputPrompt('');

    try {
      const result = await sendAudioChat({
        audio: audioBlob,
        filename: 'recording.webm',
        prompt: currentPrompt,
        model,
        messages: apiMessages,
      });

      const botMessage: ChatMessage = {
        id: `m-${Date.now()}`,
        role: 'assistant',
        content: result.reply,
        meta: {
          ...result.meta,
          intent: result.intent,
          transcript: result.transcript,
        },
      };
      updateChatMessages(botMessage);
      await loadInvoices();
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `m-${Date.now()}`,
        role: 'assistant',
        content: `❌ Error: ${err.message || 'Something went wrong.'}`,
        meta: { error: true },
      };
      updateChatMessages(errorMsg);
    }

    setIsSubmitting(false);
  };

  // -------------------------------------------------------------------------
  // Chat submission (main)
  // -------------------------------------------------------------------------

  const buildApiMessages = (): Array<{ role: string; content: string }> => {
    return activeChat.messages
      .filter((m) => m.role !== 'system')
      .map((m) => ({ role: m.role, content: m.content }));
  };

  const updateChatMessages = (newMsg: ChatMessage) => {
    setChats((prev) =>
      prev.map((chat) => {
        if (chat.id === activeChatId) {
          return {
            ...chat,
            title:
              chat.messages.length <= 1 && newMsg.role === 'user'
                ? newMsg.content.slice(0, 28) || 'Document Intelligence'
                : chat.title,
            messages: [...chat.messages, newMsg],
          };
        }
        return chat;
      })
    );
  };

  const handleSubmitMessage = async (customPrompt?: string) => {
    const promptToSend = customPrompt || inputPrompt;
    if (!promptToSend.trim() && attachedFiles.length === 0) return;

    setIsSubmitting(true);

    // Find image attachment
    const imageFile = attachedFiles.find((f) => getFileType(f) === 'image') || null;

    // User message
    const userMsgId = `u-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: promptToSend,
      attachments: attachedFiles.map((f) => ({
        name: f.name,
        size: `${(f.size / 1024).toFixed(1)} KB`,
        type: getFileType(f),
      })),
    };

    // Build API messages BEFORE adding user message (to avoid echo)
    const apiMessages = buildApiMessages();
    apiMessages.push({ role: 'user', content: promptToSend });

    updateChatMessages(userMessage);
    setInputPrompt('');
    setAttachedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    try {
      const result = await sendChatMessage({
        prompt: promptToSend,
        model,
        messages: apiMessages,
        image: imageFile,
      });

      const botMessage: ChatMessage = {
        id: `m-${Date.now()}`,
        role: 'assistant',
        content: result.reply,
        meta: {
          ...result.meta,
          intent: result.intent,
          tool_calls: result.tool_calls,
          structured_data: result.structured_data,
        },
      };
      updateChatMessages(botMessage);

      // Refresh invoices (an invoice might have been stored)
      await loadInvoices();
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `m-${Date.now()}`,
        role: 'assistant',
        content: `❌ Error: ${err.message || 'Something went wrong.'}`,
        meta: { error: true },
      };
      updateChatMessages(errorMsg);
    }

    setIsSubmitting(false);
  };

  const handleQuickPrompt = (promptText: string) => {
    handleSubmitMessage(promptText);
  };

  // -------------------------------------------------------------------------
  // RAG handlers
  // -------------------------------------------------------------------------

  const handleRagUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    e.target.value = '';

    setRagUploading(true);
    for (const file of files) {
      try {
        const result = await uploadRagDocument(file);
        if (result.ok) {
          await loadRagDocs();
        } else {
          console.error('RAG upload failed:', result.error);
        }
      } catch (err) {
        console.error('RAG upload error:', err);
      }
    }
    setRagUploading(false);
  };

  const handleDeleteRagDoc = async (docId: string) => {
    await deleteRagDocument(docId);
    await loadRagDocs();
  };

  const handleClearRagDocs = async () => {
    await clearRagDocuments();
    setRagDocs([]);
  };

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------

  const invoices = invoicesData?.raw_invoices || [];
  const invoiceTableRows = invoicesData?.invoices || [];
  const purchaseTableRows = invoicesData?.purchases || [];

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div className="flex h-screen w-screen bg-[#212121] text-gray-100 font-sans overflow-hidden antialiased select-none">

      {/* ================================================================= */}
      {/* SIDEBAR                                                           */}
      {/* ================================================================= */}
      <aside
        className={`${
          sidebarOpen ? 'w-[260px]' : 'w-0'
        } transition-all duration-300 ease-in-out bg-[#171717] border-r border-[#2f2f2f] flex flex-col z-30 shrink-0 relative overflow-hidden`}
      >
        <div className="p-3 flex flex-col h-full justify-between w-[260px]">
          {/* Top Actions */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between px-2 py-1.5">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 via-indigo-500 to-purple-400 flex items-center justify-center font-bold text-white shadow-md shadow-purple-900/30 text-sm">
                  A
                </div>
                <div>
                  <h1 className="text-sm font-semibold tracking-wide text-white flex items-center gap-1.5">
                    FriendlyBot
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-purple-900/60 text-purple-300 border border-purple-700/50">
                      Avi
                    </span>
                  </h1>
                </div>
              </div>
              <button
                onClick={() => setSidebarOpen(false)}
                className="text-gray-400 hover:text-white p-1 rounded-md hover:bg-[#262626] transition-colors"
                title="Collapse sidebar"
              >
                <Layers className="w-4 h-4" />
              </button>
            </div>

            {/* New Chat */}
            <button
              onClick={createNewChat}
              className="flex items-center justify-between w-full px-3 py-2.5 rounded-lg border border-[#383838] bg-[#212121] hover:bg-[#2a2a2a] text-sm text-gray-200 hover:text-white transition-all shadow-sm group"
            >
              <span className="flex items-center gap-2 font-medium text-xs">
                <Plus className="w-4 h-4 text-gray-400 group-hover:text-purple-400 transition-colors" />
                New Chat
              </span>
              <span className="text-[11px] text-gray-400 font-mono">⌘N</span>
            </button>

            {/* Quick Access */}
            <div className="grid grid-cols-2 gap-1.5 mt-1">
              <button
                onClick={() => setRagDrawerOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg bg-[#212121] hover:bg-[#282828] border border-[#303030] text-[11px] font-medium text-gray-300 hover:text-purple-300 transition-all text-left"
              >
                <BookOpen className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                <span className="truncate">RAG Docs ({ragDocs.length})</span>
              </button>
              <button
                onClick={() => setErpModalOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg bg-[#212121] hover:bg-[#282828] border border-[#303030] text-[11px] font-medium text-gray-300 hover:text-emerald-300 transition-all text-left"
              >
                <Database className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span className="truncate">ERP Invoices</span>
              </button>
            </div>
          </div>

          {/* Chat History */}
          <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-4 text-xs scrollbar-thin scrollbar-thumb-[#333]">
            {['Today', 'Yesterday', 'Previous 7 days'].map((group) => {
              const groupChats = chats.filter((c) => c.timeCategory === group);
              if (!groupChats.length) return null;
              return (
                <div key={group} className="space-y-1">
                  <div className="px-2 text-[11px] font-semibold text-gray-400 tracking-wider">
                    {group}
                  </div>
                  {groupChats.map((c) => (
                    <div
                      key={c.id}
                      onClick={() => setActiveChatId(c.id)}
                      className={`group flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-all ${
                        activeChatId === c.id
                          ? 'bg-[#262626] text-white font-medium'
                          : 'text-gray-300 hover:bg-[#212121] hover:text-white'
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <MessageSquare
                          className={`w-3.5 h-3.5 shrink-0 ${
                            activeChatId === c.id ? 'text-purple-400' : 'text-gray-400'
                          }`}
                        />
                        <span className="truncate">{c.title}</span>
                      </div>
                      <button
                        onClick={(e) => deleteChat(e, c.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 text-gray-400 transition-opacity"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          {/* User Profile */}
          <div className="pt-3 border-t border-[#2a2a2a] flex items-center justify-between px-2">
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <div className="w-7 h-7 rounded-full bg-emerald-700/80 flex items-center justify-center text-xs font-bold text-emerald-200">
                  U
                </div>
                <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-500 border border-[#171717]" />
              </div>
              <div className="flex flex-col text-left">
                <span className="text-xs font-medium text-gray-200">Local Analyst</span>
                <span className="text-[10px] text-gray-400">ChromaDB & SQLite Online</span>
              </div>
            </div>
            <button
              onClick={() => setErpModalOpen(true)}
              className="p-1.5 rounded-md hover:bg-[#262626] text-gray-400 hover:text-gray-200"
              title="System Database status"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* ================================================================= */}
      {/* MAIN AREA                                                         */}
      {/* ================================================================= */}
      <main className="flex-1 flex flex-col h-full bg-[#212121] relative overflow-hidden">
        {/* Top Navbar */}
        <header className="h-14 border-b border-[#2d2d2d] px-4 flex items-center justify-between shrink-0 bg-[#212121]/90 backdrop-blur z-20">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-1.5 rounded-lg hover:bg-[#2f2f2f] text-gray-300 hover:text-white transition-colors"
                title="Expand sidebar"
              >
                <Layers className="w-4 h-4" />
              </button>
            )}

            {/* Model Selector */}
            <div className="relative">
              <button
                onClick={() => setModelMenuOpen(!modelMenuOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl hover:bg-[#2f2f2f] text-sm font-semibold text-gray-100 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                  {model === 'gemini-2.5-flash' ? 'Gemini 2.5 Flash' : 'OpenRouter (Llama 4)'}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
              </button>

              {modelMenuOpen && (
                <div className="absolute left-0 mt-2 w-64 bg-[#262626] border border-[#383838] rounded-xl shadow-2xl py-1 z-50">
                  <div
                    onClick={() => { setModel('gemini-2.5-flash'); setModelMenuOpen(false); }}
                    className="px-3 py-2.5 hover:bg-[#333333] cursor-pointer flex items-start gap-2.5 transition-colors"
                  >
                    <Sparkles className="w-4 h-4 text-purple-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                        Gemini 2.5 Flash
                        <span className="text-[10px] bg-purple-900/60 text-purple-300 px-1 rounded">Primary</span>
                      </div>
                      <div className="text-[11px] text-gray-400">High speed, OCR Vision & multimodal extraction.</div>
                    </div>
                  </div>
                  <div
                    onClick={() => { setModel('openrouter/llama-4-maverick'); setModelMenuOpen(false); }}
                    className="px-3 py-2.5 hover:bg-[#333333] cursor-pointer flex items-start gap-2.5 transition-colors border-t border-[#333]"
                  >
                    <Cpu className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                        Llama 4 Maverick
                        <span className="text-[10px] bg-amber-900/60 text-amber-300 px-1 rounded">Fallback</span>
                      </div>
                      <div className="text-[11px] text-gray-400">OpenRouter failover & open-weights processing.</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* RAG Status */}
            {ragDocs.length > 0 && (
              <div
                onClick={() => setRagDrawerOpen(true)}
                className="cursor-pointer hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-700/50 text-[11px] font-medium text-emerald-300 hover:bg-emerald-900/60 transition-colors"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span>RAG Active ({ragDocs.length} Docs)</span>
              </div>
            )}
          </div>

          {/* Right Header */}
          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center gap-3 text-[11px] text-gray-400 font-mono pr-2">
              <span className="flex items-center gap-1">
                <Globe className="w-3 h-3 text-indigo-400" />
                EN / ML / HI / Manglish
              </span>
              <span className="text-gray-600">•</span>
              <span className="flex items-center gap-1 text-emerald-400">
                <ShieldCheck className="w-3 h-3" />
                ERP Synced
              </span>
            </div>

            <button
              onClick={() => setErpModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 text-xs font-medium text-purple-200 transition-colors"
            >
              <Database className="w-3.5 h-3.5 text-purple-300" />
              <span>Invoices Ledger</span>
              <span className="bg-purple-500/40 px-1 rounded text-[10px]">{invoiceTableRows.length}</span>
            </button>
          </div>
        </header>

        {/* ================================================================= */}
        {/* MESSAGE AREA                                                      */}
        {/* ================================================================= */}
        <div className="flex-1 overflow-y-auto px-4 md:px-0 py-6 scrollbar-thin scrollbar-thumb-[#383838]">
          <div className="max-w-3xl mx-auto space-y-6">
            {activeChat.messages.length <= 1 ? (
              /* Empty / Greeting State */
              <div className="pt-8 pb-4 flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center text-white shadow-xl shadow-purple-900/40 mb-4">
                  <span className="text-2xl font-bold font-mono">A</span>
                </div>
                <h2 className="text-2xl font-bold text-white tracking-tight">
                  FriendlyBot (Avi)
                </h2>
                <p className="text-sm text-gray-400 mt-1 max-w-md">
                  Autonomous document intelligence, receipt OCR, GST extraction, mock ERP synchronization, and multi-lingual conversation.
                </p>

                {/* Quick Capability Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full mt-8 text-left">
                  <div
                    onClick={() => handleQuickPrompt('Please extract this invoice, check GST calculations, and push to ERP.')}
                    className="p-3.5 rounded-xl border border-[#333] bg-[#262626]/80 hover:bg-[#2e2e2e] hover:border-purple-500/50 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center justify-between text-xs font-semibold text-purple-300 mb-1">
                      <span className="flex items-center gap-1.5">
                        <FileCheck className="w-4 h-4 text-purple-400" />
                        Process Sample Invoice
                      </span>
                      <ArrowUpRight className="w-3.5 h-3.5 text-gray-500 group-hover:text-purple-300 transition-colors" />
                    </div>
                    <div className="text-xs text-gray-400">
                      Simulate dual-vision OCR, extract GST, verify totals, and trigger ERP push.
                    </div>
                  </div>

                  <div
                    onClick={() => handleQuickPrompt('What are the invoice approval limits as per Procurement_Policy_2026.pdf?')}
                    className="p-3.5 rounded-xl border border-[#333] bg-[#262626]/80 hover:bg-[#2e2e2e] hover:border-emerald-500/50 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center justify-between text-xs font-semibold text-emerald-300 mb-1">
                      <span className="flex items-center gap-1.5">
                        <BookOpen className="w-4 h-4 text-emerald-400" />
                        Query RAG Knowledge
                      </span>
                      <ArrowUpRight className="w-3.5 h-3.5 text-gray-500 group-hover:text-emerald-300 transition-colors" />
                    </div>
                    <div className="text-xs text-gray-400">
                      Ask questions grounded on uploaded internal company guidelines & PDFs.
                    </div>
                  </div>

                  <div
                    onClick={() => handleQuickPrompt('നമസ്കാരം! ഈ മാസത്തെ ഇൻവോയ്സുകൾ ചെക്ക് ചെയ്യാൻ സഹായിക്കാമോ?')}
                    className="p-3.5 rounded-xl border border-[#333] bg-[#262626]/80 hover:bg-[#2e2e2e] hover:border-indigo-500/50 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center justify-between text-xs font-semibold text-indigo-300 mb-1">
                      <span className="flex items-center gap-1.5">
                        <Globe className="w-4 h-4 text-indigo-400" />
                        Malayalam / Manglish Prompt
                      </span>
                      <ArrowUpRight className="w-3.5 h-3.5 text-gray-500 group-hover:text-indigo-300 transition-colors" />
                    </div>
                    <div className="text-xs text-gray-400">
                      "നമസ്കാരം! ഈ മാസത്തെ ഇൻവോയ്സുകൾ ചെക്ക് ചെയ്യാൻ സഹായിക്കാമോ?"
                    </div>
                  </div>

                  <div
                    onClick={() => handleQuickPrompt("Translate: 'The payment for invoice KE/2026/8942 has been successfully posted to our ERP.' into Hindi and Malayalam.")}
                    className="p-3.5 rounded-xl border border-[#333] bg-[#262626]/80 hover:bg-[#2e2e2e] hover:border-amber-500/50 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center justify-between text-xs font-semibold text-amber-300 mb-1">
                      <span className="flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-amber-400" />
                        Auto-Translation
                      </span>
                      <ArrowUpRight className="w-3.5 h-3.5 text-gray-500 group-hover:text-amber-300 transition-colors" />
                    </div>
                    <div className="text-xs text-gray-400">
                      Translate vendor notes, accounting receipts, or messages instantly.
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {/* Message List */}
            {activeChat.messages.map((message) => {
              const isAssistant = message.role === 'assistant';
              return (
                <div key={message.id} className={`flex gap-4 ${isAssistant ? 'justify-start' : 'justify-end'}`}>
                  {isAssistant && (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center font-bold text-white text-xs shrink-0 shadow-md">
                      A
                    </div>
                  )}

                  <div className={`flex flex-col space-y-2 max-w-[88%] ${!isAssistant ? 'items-end' : 'items-start'}`}>
                    {/* Attachments */}
                    {message.attachments && message.attachments.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-1">
                        {message.attachments.map((file, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#2a2a2a] border border-[#3b3b3b] text-xs text-gray-200"
                          >
                            <FileText className="w-3.5 h-3.5 text-purple-400" />
                            <span className="font-medium">{file.name}</span>
                            <span className="text-[10px] text-gray-400 font-mono">({file.size})</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Chat Bubble */}
                    <div
                      className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                        isAssistant
                          ? 'bg-[#2a2a2a] text-gray-100 border border-[#363636] shadow-sm'
                          : 'bg-purple-600 text-white rounded-br-sm'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{message.content}</div>

                      {/* Inline invoice data from structured_data */}
                      {message.meta?.structured_data?.invoice_extraction && (
                        <div className="mt-4 pt-3 border-t border-[#3e3e3e] space-y-2">
                          <div className="flex items-center gap-2 text-xs">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-emerald-300 font-medium">Invoice processed & stored</span>
                            {message.meta?.structured_data?.invoice_extraction?.confidence && (
                              <span className="text-gray-400 font-mono ml-auto">
                                Conf: {(Number(message.meta.structured_data.invoice_extraction.confidence) * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Assistant Meta Actions */}
                    {isAssistant && (
                      <div className="flex items-center gap-2 pt-1 text-xs text-gray-400">
                        <button
                          onClick={() => handleCopy(message.content, message.id)}
                          className="hover:text-gray-200 p-1 rounded hover:bg-[#2d2d2d] transition-colors"
                          title="Copy response"
                        >
                          {copiedId === message.id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => handleSpeechSimulation(message.content)}
                          className="hover:text-gray-200 p-1 rounded hover:bg-[#2d2d2d] transition-colors"
                          title="Read aloud"
                        >
                          <Volume2 className="w-3.5 h-3.5" />
                        </button>
                        <button className="hover:text-gray-200 p-1 rounded hover:bg-[#2d2d2d] transition-colors" title="Good response">
                          <ThumbsUp className="w-3.5 h-3.5" />
                        </button>
                        <button className="hover:text-gray-200 p-1 rounded hover:bg-[#2d2d2d] transition-colors" title="Bad response">
                          <ThumbsDown className="w-3.5 h-3.5" />
                        </button>

                        {message.meta?.latency_ms && (
                          <span className="text-[10px] font-mono text-gray-400 ml-1">
                            {message.meta.latency_ms}ms
                          </span>
                        )}
                        {message.meta?.intent && (
                          <span className="text-[10px] bg-purple-950 text-purple-300 border border-purple-800/80 px-1.5 rounded font-mono">
                            {message.meta.intent}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Typing Indicator */}
            {isSubmitting && (
              <div className="flex gap-4 items-start">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center font-bold text-white text-xs shrink-0 shadow-md">
                  A
                </div>
                <div className="bg-[#2a2a2a] border border-[#383838] px-4 py-3 rounded-2xl flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-purple-300 animate-bounce" style={{ animationDelay: '300ms' }} />
                  <span className="text-xs text-gray-400 ml-2 font-mono">
                    Routing to {model === 'gemini-2.5-flash' ? 'Gemini 2.5 Flash' : 'OpenRouter Llama 4'}...
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ================================================================= */}
        {/* COMPOSER                                                          */}
        {/* ================================================================= */}
        <div className="w-full bg-[#212121] px-4 pb-4 pt-2">
          <div className="max-w-3xl mx-auto">
            {/* Attachment previews */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2 p-2 bg-[#262626] rounded-xl border border-[#383838]">
                {attachedFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#333] text-xs text-gray-200 border border-[#444]"
                  >
                    <FileText className="w-3.5 h-3.5 text-purple-400" />
                    <span className="max-w-[140px] truncate">{file.name}</span>
                    <button onClick={() => removeAttachment(idx)} className="hover:text-red-400 p-0.5 rounded">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Composer Box */}
            <div className="relative rounded-2xl bg-[#2f2f2f] border border-[#424242] focus-within:border-gray-500 shadow-xl transition-all">
              <textarea
                ref={textareaRef}
                value={inputPrompt}
                onChange={handleTextareaChange}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitMessage();
                  }
                }}
                rows={1}
                placeholder={
                  isRecording
                    ? `Recording voice note... (${audioTimer}s) Click mic to stop`
                    : "Message Avi... (Ask in English, Malayalam, Hindi, or upload an invoice)"
                }
                className="w-full bg-transparent text-gray-100 placeholder-gray-400 text-sm px-4 pt-3.5 pb-12 focus:outline-none resize-none max-h-48 overflow-y-auto"
              />

              {/* Bottom Toolbar */}
              <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    multiple
                    accept="image/*,.jfif,.pdf,.docx,.txt,.md,.wav,.mp3,.ogg,.m4a,.webm"
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="p-1.5 rounded-full text-gray-400 hover:text-white hover:bg-[#3d3d3d] transition-colors"
                    title="Attach invoice, image, receipt, or RAG document"
                  >
                    <Paperclip className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {/* Microphone */}
                  <button
                    type="button"
                    onClick={() => {
                      if (isRecording) {
                        stopRecording();
                      } else {
                        startRecording();
                      }
                    }}
                    className={`p-2 rounded-full transition-all ${
                      isRecording
                        ? 'bg-red-500 text-white animate-pulse'
                        : 'text-gray-400 hover:text-white hover:bg-[#3d3d3d]'
                    }`}
                    title={isRecording ? 'Stop recording' : 'Speech-to-text input'}
                  >
                    {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>

                  {/* Send */}
                  <button
                    type="button"
                    onClick={() => handleSubmitMessage()}
                    disabled={(!inputPrompt.trim() && attachedFiles.length === 0) || isSubmitting}
                    className={`p-2 rounded-full transition-all ${
                      (inputPrompt.trim() || attachedFiles.length > 0) && !isSubmitting
                        ? 'bg-white text-black hover:bg-gray-200'
                        : 'bg-[#404040] text-gray-500 cursor-not-allowed'
                    }`}
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            <div className="text-center text-[11px] text-gray-400 mt-2">
              FriendlyBot Avi may verify extracted data against ERP standards. Check critical numbers.
            </div>
          </div>
        </div>
      </main>

      {/* ================================================================= */}
      {/* RAG DRAWER                                                        */}
      {/* ================================================================= */}
      {ragDrawerOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-[#1e1e1e] border-l border-[#333] h-full flex flex-col shadow-2xl p-5 overflow-hidden">
            <div className="flex items-center justify-between pb-4 border-b border-[#2e2e2e]">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-emerald-950 border border-emerald-800 flex items-center justify-center">
                  <BookOpen className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">RAG Document Store</h3>
                  <p className="text-[11px] text-gray-400">ChromaDB Vector Embeddings</p>
                </div>
              </div>
              <button onClick={() => setRagDrawerOpen(false)} className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-[#2b2b2b]">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Upload Area */}
            <div className="mt-4 p-4 rounded-xl border border-dashed border-[#444] bg-[#242424] text-center">
              <Upload className="w-6 h-6 text-purple-400 mx-auto mb-2" />
              <div className="text-xs font-semibold text-gray-200">Upload Knowledge Documents</div>
              <div className="text-[11px] text-gray-400 mt-0.5">Supports PDF, DOCX, TXT, MD (Max 20MB)</div>
              <input
                type="file"
                ref={ragFileInputRef}
                onChange={handleRagUpload}
                multiple
                accept=".pdf,.docx,.txt,.md"
                className="hidden"
              />
              <button
                onClick={() => ragFileInputRef.current?.click()}
                disabled={ragUploading}
                className="mt-3 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium transition-colors disabled:opacity-50 flex items-center gap-2 mx-auto"
              >
                {ragUploading ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Ingesting...
                  </>
                ) : (
                  '+ Upload Document'
                )}
              </button>
            </div>

            {/* Document List */}
            <div className="flex-1 overflow-y-auto mt-4 space-y-2 pr-1">
              <div className="flex items-center justify-between text-xs font-semibold text-gray-400 px-1">
                <span>Ingested Documents ({ragDocs.length})</span>
                {ragDocs.length > 0 && (
                  <button onClick={handleClearRagDocs} className="text-red-400 hover:text-red-300 text-[11px]">
                    Clear All
                  </button>
                )}
              </div>

              {ragDocs.map((doc) => (
                <div
                  key={doc.doc_id}
                  className="p-3 rounded-xl bg-[#262626] border border-[#333] flex items-center justify-between group hover:border-[#444]"
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                    <div className="truncate">
                      <div className="text-xs font-medium text-gray-200 truncate">{doc.filename}</div>
                      <div className="text-[10px] text-gray-400 flex items-center gap-2 mt-0.5 font-mono">
                        <span>{doc.num_chunks} vector chunks</span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteRagDoc(doc.doc_id)}
                    className="p-1 text-gray-500 hover:text-red-400 opacity-60 group-hover:opacity-100 transition-opacity"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}

              {ragDocs.length === 0 && (
                <div className="text-center text-xs text-gray-500 py-8">
                  No documents uploaded yet. Upload files above to enable RAG mode.
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-[#2e2e2e]">
              <div className="text-[11px] text-gray-400 leading-normal">
                Documents are embedded and stored in ChromaDB for high-accuracy retrieval when answering vendor and policy questions.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* ERP / INVOICE MODAL                                               */}
      {/* ================================================================= */}
      {erpModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#1f1f1f] border border-[#383838] w-full max-w-4xl max-h-[85vh] rounded-2xl flex flex-col shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-[#303030] flex items-center justify-between bg-[#242424]">
              <div className="flex items-center gap-2.5">
                <Database className="w-5 h-5 text-purple-400" />
                <div>
                  <h3 className="text-sm font-semibold text-white">Invoice Database & Mock ERP Ledger</h3>
                  <p className="text-[11px] text-gray-400 font-mono">Synchronized with sqlite:chatbot.db</p>
                </div>
              </div>
              <button onClick={() => setErpModalOpen(false)} className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-[#333]">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Tables */}
            <div className="p-4 flex-1 overflow-y-auto">
              {/* Invoice Table */}
              <div className="rounded-xl border border-[#333] overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#292929] text-gray-400 font-semibold border-b border-[#383838]">
                    <tr>
                      <th className="py-2.5 px-3 font-mono">ID</th>
                      <th className="py-2.5 px-3">Vendor</th>
                      <th className="py-2.5 px-3 font-mono">Invoice #</th>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3 text-right">Subtotal</th>
                      <th className="py-2.5 px-3 text-right">Tax (GST)</th>
                      <th className="py-2.5 px-3 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#2d2d2d] text-gray-300">
                    {invoiceTableRows.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-gray-500">
                          No invoices stored yet. Upload an invoice image to get started.
                        </td>
                      </tr>
                    ) : (
                      invoiceTableRows.map((inv) => (
                        <tr key={inv.invoice_id} className="hover:bg-[#262626] transition-colors">
                          <td className="py-2.5 px-3 font-mono font-bold text-purple-300">{inv.invoice_id}</td>
                          <td className="py-2.5 px-3 font-medium text-white">{inv.vendor}</td>
                          <td className="py-2.5 px-3 font-mono text-gray-400">{inv.invoice_number}</td>
                          <td className="py-2.5 px-3 font-mono">{inv.date}</td>
                          <td className="py-2.5 px-3 text-right font-mono">₹{Number(inv.subtotal || 0).toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right font-mono text-amber-400">₹{Number(inv.tax || 0).toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-400">₹{Number(inv.total_amount || 0).toFixed(2)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Purchase Items */}
              {purchaseTableRows.length > 0 && (
                <div className="mt-5">
                  <div className="text-xs font-semibold text-gray-300 mb-2 flex items-center gap-1.5">
                    <Table className="w-3.5 h-3.5 text-indigo-400" />
                    Expanded Line Items Breakdown (Purchase Table)
                  </div>
                  <div className="rounded-xl border border-[#333] overflow-hidden bg-[#242424]">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#2c2c2c] text-gray-400 border-b border-[#383838]">
                        <tr>
                          <th className="py-2 px-3">Parent Invoice</th>
                          <th className="py-2 px-3">Item Description</th>
                          <th className="py-2 px-3 text-center">Qty</th>
                          <th className="py-2 px-3 text-right">Unit Rate</th>
                          <th className="py-2 px-3 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#313131] text-gray-300">
                        {purchaseTableRows.map((item, idx) => (
                          <tr key={`${item.invoice_id}-${idx}`} className="hover:bg-[#292929]">
                            <td className="py-2 px-3 font-mono text-purple-300">{item.invoice_id}</td>
                            <td className="py-2 px-3 text-white">{item.name}</td>
                            <td className="py-2 px-3 text-center">{item.quantity}</td>
                            <td className="py-2 px-3 text-right font-mono">₹{Number(item.rate || 0).toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-purple-200">₹{Number(item.total || 0).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-3 bg-[#242424] border-t border-[#303030] flex items-center justify-between text-xs text-gray-400">
              <span className="font-mono">
                Total Volume: ₹
                {invoiceTableRows
                  .reduce((a, b) => a + Number(b.total_amount || 0), 0)
                  .toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
              <button
                onClick={() => setErpModalOpen(false)}
                className="px-4 py-1.5 bg-[#3a3a3a] hover:bg-[#484848] text-white rounded-lg transition-colors font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
