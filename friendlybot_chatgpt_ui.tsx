import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Plus, Search, Trash2, Database, FileText, Upload,
  Paperclip, Mic, MicOff, Send, Copy, Check, ThumbsUp, ThumbsDown,
  Volume2, RefreshCw, ChevronDown, ChevronRight, Settings, ExternalLink,
  Eye, FileCheck, Layers, Cpu, ShieldCheck, Sparkles, AlertCircle,
  FileCode, X, ArrowUpRight, CheckCircle2, Clock, Globe, ArrowRight,
  TrendingUp, Download, Table, BookOpen, HardDrive, HelpCircle
} from 'lucide-react';

const INITIAL_INVOICES = [
  {
    invoice_id: "INV_10001",
    vendor: "Kalyan Electronics Pvt Ltd",
    invoice_number: "KE/2026/8942",
    date: "2026-03-24",
    currency: "INR (₹)",
    subtotal: 45200.00,
    cgst: 4068.00,
    sgst: 4068.00,
    tax: 8136.00,
    total_amount: 53336.00,
    confidence: 0.984,
    erp_synced: true,
    erp_reference: "ERP-SYNC-89211",
    items: [
      { sr_no: 1, name: "Dell 27-inch 4K Monitor S2722QC", qty: 2, rate: 18500.00, total: 37000.00 },
      { sr_no: 2, name: "Logitech MX Master 3S Wireless Mouse", qty: 1, rate: 8200.00, total: 8200.00 }
    ],
    ocr_raw: "KALYAN ELECTRONICS PVT LTD\nGSTIN: 32AABCK9871P1Z9\nInvoice KE/2026/8942 Date: 24-03-2026\nDell 27 Monitor x2 @ 18500 = 37000\nLogitech MX Master 3S x1 @ 8200 = 8200\nSubtotal: 45,200.00 | CGST 9%: 4,068.00 | SGST 9%: 4,068.00 | Total: 53,336.00"
  },
  {
    invoice_id: "INV_10002",
    vendor: "Apex Cloud Services LLP",
    invoice_number: "ACS-INV-1104",
    date: "2026-03-27",
    currency: "INR (₹)",
    subtotal: 12400.00,
    cgst: 1116.00,
    sgst: 1116.00,
    tax: 2232.00,
    total_amount: 14632.00,
    confidence: 0.962,
    erp_synced: true,
    erp_reference: "ERP-SYNC-91024",
    items: [
      { sr_no: 1, name: "Compute Engine Standard N2 Tier (Monthly)", qty: 1, rate: 9400.00, total: 9400.00 },
      { sr_no: 2, name: "Dedicated Persistent NVMe Storage 500GB", qty: 1, rate: 3000.00, total: 3000.00 }
    ],
    ocr_raw: "Apex Cloud Services LLP\nTax Invoice: ACS-INV-1104 Date: 27/03/2026\nItem 1: Cloud Compute N2 1 qty 9400.00\nItem 2: Persistent Storage 500GB 1 qty 3000.00\nGST 18% Total Tax: 2232.00\nTotal Due: 14,632.00 INR"
  }
];

const INITIAL_RAG_DOCS = [
  { id: "doc-1", name: "Procurement_Policy_2026.pdf", chunks: 24, size: "1.4 MB", uploadedAt: "Yesterday" },
  { id: "doc-2", name: "Vendor_GST_Compliance_Guide.docx", chunks: 18, size: "840 KB", uploadedAt: "3 days ago" },
  { id: "doc-3", name: "Malayalam_Expense_Glossary.md", chunks: 9, size: "120 KB", uploadedAt: "1 week ago" }
];

