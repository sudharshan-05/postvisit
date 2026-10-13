"use client";

import React, { useState, useEffect } from "react";
import { Search, UserCheck, Stethoscope, Languages, MessageSquare, Copy, Check, Edit2, Save, X, CheckCircle2 } from "lucide-react";
import { DiarizedTurn } from "@/types";
import { doctorApi } from "@/lib/api/doctor";
import { toast } from "sonner";

interface DiarizedTranscriptProps {
  consultationId?: string;
  turns?: DiarizedTurn[];
  language?: string;
  rawTranscript?: string | DiarizedTurn[];
  isEdited?: boolean;
  onTranscriptSaved?: () => void;
}

export function DiarizedTranscript({
  consultationId,
  turns = [],
  language = "ta",
  rawTranscript,
  isEdited = false,
  onTranscriptSaved,
}: DiarizedTranscriptProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showOriginalLanguage, setShowOriginalLanguage] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [copiedAll, setCopiedAll] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const activeTurns: DiarizedTurn[] =
    turns.length > 0
      ? turns
      : Array.isArray(rawTranscript)
      ? rawTranscript
      : typeof rawTranscript === "string" && rawTranscript.trim().length > 0
      ? [{ speaker: "Speaker", text: rawTranscript }]
      : [];

  // Generate complete plain-text representation for full copying / editing
  const getFullText = () => {
    if (typeof rawTranscript === "string" && rawTranscript.trim()) return rawTranscript;
    return activeTurns
      .map((t) => `${t.speaker || "Speaker"}: ${t.translated_text || t.text}`)
      .join("\n\n");
  };

  const [editableText, setEditableText] = useState(getFullText());

  useEffect(() => {
    setEditableText(getFullText());
  }, [rawTranscript, turns]);

  const filteredTurns = activeTurns.filter((turn) => {
    const q = searchQuery.toLowerCase();
    return (
      turn.text?.toLowerCase().includes(q) ||
      turn.translated_text?.toLowerCase().includes(q) ||
      turn.speaker?.toLowerCase().includes(q)
    );
  });

  const handleCopyTurn = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    toast.success("Transcript turn copied to clipboard");
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const handleCopyAll = () => {
    navigator.clipboard.writeText(getFullText());
    setCopiedAll(true);
    toast.success("Full consultation transcript copied to clipboard");
    setTimeout(() => setCopiedAll(false), 2000);
  };

  const handleSaveCorrections = async () => {
    if (!consultationId) {
      toast.error("No consultation ID provided to save corrections.");
      return;
    }
    setIsSaving(true);
    try {
      await doctorApi.updateTranscript(consultationId, {
        transcript: editableText,
        is_confirmed: true,
      });
      toast.success("Transcript corrections saved and confirmed in clinical record!");
      setIsEditing(false);
      if (onTranscriptSaved) onTranscriptSaved();
    } catch (err: any) {
      toast.error(err?.message || "Failed to persist transcript corrections.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full rounded-2xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden">
      {/* Search & Actions Header */}
      <div className="p-3 border-b border-[#E3ECE9] bg-[#F7F9F8] flex flex-wrap items-center justify-between gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[#5F736F]" />
          <input
            type="text"
            placeholder="Search dialogue text or speaker..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            disabled={isEditing}
            className="w-full rounded-lg border border-[#E3ECE9] bg-white py-1.5 pl-8 pr-3 text-xs text-[#172B28] placeholder-[#5F736F] focus:border-[#0D9488] focus:outline-none disabled:opacity-60"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Status badge */}
          {isEdited ? (
            <span className="flex items-center gap-1 rounded-full bg-[#DCFCE7] px-2 py-0.5 text-[10px] font-semibold text-[#166534] border border-[#BBF7D0]">
              <CheckCircle2 className="h-3 w-3" />
              Confirmed
            </span>
          ) : (
            <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-[#92400E] border border-[#FDE68A]">
              Draft ASR
            </span>
          )}

          <button
            onClick={handleCopyAll}
            className="flex items-center gap-1 rounded-lg border border-[#E3ECE9] bg-white px-2.5 py-1.5 text-[11px] font-medium text-[#5F736F] hover:bg-[#F7F9F8] transition"
            title="Copy full transcript"
          >
            {copiedAll ? <Check className="h-3.5 w-3.5 text-[#16A34A]" /> : <Copy className="h-3.5 w-3.5 text-[#5F736F]" />}
            <span>{copiedAll ? "Copied All" : "Copy All"}</span>
          </button>

          <button
            onClick={() => setShowOriginalLanguage(!showOriginalLanguage)}
            className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition ${
              showOriginalLanguage
                ? "border-[#0D9488] bg-[#E7F5F1] text-[#123B35]"
                : "border-[#E3ECE9] bg-white text-[#5F736F] hover:bg-[#F7F9F8]"
            }`}
            title="Toggle Tamil / English transcript"
          >
            <Languages className="h-3.5 w-3.5 text-[#0D9488]" />
            <span>{showOriginalLanguage ? "Original (Tamil)" : "English"}</span>
          </button>

          {consultationId && (
            <button
              onClick={() => setIsEditing(!isEditing)}
              className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition ${
                isEditing
                  ? "border-[#CBD5E1] bg-[#F1F5F9] text-[#172B28]"
                  : "border-[#0D9488] bg-[#E7F5F1] text-[#123B35] hover:bg-[#0D9488] hover:text-white"
              }`}
            >
              {isEditing ? <X className="h-3.5 w-3.5" /> : <Edit2 className="h-3.5 w-3.5" />}
              <span>{isEditing ? "Cancel" : "Edit Transcript"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {isEditing ? (
        <div className="flex-1 flex flex-col p-4 space-y-3 bg-[#F8FAFC]">
          <div className="flex items-center justify-between text-xs text-[#5F736F]">
            <span>Edit consultation draft transcript below. Click Save to persist corrections to the clinical record.</span>
          </div>
          <textarea
            value={editableText}
            onChange={(e) => setEditableText(e.target.value)}
            rows={15}
            className="flex-1 w-full rounded-xl border border-[#CBD5E1] bg-white p-3.5 font-mono text-xs text-[#172B28] leading-relaxed focus:border-[#0D9488] focus:outline-none"
          />
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setIsEditing(false)}
              className="rounded-xl border border-[#E3ECE9] bg-white px-4 py-2 text-xs font-semibold text-[#5F736F] hover:bg-slate-50 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveCorrections}
              disabled={isSaving}
              className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#0F766E] transition disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              <span>{isSaving ? "Saving..." : "Save Corrections"}</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {activeTurns.length === 0 && !rawTranscript ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <MessageSquare className="h-8 w-8 text-[#CBD5E1] mb-3" />
              <p className="text-sm font-semibold text-[#172B28] mb-1">Transcript not available.</p>
              <p className="text-xs text-[#5F736F]">No transcript has been generated for this consultation yet.</p>
            </div>
          ) : rawTranscript && activeTurns.length === 0 ? (
            <div className="p-4 rounded-xl bg-[#F7F9F8] border border-[#E3ECE9]">
              <p className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider mb-2">Consultation Transcript</p>
              <pre className="text-xs text-[#172B28] whitespace-pre-wrap leading-relaxed font-sans">
                {typeof rawTranscript === "string" ? rawTranscript : JSON.stringify(rawTranscript, null, 2)}
              </pre>
            </div>
          ) : filteredTurns.length === 0 ? (
            <div className="text-center py-8 text-xs text-[#5F736F]">
              No dialogue matches "{searchQuery}".
            </div>
          ) : (
            filteredTurns.map((turn, idx) => {
              const rawSpeaker = turn.speaker || "Speaker";
              const isDoctor = turn.speaker_role === "doctor" || rawSpeaker.toLowerCase().includes("doc");
              const isPatient = turn.speaker_role === "patient" || rawSpeaker.toLowerCase().includes("pat");
              const speakerLabel = isDoctor ? "Doctor" : isPatient ? "Patient" : rawSpeaker;
              const hasTranslation = turn.translated_text && turn.translated_text !== turn.text;
              const timeVal = turn.start ?? turn.start_time;

              return (
                <div
                  key={idx}
                  className={`p-3.5 rounded-xl border transition-all ${
                    isDoctor
                      ? "bg-[#F7F9F8] border-[#E3ECE9] text-[#172B28]"
                      : isPatient
                      ? "bg-white border-[#E7F5F1] text-[#172B28] shadow-xs"
                      : "bg-[#FAFAFA] border-[#E5E7EB] text-[#172B28]"
                  }`}
                >
                  {/* Speaker Header */}
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      {isDoctor ? (
                        <span className="flex items-center gap-1 text-xs font-semibold text-[#123B35]">
                          <Stethoscope className="h-3.5 w-3.5 text-[#0D9488]" />
                          {speakerLabel}
                        </span>
                      ) : isPatient ? (
                        <span className="flex items-center gap-1 text-xs font-semibold text-[#075985]">
                          <UserCheck className="h-3.5 w-3.5 text-[#0284C7]" />
                          {speakerLabel}
                        </span>
                      ) : (
                        <span className="text-xs font-semibold text-[#475569]">
                          {speakerLabel}
                        </span>
                      )}

                      {timeVal != null && (
                        <span className="text-[10px] text-[#5F736F] font-mono ml-1">
                          · {Math.floor(timeVal / 60)}:{String(Math.floor(timeVal % 60)).padStart(2, "0")}
                        </span>
                      )}
                    </div>

                    <button
                      onClick={() => handleCopyTurn(turn.text, idx)}
                      className="p-1 rounded text-[#5F736F] hover:bg-white hover:text-[#172B28] transition"
                      title="Copy dialogue turn"
                    >
                      {copiedIdx === idx ? <Check className="h-3.5 w-3.5 text-[#16A34A]" /> : <Copy className="h-3.5 w-3.5" />}
                    </button>
                  </div>

                  {/* Message Body */}
                  <p className="text-xs leading-relaxed">
                    {showOriginalLanguage && turn.text ? turn.text : turn.translated_text || turn.text}
                  </p>

                  {/* Bilingual subtitle */}
                  {showOriginalLanguage && hasTranslation && (
                    <p className="text-[11px] text-[#5F736F] mt-1 pt-1 border-t border-dashed border-[#E3ECE9]">
                      English: {turn.translated_text}
                    </p>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
