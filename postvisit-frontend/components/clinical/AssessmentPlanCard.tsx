"use client";

import React, { useState } from "react";
import { CheckSquare, Copy, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

interface AssessmentPlanCardProps {
  hpi?: string;
  assessmentPlan?: string[];
  recommendations?: string[];
}

export function AssessmentPlanCard({
  hpi,
  assessmentPlan = [],
  recommendations = [],
}: AssessmentPlanCardProps) {
  const [copied, setCopied] = useState(false);

  const hasContent = !!hpi || assessmentPlan.length > 0 || recommendations.length > 0;

  const handleCopy = () => {
    const parts = [];
    if (hpi) parts.push(`HISTORY OF PRESENT ILLNESS:\n${hpi}`);
    if (assessmentPlan.length > 0) parts.push(`ASSESSMENT & PLAN:\n${assessmentPlan.map((p) => `• ${p}`).join("\n")}`);
    if (recommendations.length > 0) parts.push(`RECOMMENDATIONS:\n${recommendations.map((r) => `• ${r}`).join("\n")}`);

    navigator.clipboard.writeText(parts.join("\n\n"));
    setCopied(true);
    toast.success("Assessment & Plan copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-5 shadow-xs">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#E3ECE9]">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#E7F5F1] text-[#0D9488]">
            <CheckSquare className="h-4 w-4" />
          </div>
          <h3 className="text-sm font-bold text-[#172B28]">Clinical Assessment & Plan</h3>
        </div>
        {hasContent && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold text-[#5F736F] hover:bg-[#F7F9F8] hover:text-[#172B28] transition border border-[#E3ECE9]"
            title="Copy Assessment & Plan"
          >
            {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-[#16A34A]" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        )}
      </div>

      {!hasContent ? (
        <div className="p-6 text-center text-xs text-[#5F736F]">
          Clinical assessment narrative not documented in this consultation.
        </div>
      ) : (
        <div className="space-y-4 text-xs">
          {/* Narrative HPI */}
          {hpi && (
            <div>
              <h4 className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider mb-1">
                History of Present Illness (HPI)
              </h4>
              <p className="text-xs text-[#172B28] leading-relaxed bg-[#F7F9F8] p-3 rounded-xl border border-[#E3ECE9]">
                {hpi}
              </p>
            </div>
          )}

          {/* Assessment & Plan */}
          {assessmentPlan.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider mb-2">
                Assessment & Plan
              </h4>
              <div className="space-y-1.5">
                {assessmentPlan.map((item, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-[#172B28]">
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-md bg-[#DCFCE7] text-[#166534]">
                      ✓
                    </span>
                    <span className="leading-snug">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider mb-2">
                Care Recommendations
              </h4>
              <div className="space-y-1">
                {recommendations.map((rec, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-[#5F736F]">
                    <span className="text-[#0D9488] font-bold">•</span>
                    <span className="leading-snug">{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
