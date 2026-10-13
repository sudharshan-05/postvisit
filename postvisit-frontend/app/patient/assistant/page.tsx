"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Bot, Sparkles, Mic, AlertCircle, Languages, RotateCcw } from "lucide-react";
import { patientApi } from "@/lib/api/patient";
import { AudioRecorder } from "@/components/clinical/AudioRecorder";
import { ChatMessage } from "@/types";
import { toast } from "sonner";

export default function PatientAssistantPage() {
  const [query, setQuery] = useState("");
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

  // Load chat history or set initial greeting
  useEffect(() => {
    let mounted = true;

    async function loadHistory() {
      try {
        const res = await patientApi.getChatHistory();
        if (mounted && res?.messages && res.messages.length > 0) {
          const loaded: ChatMessage[] = res.messages.map((m: any, idx: number) => ({
            id: m.id || `hist-${idx}-${Date.now()}`,
            role: m.role === "user" ? "user" : "assistant",
            content: m.content || m.text || m.message || "",
            createdAt: m.created_at || new Date().toISOString(),
          }));
          setMessages(loaded);
          setIsPersisted(true);
          return;
        }
      } catch (e) {
        // Fallback to initial message
      }

      if (mounted && messages.length === 0) {
        setMessages([
          {
            id: "welcome-patient",
            role: "assistant",
            content:
              language === "ta"
                ? "வணக்கம்! நான் உங்கள் PostVisit AI உதவியாளர். உங்கள் மருந்துகள், மருத்துவரின் மீட்பு வழிமுறைகள் மற்றும் பரிந்துரைக்கப்பட்ட சோதனைகளை எளிய மொழியில் விளக்க முடியும்."
                : "Hello! I am your PostVisit AI assistant. I can explain your medicines, doctor's recovery instructions, and recommended tests in clear, simple language.",
            createdAt: new Date().toISOString(),
            disclaimer:
              "This assistant provides information directly grounded in your doctor-approved consultation record.",
          },
        ]);
        setIsPersisted(false);
      }
    }

    loadHistory();

    return () => {
      mounted = false;
    };
  }, [language]);

  const handleSend = async (textToSend?: string) => {
    const q = (textToSend || query).trim();
    if (!q || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: q,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setLoading(true);

    try {
      const res = await patientApi.chat(q, undefined, "all", language);
      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: res.answer || "Clinical response received.",
        createdAt: new Date().toISOString(),
        disclaimer: res.safety_disclaimer,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: "PostVisit AI couldn't answer this question right now.",
        createdAt: new Date().toISOString(),
        isError: true,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = (originalIndex: number) => {
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

  const sampleQuestions =
    language === "ta"
      ? [
          "எனது மருந்துகளை எப்போது எடுத்துக்கொள்ள வேண்டும்?",
          "மருத்துவர் என்ன உணவு முறைகளை பரிந்துரைத்தார்?",
          "எனது அடுத்த மருத்துவ சந்திப்பு எப்போது?",
          "வெறும் வயிற்றில் மருந்து சாப்பிடலாமா?",
        ]
      : [
          "When should I take my Metformin 500mg?",
          "What diet changes did Dr. Ramanathan recommend?",
          "When is my next follow-up appointment?",
          "Can I take my medicine on an empty stomach?",
        ];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header with Bilingual Toggle */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            AI Health Assistant
          </h2>
          <p className="text-xs text-[#5F736F]">
            {isPersisted
              ? "Your conversation history is saved and grounded in verified visit records."
              : "Ask questions about your prescribed medications, recovery plan, or diet instructions."}
          </p>
        </div>

        <button
          onClick={() => setLanguage(language === "en" ? "ta" : "en")}
          className="flex items-center gap-1.5 rounded-full border border-[#0D9488] bg-[#E7F5F1] px-3.5 py-1.5 text-xs font-semibold text-[#123B35] hover:bg-[#0D9488] hover:text-white transition"
        >
          <Languages className="h-3.5 w-3.5" />
          <span>{language === "en" ? "Switch to தமிழ் (Tamil)" : "Switch to English"}</span>
        </button>
      </div>

      {/* Voice Recorder drawer if active */}
      {showVoiceRecorder && (
        <AudioRecorder
          mode="patient_question"
          onTranscriptionSuccess={(transcript) => {
            setShowVoiceRecorder(false);
            handleSend(transcript);
          }}
          onClose={() => setShowVoiceRecorder(false)}
        />
      )}

      {/* Chat Conversation Card */}
      <div className="rounded-3xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden flex flex-col h-[520px]">
        {/* Messages Feed */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((m, i) => (
            <div
              key={m.id || i}
              className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-3xl p-4 text-xs leading-relaxed ${
                  m.role === "user"
                    ? "bg-[#123B35] text-white"
                    : m.isError
                    ? "bg-[#FEF2F2] text-[#991B1B] border border-[#FECACA]"
                    : "bg-[#F7F9F8] text-[#172B28] border border-[#E3ECE9]"
                }`}
              >
                {m.isError ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 font-medium">
                      <AlertCircle className="h-3.5 w-3.5 text-red-600" />
                      <span>{m.content}</span>
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
                  m.content
                )}

                {m.disclaimer && (
                  <p className="text-[10px] text-[#5F736F] mt-2 pt-2 border-t border-[#E3ECE9] italic">
                    {m.disclaimer}
                  </p>
                )}
              </div>
              <span className="text-[10px] text-[#5F736F] mt-1 px-2">
                {m.role === "user" ? "You" : "PostVisit AI"}
              </span>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 rounded-2xl bg-[#F7F9F8] p-3 text-xs text-[#5F736F] border border-[#E3ECE9] w-fit">
              <Sparkles className="h-3.5 w-3.5 animate-spin text-[#0D9488]" />
              Thinking...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Suggestion Chips */}
        <div className="p-3 border-t border-[#E3ECE9] bg-[#F7F9F8]">
          <div className="flex flex-wrap gap-1.5 mb-2.5">
            {sampleQuestions.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(q)}
                className="rounded-full border border-[#E3ECE9] bg-white px-3 py-1 text-[11px] text-[#5F736F] hover:border-[#0D9488] hover:text-[#0D9488] transition shadow-2xs"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input Row */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowVoiceRecorder(!showVoiceRecorder)}
              className={`flex h-10 w-10 items-center justify-center rounded-2xl border transition ${
                showVoiceRecorder
                  ? "bg-red-50 border-red-300 text-red-600"
                  : "bg-white border-[#E3ECE9] text-[#5F736F] hover:text-[#0D9488]"
              }`}
              title="Record question by voice"
              aria-label="Record question by voice"
            >
              <Mic className="h-4 w-4" />
            </button>

            <input
              type="text"
              placeholder={
                language === "ta"
                  ? "மருந்துகள், உணவுமுறை அல்லது வருகை பற்றி கேளுங்கள்..."
                  : "Ask a question about your medicines, diet, or visit..."
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              className="flex-1 rounded-2xl border border-[#E3ECE9] bg-white py-2.5 px-4 text-xs text-[#172B28] placeholder-[#5F736F] focus:border-[#0D9488] focus:outline-none"
            />
            <button
              onClick={() => handleSend()}
              disabled={!query.trim() || loading}
              className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#0D9488] text-white disabled:opacity-50 hover:bg-[#0F766E] transition shadow-xs"
              aria-label="Send query"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