export default function App() {
  // Navigation & Sessions
  const [chats, setChats] = useState([
    {
      id: "session-1",
      title: "Invoice KE/2026/8942 Extraction",
      timeCategory: "Today",
      messages: [
        {
          id: "m-init-1",
          role: "assistant",
          content: "Hello there! I'm **Avi**, your document intelligence companion. You can upload invoices, ask questions about your uploaded PDFs, request translations, or test ERP sync. How can I help your workflow today?",
          meta: { latency: 120 }
        }
      ]
    },
    {
      id: "session-2",
      title: "Malayalam GST Policy Query",
      timeCategory: "Yesterday",
      messages: [
        {
          id: "m-old-1",
          role: "user",
          content: "നമസ്കാരം! നമ്മുടെ പർച്ചേസ് പോളിസി പ്രകാരം പരമാവധി അപ്രൂവൽ ലിമിറ്റ് എത്രയാണ്?"
        },
        {
          id: "m-old-2",
          role: "assistant",
          content: "നമസ്കാരം! 'Procurement_Policy_2026.pdf' പ്രകാരം ലെവൽ 1 മാനേജർമാർക്ക് ₹50,000 വരെയുള്ള ഇൻവോയ്സുകൾ അപ്രൂവ് ചെയ്യാം. ഇതിന് മുകളിലുള്ള തുകയ്ക്ക് ഫിനാൻസ് ഹെഡിന്റെ പ്രത്യേക അനുമതി ആവശ്യമാണ്.\n\n*(Detected Language: Malayalam | Grounded via ChromaDB RAG chunk #4)*",
          meta: { latency: 310, ragHit: true }
        }
      ]
    },
    {
      id: "session-3",
      title: "OpenRouter Llama 4 Benchmark",
      timeCategory: "Previous 7 days",
      messages: []
    }
  ]);

  const [activeChatId, setActiveChatId] = useState("session-1");
  const [model, setModel] = useState("gemini-2.5-flash"); // or "openrouter/llama-4-maverick"
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);

  // Composer State
  const [inputPrompt, setInputPrompt] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Features Drawers & Modals
  const [erpModalOpen, setErpModalOpen] = useState(false);
  const [ragDrawerOpen, setRagDrawerOpen] = useState(false);
  const [invoices, setInvoices] = useState(INITIAL_INVOICES);
  const [ragDocs, setRagDocs] = useState(INITIAL_RAG_DOCS);
  const [debugOcrModal, setDebugOcrModal] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  // Audio Simulation state
  const [audioTimer, setAudioTimer] = useState(0);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  const activeChat = chats.find(c => c.id === activeChatId) || chats[0];

  // Auto-scroll on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChat?.messages, isSubmitting]);

  // Audio recording simulation timer
  useEffect(() => {
    let interval;
    if (isRecording) {
      interval = setInterval(() => setAudioTimer(t => t + 1), 1000);
    } else {
      setAudioTimer(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  const handleTextareaChange = (e) => {
    setInputPrompt(e.target.value);
    // Auto grow
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSpeechSimulation = (text) => {
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
    const newChat = {
      id: newId,
      title: "New conversation",
      timeCategory: "Today",
      messages: [
        {
          id: `m-${Date.now()}`,
          role: "assistant",
          content: "Hi, I'm **Avi**! I can parse multi-format invoices with OCR, extract GST and line items, sync directly with your ERP, or query your internal documents with RAG. Try uploading an invoice or typing a question in Hindi, Malayalam, Manglish, or English!",
          meta: { latency: 95 }
        }
      ]
    };
    setChats([newChat, ...chats]);
    setActiveChatId(newId);
  };

  const deleteChat = (e, id) => {
    e.stopPropagation();
    const remaining = chats.filter(c => c.id !== id);
    if (remaining.length === 0) {
      createNewChat();
    } else {
      setChats(remaining);
      if (activeChatId === id) {
        setActiveChatId(remaining[0].id);
      }
    }
  };

  const handleFileUpload = (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;

    const newAttachments = files.map(file => ({
      name: file.name,
      size: (file.size / 1024).toFixed(1) + " KB",
      type: file.type.includes('image') ? 'image' : file.type.includes('pdf') ? 'pdf' : 'document'
    }));

    setAttachedFiles(prev => [...prev, ...newAttachments]);
    e.target.value = '';
  };

  const removeAttachment = (index) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmitMessage = async (customPrompt = null, forcedAttachments = null) => {
    const promptToSend = customPrompt || inputPrompt;
    const filesToSend = forcedAttachments || attachedFiles;

    if (!promptToSend.trim() && filesToSend.length === 0) return;

    const userMessageId = `u-${Date.now()}`;
    const newUserMessage = {
      id: userMessageId,
      role: "user",
      content: promptToSend,
      attachments: [...filesToSend]
    };

    // Update session with user message
    const updatedChats = chats.map(chat => {
      if (chat.id === activeChatId) {
        return {
          ...chat,
          title: chat.messages.length <= 1 ? (promptToSend.slice(0, 28) || "Document Intelligence") : chat.title,
          messages: [...chat.messages, newUserMessage]
        };
      }
      return chat;
    });

    setChats(updatedChats);
    setInputPrompt("");
    setAttachedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setIsSubmitting(true);

    // Simulate Network Latency
    const simulatedLatency = Math.floor(Math.random() * 450) + 380;
    await new Promise(r => setTimeout(r, simulatedLatency));

    // Intelligence routing logic
    const lower = promptToSend.toLowerCase();
    const hasImage = filesToSend.some(f => f.type === 'image') || lower.includes("invoice") || lower.includes("bill") || lower.includes("receipt");
    const isMalayalam = /[\u0D00-\u0D7F]/.test(promptToSend);
    const isHindi = /[\u0900-\u097F]/.test(promptToSend);
    const isTranslation = lower.includes("translate") || lower.includes("വിവർത്തനം") || lower.includes("अनुवाद");
    const isRag = lower.includes("policy") || lower.includes("guide") || lower.includes("rule") || lower.includes("limit") || lower.includes("rag");

    let botResponse = {};

    if (hasImage) {
      // INVOICE OCR & ERP PIPELINE
      const nextInvNum = invoices.length + 10001;
      const invId = `INV_${nextInvNum}`;
      const newInvoiceObj = {
        invoice_id: invId,
        vendor: "TechnoWorld Hardware Solutions",
        invoice_number: `TW/2026/0${Math.floor(Math.random() * 899 + 100)}`,
        date: "2026-03-28",
        currency: "INR (₹)",
        subtotal: 28900.00,
        cgst: 2601.00,
        sgst: 2601.00,
        tax: 5202.00,
        total_amount: 34102.00,
        confidence: 0.988,
        erp_synced: true,
        erp_reference: `ERP-SYNC-${Math.floor(Math.random() * 90000 + 10000)}`,
        items: [
          { sr_no: 1, name: "Crucial Pro 64GB DDR5 RAM Kit (32GBx2)", qty: 2, rate: 10450.00, total: 20900.00 },
          { sr_no: 2, name: "Samsung 990 Pro 2TB PCIe 4.0 NVMe SSD", qty: 1, rate: 8000.00, total: 8000.00 }
        ],
        ocr_raw: `TECHNOWORLD HARDWARE SOLUTIONS\nGSTIN: 29AAGCB1293Q1Z2\nTax Invoice: TW/2026/0412 | Date: 28/03/2026\nDescription: Crucial Pro 64GB DDR5 RAM x2 @ 10,450.00 = 20,900.00\nDescription: Samsung 990 Pro 2TB SSD x1 @ 8,000.00 = 8,000.00\nSub Total: 28,900.00\nCGST @ 9%: 2,601.00\nSGST @ 9%: 2,601.00\nGrand Total: 34,102.00 INR\nStatus: Verified via Dual Vision OCR Engine`
      };

      // Push to our mock DB
      setInvoices(prev => [newInvoiceObj, ...prev]);

      let intro = "I've processed your invoice through the **Vision OCR & Parsing Pipeline**! The data has been validated, verified against template spoofing, and stored in the SQLite ledger with automatic ERP synchronisation.";
      if (isMalayalam) {
        intro = "തീർച്ചയായും! നിങ്ങളുടെ ഇൻവോയ്സ് സ്കാൻ ചെയ്ത് കൃത്യമായ വിവരങ്ങൾ പുറത്തെടുത്തിട്ടുണ്ട്. GST കണക്കുകൂട്ടലുകൾ പരിശോധിച്ച ശേഷം Mock ERP സിസ്റ്റത്തിലേക്ക് അപ്‌ലോഡ് ചെയ്തു.";
      } else if (isHindi) {
        intro = "मैंने आपका इनवॉइस सफलतापूर्वक स्कैन कर लिया है! GST विवरण और लाइन आइटम्स को वेरीफाई करके Mock ERP डेटाबेस में सिंक कर दिया गया है।";
      }

      botResponse = {
        id: `m-${Date.now()}`,
        role: "assistant",
        content: intro,
        meta: {
          latency: simulatedLatency + 240,
          confidence: 0.988,
          erpStatus: "Synced",
          modelUsed: model,
          invoiceData: newInvoiceObj,
          intent: "invoice_extraction"
        }
      };

    } else if (isTranslation) {
      let translationResult = "";
      if (isMalayalam) {
        translationResult = "**Translation (Malayalam ➔ English):**\n\n> *\"Greetings! Please verify whether this purchase order has been approved according to company standards.\"*\n\n**Confidence:** 99.2% | Detected Script: Malayalam Unicode";
      } else if (isHindi) {
        translationResult = "**Translation (Hindi ➔ English):**\n\n> *\"Please verify the payment status of the previous invoice immediately.\"*\n\n**Confidence:** 98.9% | Detected Script: Devanagari";
      } else {
        translationResult = "**Translation (English ➔ Malayalam / Hindi):**\n\n- **Malayalam:** ഈ മാസത്തെ എല്ലാ ഇൻവോയ്സുകളും വിജയകരമായി സമന്വയിപ്പിച്ചു.\n- **Hindi:** इस महीने के सभी इनवॉइस सफलतापूर्वक सिंक कर दिए गए हैं।\n\n*(Handled via Avi Multilingual Text Engine)*";
      }

      botResponse = {
        id: `m-${Date.now()}`,
        role: "assistant",
        content: `Here is the requested translation:\n\n${translationResult}`,
        meta: { latency: simulatedLatency, modelUsed: model, intent: "translation" }
      };

    } else if (isRag) {
      botResponse = {
        id: `m-${Date.now()}`,
        role: "assistant",
        content: `Based on your indexed RAG document knowledge base (**Procurement_Policy_2026.pdf**):\n\n1. **Standard Approval Limit**: Single invoices up to **₹50,000** can be approved directly by Team Leads.\n2. **GST Compliance Check**: Invoices above ₹25,000 must include mandatory HSN/SAC codes and verified 2B reconciliation.\n3. **ERP Posting**: Automatic ERP sync triggers only after confidence threshold $(\\ge 0.95)$ is reached.\n\n*Retrieved from 2 vector chunks using ChromaDB similarity index (cosine distance: 0.142).*`,
        meta: { latency: simulatedLatency + 110, ragHit: true, modelUsed: model, intent: "rag_qa" }
      };

    } else {
      // Standard Conversational Avi Persona
      let reply = `I'm here to streamline your document workflow! I can extract line items from supplier bills, manage GST numbers, verify mock ERP entries, or answer questions about your uploaded vendor manuals.\n\nTry clicking one of the sample prompt chips below or upload a photo of a bill!`;
      if (isMalayalam) {
        reply = `നമസ്കാരം! ഞാൻ അവി (Avi). നിങ്ങൾക്ക് ഇൻവോയ്സ് പ്രോസസ്സിംഗ്, RAG ഡോക്യുമെന്റ് തിരച്ചിൽ, അല്ലെങ്കിൽ മലയാളം/മംഗ്ലീഷ് ഭാഷാ സഹായങ്ങൾ എന്നിവയിൽ എന്നെ ഉപയോഗിക്കാം. എന്താണ് ഇന്ന് ചെയ്യേണ്ടത്?`;
      } else if (isHindi) {
        reply = `नमस्ते! मैं 'अवि' (Avi) हूँ। आप मुझसे इनवॉइस एक्सट्रैक्शन, GST कैलकुलेशन या किसी भी पीडीएफ डाक्यूमेंट्स से जुड़े सवाल पूछ सकते हैं। आप कैसे आगे बढ़ना चाहेंगे?`;
      }

      botResponse = {
        id: `m-${Date.now()}`,
        role: "assistant",
        content: reply,
        meta: { latency: simulatedLatency, modelUsed: model, intent: "general_chat" }
      };
    }

    setChats(prev => prev.map(chat => {
      if (chat.id === activeChatId) {
        return {
          ...chat,
          messages: [...chat.messages, botResponse]
        };
      }
      return chat;
    }));

    setIsSubmitting(false);
  };

  const handleQuickPrompt = (promptText) => {
    handleSubmitMessage(promptText);
  };

  const triggerSampleInvoiceUpload = () => {
    const sampleAttachment = [{
      name: "sample_vendor_invoice_tech.png",
      size: "420.5 KB",
      type: "image"
    }];
    handleSubmitMessage("Please extract this invoice, check GST calculations, and push to ERP.", sampleAttachment);
  };

  return (
    <div className="flex h-screen w-screen bg-[#212121] text-gray-100 font-sans overflow-hidden antialiased select-none">
      
      {}
      <aside
        className={`${
          sidebarOpen ? 'w-[260px]' : 'w-0'
        } transition-all duration-300 ease-in-out bg-[#171717] border-r border-[#2f2f2f] flex flex-col z-30 shrink-0 relative overflow-hidden`}
      >
        <div className="p-3 flex flex-col h-full justify-between w-[260px]">
          {/* Top Actions: New Chat & FriendlyBot Header */}
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

            {/* New Chat Button */}
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

            {/* Knowledge Base & ERP Fast Access Buttons */}
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

          {/* Chat History List */}
          <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-4 text-xs scrollbar-thin scrollbar-thumb-[#333]">
            {['Today', 'Yesterday', 'Previous 7 days'].map(group => {
              const groupChats = chats.filter(c => c.timeCategory === group);
              if (!groupChats.length) return null;
              return (
                <div key={group} className="space-y-1">
                  <div className="px-2 text-[11px] font-semibold text-gray-400 tracking-wider">
                    {group}
                  </div>
                  {groupChats.map(c => (
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
                        <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${activeChatId === c.id ? 'text-purple-400' : 'text-gray-400'}`} />
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

          {/* User Profile Pill & System Status */}
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

      {}
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

            {/* Model Selector Pill (ChatGPT Style) */}
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
                <div className="absolute left-0 mt-2 w-64 bg-[#262626] border border-[#383838] rounded-xl shadow-2xl py-1 z-50 animate-in fade-in zoom-in-95">
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

            {/* RAG Status Indicator */}
            <div
              onClick={() => setRagDrawerOpen(true)}
              className="cursor-pointer hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-700/50 text-[11px] font-medium text-emerald-300 hover:bg-emerald-900/60 transition-colors"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>RAG Active ({ragDocs.length} Docs)</span>
            </div>
          </div>

          {/* Right Header Status Bar */}
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
              <span className="bg-purple-500/40 px-1 rounded text-[10px]">{invoices.length}</span>
            </button>
          </div>
        </header>

        {}
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

                {/* Quick Capability Cards / Suggestions */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full mt-8 text-left">
                  <div
                    onClick={triggerSampleInvoiceUpload}
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
                    onClick={() => handleQuickPrompt("What are the invoice approval limits as per Procurement_Policy_2026.pdf?")}
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
                    onClick={() => handleQuickPrompt("നമസ്കാരം! ഈ മാസത്തെ ഇൻവോയ്സുകൾ ചെക്ക് ചെയ്യാൻ സഹായിക്കാമോ?")}
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

            {/* Conversational Stream List */}
            {activeChat.messages.map((message) => {
              const isAssistant = message.role === "assistant";
              return (
                <div
                  key={message.id}
                  className={`flex gap-4 ${isAssistant ? 'justify-start' : 'justify-end'}`}
                >
                  {isAssistant && (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center font-bold text-white text-xs shrink-0 shadow-md">
                      A
                    </div>
                  )}

                  <div className={`flex flex-col space-y-2 max-w-[88%] ${!isAssistant ? 'items-end' : 'items-start'}`}>
                    {/* User Attached File Previews */}
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

                    {/* Chat Bubble Box */}
                    <div
                      className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                        isAssistant
                          ? 'bg-[#2a2a2a] text-gray-100 border border-[#363636] shadow-sm'
                          : 'bg-purple-600 text-white rounded-br-sm'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{message.content}</div>

                      {}
                      {message.meta?.invoiceData && (
                        <div className="mt-4 pt-3 border-t border-[#3e3e3e] space-y-3">
                          <div className="flex items-center justify-between flex-wrap gap-2">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-purple-900/80 text-purple-300 border border-purple-700/60">
                                {message.meta.invoiceData.invoice_id}
                              </span>
                              <span className="font-semibold text-xs text-white">
                                {message.meta.invoiceData.vendor}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                                <CheckCircle2 className="w-3 h-3" />
                                {message.meta.invoiceData.erp_reference}
                              </span>
                              <span className="text-[11px] text-gray-400 font-mono">
                                Conf: {(message.meta.confidence * 100).toFixed(1)}%
                              </span>
                            </div>
                          </div>

                          {/* Line items table */}
                          <div className="overflow-x-auto rounded-lg border border-[#383838] bg-[#212121]">
                            <table className="w-full text-left text-xs">
                              <thead className="bg-[#282828] text-gray-400 font-semibold border-b border-[#383838]">
                                <tr>
                                  <th className="py-2 px-3">Item Description</th>
                                  <th className="py-2 px-3 text-center">Qty</th>
                                  <th className="py-2 px-3 text-right">Rate</th>
                                  <th className="py-2 px-3 text-right">Total</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-[#2c2c2c] text-gray-300">
                                {message.meta.invoiceData.items.map((it, idx) => (
                                  <tr key={idx} className="hover:bg-[#272727]/50">
                                    <td className="py-2 px-3 font-medium text-white">{it.name}</td>
                                    <td className="py-2 px-3 text-center">{it.qty}</td>
                                    <td className="py-2 px-3 text-right">₹{it.rate.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                                    <td className="py-2 px-3 text-right font-medium text-purple-300">₹{it.total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          {/* Financial Summary Breakdown */}
                          <div className="flex justify-between items-end bg-[#252525] p-3 rounded-lg border border-[#353535]">
                            <div className="text-xs space-y-1 text-gray-400 font-mono">
                              <div>Invoice No: <span className="text-gray-200">{message.meta.invoiceData.invoice_number}</span></div>
                              <div>Date: <span className="text-gray-200">{message.meta.invoiceData.date}</span></div>
                              <div>GST Split: <span className="text-purple-300">CGST ₹{message.meta.invoiceData.cgst} + SGST ₹{message.meta.invoiceData.sgst}</span></div>
                            </div>
                            <div className="text-right">
                              <div className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">Total Amount</div>
                              <div className="text-base font-bold text-white text-emerald-400 font-mono">
                                ₹{message.meta.invoiceData.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </div>
                            </div>
                          </div>

                          {/* OCR Inspect Button */}
                          <div className="flex items-center justify-between pt-1 text-xs">
                            <button
                              onClick={() => setDebugOcrModal(message.meta.invoiceData)}
                              className="flex items-center gap-1.5 text-gray-400 hover:text-purple-300 transition-colors text-xs font-mono underline"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              Inspect Raw OCR & Bounding Tokens
                            </button>
                            <span className="text-[10px] text-gray-500">Auto-assigned ID: {message.meta.invoiceData.invoice_id}</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Assistant Response Meta Actions (Copy, TTS, Feedback, Latency) */}
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

                        {message.meta?.latency && (
                          <span className="text-[10px] font-mono text-gray-400 ml-1">
                            {message.meta.latency}ms
                          </span>
                        )}
                        {message.meta?.ragHit && (
                          <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800/80 px-1.5 py-0.2 rounded font-mono">
                            ChromaDB RAG
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Is Typing / Submitting state indicator */}
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

        {}
        <div className="w-full bg-[#212121] px-4 pb-4 pt-2">
          <div className="max-w-3xl mx-auto">
            {/* Attachment preview pills before sending */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2 p-2 bg-[#262626] rounded-xl border border-[#383838]">
                {attachedFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#333] text-xs text-gray-200 border border-[#444]"
                  >
                    <FileText className="w-3.5 h-3.5 text-purple-400" />
                    <span className="max-w-[140px] truncate">{file.name}</span>
                    <button
                      onClick={() => removeAttachment(idx)}
                      className="hover:text-red-400 p-0.5 rounded"
                    >
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

              {/* Bottom Toolbar inside the Composer */}
              <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  {/* Hidden File Input */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    multiple
                    accept="image/*,.pdf,.docx,.txt,.md"
                    className="hidden"
                  />

                  {/* Plus / Upload Button */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="p-1.5 rounded-full text-gray-400 hover:text-white hover:bg-[#3d3d3d] transition-colors"
                    title="Attach invoice, image, receipt, or RAG document"
                  >
                    <Paperclip className="w-4 h-4" />
                  </button>

                  {/* Preset invoice test helper */}
                  <button
                    type="button"
                    onClick={triggerSampleInvoiceUpload}
                    className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-full bg-[#383838] hover:bg-[#444] text-purple-300 border border-purple-800/40 transition-colors"
                  >
                    <FileCheck className="w-3 h-3" />
                    <span>Test Invoice</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {/* Audio Microphone Button */}
                  <button
                    type="button"
                    onClick={() => {
                      if (isRecording) {
                        setIsRecording(false);
                        setInputPrompt(prev => (prev ? prev + " " : "") + "ഇൻവോയ്സ് KE/2026/8942 സ്റ്റാറ്റസ് ചെക്ക് ചെയ്യുക.");
                      } else {
                        setIsRecording(true);
                      }
                    }}
                    className={`p-2 rounded-full transition-all ${
                      isRecording
                        ? 'bg-red-500 text-white animate-pulse'
                        : 'text-gray-400 hover:text-white hover:bg-[#3d3d3d]'
                    }`}
                    title={isRecording ? "Stop recording" : "Speech-to-text input"}
                  >
                    {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>

                  {/* Send Button */}
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

            {/* Disclaimer Footer */}
            <div className="text-center text-[11px] text-gray-400 mt-2">
              FriendlyBot Avi may verify extracted data against ERP standards. Check critical numbers.
            </div>
          </div>
        </div>
      </main>

      {}
      {ragDrawerOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in">
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
              <button
                onClick={() => setRagDrawerOpen(false)}
                className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-[#2b2b2b]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Ingest / Upload Area */}
            <div className="mt-4 p-4 rounded-xl border border-dashed border-[#444] bg-[#242424] text-center">
              <Upload className="w-6 h-6 text-purple-400 mx-auto mb-2" />
              <div className="text-xs font-semibold text-gray-200">Upload Knowledge Documents</div>
              <div className="text-[11px] text-gray-400 mt-0.5">Supports PDF, DOCX, TXT, MD (Max 20MB)</div>
              <button
                onClick={() => {
                  const newDoc = {
                    id: `doc-${Date.now()}`,
                    name: `Vendor_Agreement_Draft_${ragDocs.length + 1}.pdf`,
                    chunks: Math.floor(Math.random() * 15 + 8),
                    size: "950 KB",
                    uploadedAt: "Just now"
                  };
                  setRagDocs([newDoc, ...ragDocs]);
                }}
                className="mt-3 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium transition-colors"
              >
                + Ingest Sample PDF Document
              </button>
            </div>

            {/* Document List */}
            <div className="flex-1 overflow-y-auto mt-4 space-y-2 pr-1">
              <div className="flex items-center justify-between text-xs font-semibold text-gray-400 px-1">
                <span>Ingested Documents ({ragDocs.length})</span>
                {ragDocs.length > 0 && (
                  <button
                    onClick={() => setRagDocs([])}
                    className="text-red-400 hover:text-red-300 text-[11px]"
                  >
                    Clear All
                  </button>
                )}
              </div>

              {ragDocs.map(doc => (
                <div
                  key={doc.id}
                  className="p-3 rounded-xl bg-[#262626] border border-[#333] flex items-center justify-between group hover:border-[#444]"
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                    <div className="truncate">
                      <div className="text-xs font-medium text-gray-200 truncate">{doc.name}</div>
                      <div className="text-[10px] text-gray-400 flex items-center gap-2 mt-0.5 font-mono">
                        <span>{doc.chunks} vector chunks</span>
                        <span>•</span>
                        <span>{doc.size}</span>
                        <span>•</span>
                        <span>{doc.uploadedAt}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => setRagDocs(prev => prev.filter(d => d.id !== doc.id))}
                    className="p-1 text-gray-500 hover:text-red-400 opacity-60 group-hover:opacity-100 transition-opacity"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>

            <div className="pt-4 border-t border-[#2e2e2e]">
              <div className="text-[11px] text-gray-400 leading-normal">
                Documents are embedded and stored in ChromaDB for high-accuracy retrieval when answering vendor and policy questions.
              </div>
            </div>
          </div>
        </div>
      )}

      {}
      {erpModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-[#1f1f1f] border border-[#383838] w-full max-w-4xl max-h-[85vh] rounded-2xl flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-[#303030] flex items-center justify-between bg-[#242424]">
              <div className="flex items-center gap-2.5">
                <Database className="w-5 h-5 text-purple-400" />
                <div>
                  <h3 className="text-sm font-semibold text-white">Invoice Database & Mock ERP Ledger</h3>
                  <p className="text-[11px] text-gray-400 font-mono">Synchronized with sqlite:chatbot.db / mock_erp_submissions.json</p>
                </div>
              </div>
              <button
                onClick={() => setErpModalOpen(false)}
                className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-[#333]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Database Table */}
            <div className="p-4 flex-1 overflow-y-auto">
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
                      <th className="py-2.5 px-3 text-center">ERP Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#2d2d2d] text-gray-300">
                    {invoices.map(inv => (
                      <tr key={inv.invoice_id} className="hover:bg-[#262626] transition-colors">
                        <td className="py-2.5 px-3 font-mono font-bold text-purple-300">{inv.invoice_id}</td>
                        <td className="py-2.5 px-3 font-medium text-white">{inv.vendor}</td>
                        <td className="py-2.5 px-3 font-mono text-gray-400">{inv.invoice_number}</td>
                        <td className="py-2.5 px-3 font-mono">{inv.date}</td>
                        <td className="py-2.5 px-3 text-right font-mono">₹{inv.subtotal.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-amber-400">₹{inv.tax.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-400">₹{inv.total_amount.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-center">
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                            <CheckCircle2 className="w-3 h-3" />
                            {inv.erp_synced ? 'Synced' : 'Pending'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Purchase Item details overview */}
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
                      {invoices.flatMap(inv =>
                        inv.items.map((item, idx) => (
                          <tr key={`${inv.invoice_id}-${idx}`} className="hover:bg-[#292929]">
                            <td className="py-2 px-3 font-mono text-purple-300">{inv.invoice_id}</td>
                            <td className="py-2 px-3 text-white">{item.name}</td>
                            <td className="py-2 px-3 text-center">{item.qty}</td>
                            <td className="py-2 px-3 text-right font-mono">₹{item.rate.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-purple-200">₹{item.total.toFixed(2)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-3 bg-[#242424] border-t border-[#303030] flex items-center justify-between text-xs text-gray-400">
              <span className="font-mono">Total Synced Volume: ₹{invoices.reduce((a, b) => a + b.total_amount, 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
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

      {}
      {debugOcrModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-[#1c1c1c] border border-[#3b3b3b] w-full max-w-2xl rounded-2xl flex flex-col shadow-2xl overflow-hidden max-h-[80vh]">
            <div className="p-4 border-b border-[#303030] flex items-center justify-between bg-[#242424]">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold text-white">OCR Vision Pipeline Debug Inspector</h3>
              </div>
              <button
                onClick={() => setDebugOcrModal(null)}
                className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-[#333]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto space-y-4">
              <div>
                <div className="text-xs font-semibold text-gray-300 mb-1">OCR Raw Text Tokens Stream</div>
                <pre className="p-3 rounded-xl bg-[#141414] border border-[#2d2d2d] text-xs font-mono text-emerald-400 whitespace-pre-wrap leading-relaxed">
                  {debugOcrModal.ocr_raw}
                </pre>
              </div>

              <div>
                <div className="text-xs font-semibold text-gray-300 mb-1">Structured Extraction Object (Pipeline Output)</div>
                <pre className="p-3 rounded-xl bg-[#141414] border border-[#2d2d2d] text-xs font-mono text-purple-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                  {JSON.stringify(debugOcrModal, null, 2)}
                </pre>
              </div>
            </div>
            <div className="p-3 bg-[#242424] border-t border-[#303030] text-right">
              <button
                onClick={() => setDebugOcrModal(null)}
                className="px-3.5 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-medium"
              >
                Done Inspecting
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}