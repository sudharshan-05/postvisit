"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Bot,
  Send,
  Sparkles,
  Database,
  FileCheck,
  BookOpen,
  Brain,
  Mic,
  AlertCircle,
  RotateCcw,
  Languages,
} from "lucide-react";
import { doctorApi } from "@/lib/api/doctor";
import { patientApi } from "@/lib/api/patient";
import { useAuth } from "@/lib/auth/context";
import { AskAIResponse, ChatMessage } from "@/types";
import { AudioRecorder } from "@/components/clinical/AudioRecorder";
import { toast } from "sonner";

interface AskAIDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  consultationId?: string;
  patientId?: string;
  defaultContext?: string;
  initialQuestion?: string;
  initialPrompt?: string;
}

export function AskAIDrawer({
  isOpen,
  onClose,
  consultationId = "default-consultation",
  patientId,
  defaultContext = "all",
  initialQuestion,
  initialPrompt,
}: AskAIDrawerProps) {
  const { role } = useAuth();
  const effectiveInitialPrompt = initialQuestion || initialPrompt;

  const [query, setQuery] = useState("");
  const [activeContext, setActiveContext] = useState<string>(defaultContext);
  const [language, setLanguage] = useState<"en" | "ta">("en");
  const [loading, setLoading] = useState(false);
  const [showVoiceRecorder, setShowVoiceRecorder] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isPersisted, setIsPersisted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Load chat history or initialize welcome message
  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;

    async function loadHistory() {
      if (role === "patient") {
        try {
          const res = await patientApi.getChatHistory();
          if (mounted && res?.messages && res.messages.length > 0) {
            const loaded: ChatMessage[] = res.messages.map((m: any, idx: number) => ({
              id: m.id || `hist-${idx}-${Date.now()}`,
              role: m.role === "user" ? "user" : "assistant",
              content: m.content || m.text || m.message || "",
              createdAt: m.created_at || new Date().toISOString(),
              consultationId: m.consultation_id || consultationId,
              contextType: m.context_type || "all",
            }));
            setMessages(loaded);
            setIsPersisted(true);
            return;
          }
        } catch (e) {
          // Graceful fallback to session-only chat
        }
      }

      // Default welcome message if no history found
      if (mounted && messages.length === 0) {
        setMessages([
          {
            id: "welcome-1",
            role: "assistant",
            content:
              role === "doctor"
                ? "Hello Dr. Ramanathan. I am your grounded clinical copilot. How can I assist with this encounter?"
                : "Hello! I can explain your doctor-approved visit instructions, medicines, and recommended follow-up in clear language. How can I help?",
            createdAt: new Date().toISOString(),
            consultationId,
            contextType: defaultContext,
          },
        ]);
        setIsPersisted(false);
      }
    }

    loadHistory();

    return () => {
      mounted = false;
    };
  }, [isOpen, role, consultationId, defaultContext]);

  // Handle initial contextual prompt if provided
  useEffect(() => {
    if (isOpen && effectiveInitialPrompt && effectiveInitialPrompt.trim().length > 0) {
      handleSend(effectiveInitialPrompt);
    }
  }, [isOpen, effectiveInitialPrompt]);


  if (!isOpen) return null;

  const handleSend = async (messageToSend?: string) => {
    const q = (messageToSend || query).trim();
    if (!q || loading) return;

    const userMsgId = `user-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      role: "user",
      content: q,
      createdAt: new Date().toISOString(),
      consultationId,
      contextType: activeContext,
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setLoading(true);

    try {
      let res: AskAIResponse;
      if (role === "doctor") {
        res = await doctorApi.askAI(consultationId, q, activeContext);
      } else {
        res = await patientApi.chat(q, consultationId, activeContext, language);
      }

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: res.answer || "Clinical response received.",
        createdAt: new Date().toISOString(),
        consultationId,
        contextType: activeContext,
        data: res,
        disclaimer: res.safety_disclaimer,
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errAssistantMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: "PostVisit AI couldn't answer this question right now.",
        createdAt: new Date().toISOString(),
        consultationId,
        contextType: activeContext,
        isError: true,
      };
      setMessages((prev) => [...prev, errAssistantMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = (originalIndex: number) => {
    // Find the nearest preceding user message
    let queryToRetry = "";
    for (let i = originalIndex - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        queryToRetry = messages[i].content;
        break;
      }
    }
    if (queryToRetry) {
      handleSend(queryToRetry);
    }
  };

  const quickPrompts =
    role === "doctor"
      ? [
          "Explain medication justification",
          "Check ICMR guideline evidence",
          "Review follow-up & red flags",
          "Summarize patient symptoms",
        ]
      : [
          "When should I take my medicines?",
          "What tests did the doctor recommend?",
          "What foods should I avoid?",
          "When is my follow-up appointment?",
        ];

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-2xl border-l border-[#E3ECE9] transition-all">
      {/* Header */}
      <div className="flex h-16 items-center justify-between border-b border-[#E3ECE9] px-5 bg-[#F7F9F8]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#123B35] text-white">
            <Sparkles className="h-4 w-4 text-[#0D9488]" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-[#172B28]">PostVisit AI Assistant</h3>
            <p className="text-[10px] text-[#5F736F]">
              {isPersisted ? "Conversation History Active" : "Session Clinical Conversation"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {role === "patient" && (
            <button
              onClick={() => setLanguage(language === "en" ? "ta" : "en")}
              className="flex items-center gap-1 rounded-lg border border-[#E3ECE9] bg-white px-2 py-1 text-[10px] font-semibold text-[#123B35] hover:border-[#0D9488] transition"
              title="Toggle language"
            >
              <Languages className="h-3 w-3 text-[#0D9488]" />
              <span>{language === "en" ? "EN" : "தமிழ்"}</span>
            </button>
          )}

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#E3ECE9] transition"
            aria-label="Close Assistant"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Context Pillars Header (Doctor Requirement) */}
      {role === "doctor" && (
        <div className="border-b border-[#E3ECE9] bg-white p-3">
          <span className="text-[10px] font-semibold text-[#5F736F] uppercase tracking-wider block mb-1.5">
            Active Context Scope:
          </span>
          <div className="grid grid-cols-4 gap-1">
            <button
              onClick={() => setActiveContext("source")}
              className={`flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[10px] font-medium border transition ${
                activeContext === "source"
                  ? "border-[#0D9488] bg-[#E7F5F1] text-[#123B35]"
                  : "border-[#E3ECE9] bg-[#F7F9F8] text-[#5F736F]"
              }`}
            >
              <Database className="h-3 w-3" />
              Source
            </button>
            <button
              onClick={() => setActiveContext("summary")}
              className={`flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[10px] font-medium border transition ${
                activeContext === "summary"
                  ? "border-[#0D9488] bg-[#E7F5F1] text-[#123B35]"
                  : "border-[#E3ECE9] bg-[#F7F9F8] text-[#5F736F]"
              }`}
            >
              <FileCheck className="h-3 w-3" />
              Summary
            </button>
            <button
              onClick={() => setActiveContext("guidelines")}
              className={`flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[10px] font-medium border transition ${
                activeContext === "guidelines"
                  ? "border-[#0D9488] bg-[#E7F5F1] text-[#123B35]"
                  : "border-[#E3ECE9] bg-[#F7F9F8] text-[#5F736F]"
              }`}
            >
              <BookOpen className="h-3 w-3" />
              Guidelines
            </button>
            <button
              onClick={() => setActiveContext("all")}
              className={`flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[10px] font-medium border transition ${
                activeContext === "all"
                  ? "border-[#0D9488] bg-[#E7F5F1] text-[#123B35]"
                  : "border-[#E3ECE9] bg-[#F7F9F8] text-[#5F736F]"
              }`}
            >
              <Brain className="h-3 w-3" />
              All Context
            </button>
          </div>
        </div>
      )}

      {/* Voice Recorder Drawer Mode */}
      {showVoiceRecorder && (
        <div className="p-3 border-b border-[#E3ECE9] bg-[#F7F9F8]">
          <AudioRecorder
            mode={role === "doctor" ? "doctor_note" : "patient_question"}
            consultationId={consultationId}
            onTranscriptionSuccess={(transcript) => {
              setShowVoiceRecorder(false);
              handleSend(transcript);
            }}
            onClose={() => setShowVoiceRecorder(false)}
          />
        </div>
      )}

      {/* Multi-Message Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={msg.id || i}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed ${
                msg.role === "user"
                  ? "bg-[#123B35] text-white"
                  : msg.isError
                  ? "bg-[#FEF2F2] text-[#991B1B] border border-[#FECACA]"
                  : "bg-[#F7F9F8] text-[#172B28] border border-[#E3ECE9]"
              }`}
            >
              {msg.isError ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 font-medium">
                    <AlertCircle className="h-3.5 w-3.5 text-red-600" />
                    <span>{msg.content}</span>
                  </div>
                  <button
                    onClick={() => handleRetry(i)}
                    className="flex items-center gap-1 text-[11px] font-bold text-red-700 underline hover:text-red-900"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Retry this question
                  </button>
                </div>
              ) : (
                msg.content
              )}

              {/* Categorized response layers for doctors */}
              {msg.data && role === "doctor" && (
                <div className="mt-2.5 pt-2 border-t border-[#E3ECE9] space-y-1.5 text-[11px]">
                  {msg.data.guideline_evidence && (
                    <div className="rounded bg-[#E7F5F1] p-1.5 text-[#123B35]">
                      <span className="font-bold">Guideline Evidence:</span>{" "}
                      {msg.data.guideline_evidence}
                    </div>
                  )}
                  {msg.data.ai_interpretation && (
                    <div className="text-[#5F736F] italic">
                      <span className="font-semibold text-[#172B28]">Interpretation:</span>{" "}
                      {msg.data.ai_interpretation}
                    </div>
                  )}
                </div>
              )}

              {/* Patient Safety Disclaimer */}
              {msg.disclaimer && (
                <div className="mt-2 pt-1.5 border-t border-[#E3ECE9] text-[10px] text-[#5F736F] italic">
                  {msg.disclaimer}
                </div>
              )}
            </div>
            <span className="text-[10px] text-[#5F736F] mt-1 px-1">
              {msg.role === "user" ? "You" : "PostVisit AI"}
            </span>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 rounded-2xl bg-[#F7F9F8] p-3 text-xs text-[#5F736F] border border-[#E3ECE9] w-fit">
            <Sparkles className="h-3.5 w-3.5 animate-spin text-[#0D9488]" />
            Synthesizing clinical response...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts */}
      <div className="p-3 border-t border-[#E3ECE9] bg-[#F7F9F8]">
        <div className="flex flex-wrap gap-1.5 mb-2">
          {quickPrompts.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(prompt)}
              className="rounded-full border border-[#E3ECE9] bg-white px-2.5 py-1 text-[11px] text-[#5F736F] hover:border-[#0D9488] hover:text-[#0D9488] transition shadow-2xs"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowVoiceRecorder(!showVoiceRecorder)}
            className={`flex h-8 w-8 items-center justify-center rounded-xl border transition ${
              showVoiceRecorder
                ? "bg-red-50 border-red-300 text-red-600"
                : "bg-white border-[#E3ECE9] text-[#5F736F] hover:text-[#0D9488]"
            }`}
            title="Ask by Voice"
            aria-label="Ask by Voice"
          >
            <Mic className="h-4 w-4" />
          </button>

          <input
            type="text"
            placeholder={
              role === "doctor"
                ? "Ask about symptoms, medicines, guidelines..."
                : language === "ta"
                ? "உங்கள் வருகை பற்றி கேள்வி கேளுங்கள்..."
                : "Ask a question about your visit..."
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            className="flex-1 rounded-xl border border-[#E3ECE9] bg-white py-2 px-3 text-xs text-[#172B28] placeholder-[#5F736F] focus:border-[#0D9488] focus:outline-none"
          />
          <button
            onClick={() => handleSend()}
            disabled={!query.trim() || loading}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#0D9488] text-white disabled:opacity-50 hover:bg-[#0F766E] transition"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

