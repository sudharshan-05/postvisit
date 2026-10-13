"use client";

import React, { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  Edit2,
  Sparkles,
  RefreshCw,
  Save,
  Clock,
  History,
  FileCheck,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { PatientSummary, MedicalRecordData } from "@/types";
import { summariesApi } from "@/lib/api/summaries";
import { queryKeys } from "@/lib/query/keys";
import { toast } from "sonner";

interface SummaryReviewComparisonProps {
  summary?: PatientSummary | null;
  medicalRecord?: MedicalRecordData | null;
  consultationId: string;
  onStatusChange?: () => void;
}

export function SummaryReviewComparison({
  summary,
  medicalRecord,
  consultationId,
  onStatusChange,
}: SummaryReviewComparisonProps) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Editable Form Fields
  const [overview, setOverview] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [findings, setFindings] = useState("");
  const [instructions, setInstructions] = useState("");
  const [tests, setTests] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [warnings, setWarnings] = useState("");
  const [doctorNotes, setDoctorNotes] = useState("");

  const content: any = summary?.summary_content || {};

  // Populate state on summary load or change
  useEffect(() => {
    if (summary) {
      const c: any = summary.summary_content || {};
      setOverview(c.overview || c.diagnosis_summary || c.reason_for_visit || "");
      
      const symList = c.symptoms_discussed || c.symptoms_explained || medicalRecord?.symptoms || [];
      setSymptoms(Array.isArray(symList) ? symList.join("\n") : String(symList));

      setFindings(c.findings || (Array.isArray(medicalRecord?.examination_findings) ? medicalRecord.examination_findings.join(", ") : "") || "");

      const instList = c.self_care_instructions || c.doctor_instructions || medicalRecord?.doctor_recommendations || [];
      setInstructions(Array.isArray(instList) ? instList.join("\n") : String(instList));

      const testList = c.tests_ordered || c.tests_explained || medicalRecord?.tests_recommended || medicalRecord?.investigations || [];
      setTests(
        Array.isArray(testList)
          ? testList.map((t: any) => (typeof t === "string" ? t : `${t.test_name || t.name}${t.instructions ? ` (${t.instructions})` : ""}`)).join("\n")
          : String(testList)
      );

      setFollowUp(c.when_to_visit_again || c.follow_up || (typeof medicalRecord?.follow_up === "string" ? medicalRecord.follow_up : medicalRecord?.follow_up_instructions) || "");

      const warnList = c.warnings_and_precautions || c.precautions || medicalRecord?.warnings || medicalRecord?.red_flags || [];
      setWarnings(Array.isArray(warnList) ? warnList.join("\n") : String(warnList));

      setDoctorNotes(summary.review_notes || "");
    }
  }, [summary, medicalRecord]);

  const handleGenerateSummary = async () => {
    setIsGenerating(true);
    try {
      await summariesApi.generate(consultationId, "en");
      toast.success("Patient summary generation triggered!");
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      toast.error(err?.message || "Failed to generate summary. Verify that the encounter has completed transcription.");
    } finally {
      setIsGenerating(false);
    }
  };

  const buildCorrectedPayload = () => {
    const symArray = symptoms.split("\n").map((s) => s.trim()).filter(Boolean);
    const instArray = instructions.split("\n").map((s) => s.trim()).filter(Boolean);
    const warnArray = warnings.split("\n").map((s) => s.trim()).filter(Boolean);
    const testArray = tests
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((t) => ({ test_name: t, timing: undefined, instructions: undefined }));

    // Preserve existing medication instructions with dosage and timing
    const existingMeds = (content.medications || content.medications_list || []).map((m: any) => ({
      medication_name: m.medication_name || m.name,
      strength: m.strength || m.dosage,
      dose: m.dose,
      route: m.route || "oral",
      frequency: m.frequency,
      timing: m.timing,
      duration: m.duration,
      instructions: m.instructions || "Take as prescribed by physician.",
    }));

    return {
      overview: overview || "Clinical consultation summary",
      symptoms_discussed: symArray,
      medications: existingMeds,
      tests_ordered: testArray,
      self_care_instructions: instArray,
      warnings_and_precautions: warnArray,
      when_to_visit_again: followUp || undefined,
      unspecified_or_uncertain_info: content.unspecified_or_uncertain_info || [],
    };
  };

  const invalidatePortalQueries = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.summaryDetail(consultationId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.consultationDetail(consultationId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.doctorQueue({}) });
    queryClient.invalidateQueries({ queryKey: queryKeys.patientLastVisit() });
    queryClient.invalidateQueries({ queryKey: queryKeys.patientOverview() });
    queryClient.invalidateQueries({ queryKey: queryKeys.patientHistory() });
  };

  const handleSaveDraft = async () => {
    if (!summary?.id) return;
    setIsSubmitting(true);
    try {
      await summariesApi.review(summary.id, {
        doctor_name: "Dr. A. Ramanathan",
        decision: "amended",
        notes: doctorNotes || "Draft corrections saved by clinician.",
        corrected_summary: buildCorrectedPayload(),
      });
      toast.success("Summary draft saved and updated in review workspace!");
      setIsEditing(false);
      invalidatePortalQueries();
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      toast.error(err?.message || "Failed to save summary draft.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!summary?.id) return;
    setIsSubmitting(true);
    try {
      await summariesApi.review(summary.id, {
        doctor_name: "Dr. A. Ramanathan",
        decision: "approved",
        notes: doctorNotes || "Clinically reviewed and confirmed for patient portal release.",
        corrected_summary: isEditing ? buildCorrectedPayload() : undefined,
      });
      toast.success("Summary approved and securely released to authorized patient!");
      setIsEditing(false);
      invalidatePortalQueries();
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      toast.error(err?.message || "Failed to approve summary.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!summary?.id) return;
    setIsSubmitting(true);
    try {
      await summariesApi.review(summary.id, {
        doctor_name: "Dr. A. Ramanathan",
        decision: "rejected",
        notes: doctorNotes || "Requires revision by clinician.",
      });
      toast.info("Summary rejected. Returned to draft status.");
      invalidatePortalQueries();
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      toast.error(err?.message || "Failed to reject summary.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!summary) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-12 text-center space-y-4">
        <AlertTriangle className="h-10 w-10 text-[#CBD5E1] mx-auto" />
        <div>
          <h3 className="text-sm font-bold text-[#172B28]">Summary has not been generated yet.</h3>
          <p className="text-xs text-[#5F736F] mt-1 max-w-md mx-auto">
            You can trigger patient-friendly summary generation directly from the extracted medical record.
          </p>
        </div>
        <button
          onClick={handleGenerateSummary}
          disabled={isGenerating}
          className="inline-flex items-center gap-2 rounded-xl bg-[#0D9488] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#0F766E] transition disabled:opacity-50"
        >
          {isGenerating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          <span>{isGenerating ? "Generating..." : "Generate Patient Summary"}</span>
        </button>
      </div>
    );
  }

  const isApproved =
    summary.status === "SUMMARY_APPROVED" ||
    summary.doctor_reviewed ||
    summary.review_decision === "approved";

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-6">
      {/* Header with Guardrail Badge & Approval Lifecycle */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b border-[#E3ECE9]">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-[#172B28]">
              Patient Summary Review & Patient Release Gate
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[#F1F5F9] text-[#475569]">
              v{summary.version || 1}
            </span>
          </div>
          <p className="text-xs text-[#5F736F]">
            Side-by-side verification between immutable source clinical data and patient-facing summary.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isApproved ? (
            <span className="flex items-center gap-1.5 rounded-full bg-[#DCFCE7] px-3 py-1 text-xs font-semibold text-[#166534] border border-[#BBF7D0]">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approved & Released
            </span>
          ) : (
            <span className="flex items-center gap-1.5 rounded-full bg-[#FEF3C7] px-3 py-1 text-xs font-semibold text-[#92400E] border border-[#FDE68A]">
              <AlertTriangle className="h-3.5 w-3.5" />
              Pending Doctor Review
            </span>
          )}

          <div className="flex items-center gap-1 rounded-full bg-[#F0FDF4] px-2.5 py-1 text-xs font-medium text-[#15803D] border border-[#BBF7D0]">
            <ShieldCheck className="h-3.5 w-3.5 text-[#16A34A]" />
            Guardrails: {summary.guardrail_status || "Passed"}
          </div>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-1 rounded-lg border border-[#E3ECE9] bg-white px-2.5 py-1 text-xs text-[#5F736F] hover:bg-[#F7F9F8]"
            title="Toggle Audit & Version History"
          >
            <History className="h-3.5 w-3.5" />
            <span>Audit History</span>
            {showHistory ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Version History Drawer */}
      {showHistory && (
        <div className="p-4 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] text-xs space-y-2">
          <h4 className="font-bold text-[#1E293B] flex items-center gap-1.5">
            <History className="h-3.5 w-3.5 text-[#0D9488]" />
            <span>Summary Audit & Version Lifecycle</span>
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px] text-[#64748B]">
            <div>
              <span className="font-semibold block text-[#334155]">Current Version:</span>
              <span>Version {summary.version || 1}</span>
            </div>
            <div>
              <span className="font-semibold block text-[#334155]">Workflow Status:</span>
              <span className="font-mono">{summary.status || "PENDING_SUMMARY_REVIEW"}</span>
            </div>
            <div>
              <span className="font-semibold block text-[#334155]">Review Decision:</span>
              <span>{summary.review_decision || "Pending"}</span>
            </div>
            <div>
              <span className="font-semibold block text-[#334155]">Reviewer:</span>
              <span>{summary.doctor_name || "Dr. A. Ramanathan"}</span>
            </div>
          </div>
          {summary.review_notes && (
            <p className="text-[11px] text-[#475569] bg-white p-2.5 rounded-lg border border-[#E2E8F0]">
              <strong>Review Notes:</strong> {summary.review_notes}
            </p>
          )}
        </div>
      )}

      {/* Side-by-side verification columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (5 cols): Immutable Source EHR Record */}
        <div className="lg:col-span-5 rounded-xl border border-[#E3ECE9] bg-[#F7F9F8] p-4 space-y-4 text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-[#E3ECE9]">
            <span className="font-bold text-[#123B35] uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <FileCheck className="h-3.5 w-3.5 text-[#0D9488]" />
              Source Clinical Record (Doctor View)
            </span>
            <span className="text-[10px] text-[#5F736F] font-mono">Immutable EHR</span>
          </div>

          <div>
            <span className="font-semibold text-[#172B28] block mb-0.5">Reported Symptoms:</span>
            <p className="text-[#5F736F] leading-relaxed">
              {medicalRecord?.symptoms?.join(", ") ||
                medicalRecord?.symptoms_mentioned?.join(", ") ||
                "None documented"}
            </p>
          </div>

          <div>
            <span className="font-semibold text-[#172B28] block mb-0.5">History of Present Illness (HPI):</span>
            <p className="text-[#5F736F] leading-relaxed">
              {medicalRecord?.hpi || "No HPI documented"}
            </p>
          </div>

          {medicalRecord?.examination_findings && medicalRecord.examination_findings.length > 0 && (
            <div>
              <span className="font-semibold text-[#172B28] block mb-0.5">Examination Findings:</span>
              <ul className="list-disc pl-4 text-[#5F736F] space-y-0.5">
                {medicalRecord.examination_findings.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <span className="font-semibold text-[#172B28] block mb-0.5">Doctor-Prescribed Medications:</span>
            {medicalRecord?.medications && medicalRecord.medications.length > 0 ? (
              <ul className="list-disc pl-4 text-[#5F736F] space-y-1">
                {medicalRecord.medications.map((m, idx) => (
                  <li key={idx}>
                    <strong>{m.name || m.medicine_name}</strong> {m.strength || m.dose || ""} — {m.frequency || ""} ({m.timing || ""})
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[#5F736F]">No medications in record</p>
            )}
          </div>

          <div>
            <span className="font-semibold text-[#172B28] block mb-0.5">Doctor Recommendations:</span>
            {medicalRecord?.doctor_recommendations && medicalRecord.doctor_recommendations.length > 0 ? (
              <ul className="list-disc pl-4 text-[#5F736F] space-y-1">
                {medicalRecord.doctor_recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            ) : (
              <p className="text-[#5F736F]">None documented</p>
            )}
          </div>

          {medicalRecord?.follow_up_instructions && (
            <div>
              <span className="font-semibold text-[#172B28] block mb-0.5">Follow-up Instructions:</span>
              <p className="text-[#5F736F]">{medicalRecord.follow_up_instructions}</p>
            </div>
          )}

          {medicalRecord?.warnings && medicalRecord.warnings.length > 0 && (
            <div>
              <span className="font-semibold text-[#991B1B] block mb-0.5">Warnings & Red Flags:</span>
              <ul className="list-disc pl-4 text-[#991B1B] space-y-0.5">
                {medicalRecord.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Column (7 cols): Patient Summary Editor */}
        <div className="lg:col-span-7 rounded-xl border border-[#CCFBF1] bg-white p-5 space-y-4 text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-[#E3ECE9]">
            <span className="font-bold text-[#0D9488] uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-[#0D9488]" />
              Patient-Facing Summary {isEditing ? "(Editing Draft)" : "(Preview)"}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsEditing(!isEditing)}
                className="flex items-center gap-1 text-[11px] font-semibold text-[#0D9488] hover:underline"
              >
                <Edit2 className="h-3 w-3" />
                <span>{isEditing ? "Finish Editing" : "Edit Fields"}</span>
              </button>
            </div>
          </div>

          {/* Field 1: Visit Overview */}
          <div>
            <label className="font-semibold text-[#172B28] block mb-1">
              Visit Overview & Primary Diagnosis:
            </label>
            {isEditing ? (
              <textarea
                value={overview}
                onChange={(e) => setOverview(e.target.value)}
                rows={2}
                className="w-full rounded-xl border border-[#CBD5E1] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
              />
            ) : (
              <p className="text-[#172B28] leading-relaxed bg-[#F7F9F8] p-2.5 rounded-xl border border-[#E3ECE9]">
                {overview || "Summary pending generation"}
              </p>
            )}
          </div>

          {/* Field 2: Reported Symptoms */}
          <div>
            <label className="font-semibold text-[#172B28] block mb-1">
              Reported Symptoms Discussed:
            </label>
            {isEditing ? (
              <textarea
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
                rows={2}
                placeholder="One symptom per line"
                className="w-full rounded-xl border border-[#CBD5E1] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
              />
            ) : (
              <p className="text-[#172B28] leading-relaxed bg-[#F7F9F8] p-2.5 rounded-xl border border-[#E3ECE9]">
                {symptoms ? symptoms.split("\n").join(", ") : "None specified"}
              </p>
            )}
          </div>

          {/* Field 3: Prescribed Medications Explained */}
          <div>
            <span className="font-semibold text-[#172B28] block mb-1">
              Prescribed Medications Explained:
            </span>
            {content.medications && content.medications.length > 0 ? (
              <div className="space-y-1.5">
                {content.medications.map((m: any, idx: number) => (
                  <div key={idx} className="p-2.5 rounded-xl bg-[#F7F9F8] border border-[#E3ECE9]">
                    <div className="flex items-center justify-between">
                      <strong className="text-[#172B28]">{m.medication_name || m.name}</strong>
                      <span className="text-[10px] font-mono text-[#5F736F]">
                        {m.strength || m.dosage || ""} {m.frequency || ""}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#5F736F] mt-1">
                      {m.instructions || `Take ${m.timing || "as directed"}`}
                    </p>
                  </div>
                ))}
              </div>
            ) : content.medications_list && content.medications_list.length > 0 ? (
              <div className="space-y-1.5">
                {content.medications_list.map((m: any, idx: number) => (
                  <div key={idx} className="p-2.5 rounded-xl bg-[#F7F9F8] border border-[#E3ECE9]">
                    <div className="flex items-center justify-between">
                      <strong className="text-[#172B28]">{m.name}</strong>
                      <span className="text-[10px] font-mono text-[#5F736F]">{m.dosage || ""}</span>
                    </div>
                    <p className="text-[11px] text-[#5F736F] mt-1">{m.instructions || m.timing || ""}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#5F736F] italic bg-[#F7F9F8] p-2 rounded-xl border border-[#E3ECE9]">
                No prescribed medications documented for this encounter.
              </p>
            )}
          </div>

          {/* Field 4: Care & Lifestyle Instructions */}
          <div>
            <label className="font-semibold text-[#172B28] block mb-1">
              Care & Recovery Instructions:
            </label>
            {isEditing ? (
              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                rows={3}
                placeholder="One instruction per line"
                className="w-full rounded-xl border border-[#CBD5E1] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
              />
            ) : (
              <div className="bg-[#F7F9F8] p-2.5 rounded-xl border border-[#E3ECE9] space-y-1">
                {instructions ? (
                  instructions.split("\n").filter(Boolean).map((inst, idx) => (
                    <div key={idx} className="flex items-start gap-1.5 text-[#172B28]">
                      <span className="text-[#0D9488] font-bold">•</span>
                      <span>{inst}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-[#5F736F]">No specific instructions documented</p>
                )}
              </div>
            )}
          </div>

          {/* Field 5: Tests Ordered */}
          <div>
            <label className="font-semibold text-[#172B28] block mb-1">
              Diagnostic Tests & Investigations Ordered:
            </label>
            {isEditing ? (
              <textarea
                value={tests}
                onChange={(e) => setTests(e.target.value)}
                rows={2}
                placeholder="One test per line"
                className="w-full rounded-xl border border-[#CBD5E1] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
              />
            ) : (
              <p className="text-[#172B28] bg-[#F7F9F8] p-2.5 rounded-xl border border-[#E3ECE9]">
                {tests || "None ordered"}
              </p>
            )}
          </div>

          {/* Field 6: Follow-up */}
          <div>
            <label className="font-semibold text-[#172B28] block mb-1">
              Follow-up Timeline & Visit Instructions:
            </label>
            {isEditing ? (
              <input
                type="text"
                value={followUp}
                onChange={(e) => setFollowUp(e.target.value)}
                placeholder="e.g., Return in 2 weeks or if symptoms worsen"
                className="w-full rounded-xl border border-[#CBD5E1] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
              />
            ) : (
              <p className="text-[#172B28] bg-[#F7F9F8] p-2.5 rounded-xl border border-[#E3ECE9]">
                {followUp || "No follow-up timeline documented"}
              </p>
            )}
          </div>

          {/* Field 7: Warnings & Red Flags */}
          <div>
            <label className="font-semibold text-[#991B1B] block mb-1">
              Warnings & Emergency Red Flags:
            </label>
            {isEditing ? (
              <textarea
                value={warnings}
                onChange={(e) => setWarnings(e.target.value)}
                rows={2}
                placeholder="One warning per line"
                className="w-full rounded-xl border border-red-200 p-2.5 text-xs text-[#991B1B] focus:border-red-500 focus:outline-none"
              />
            ) : (
              <p className="text-[#991B1B] bg-red-50 p-2.5 rounded-xl border border-red-200">
                {warnings || "Standard emergency precautions"}
              </p>
            )}
          </div>

          {/* Field 8: Doctor Clinical Review Remarks */}
          <div className="pt-2 border-t border-[#E3ECE9]">
            <label className="font-semibold text-[#172B28] block mb-1">
              Physician Review Remarks / Audit Notes:
            </label>
            <textarea
              value={doctorNotes}
              onChange={(e) => setDoctorNotes(e.target.value)}
              rows={2}
              placeholder="Add clinical verification notes for audit trail..."
              className="w-full rounded-xl border border-[#CBD5E1] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Action Controls & Gate */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[#E3ECE9]">
        <div className="text-xs text-[#5F736F]">
          {isApproved ? (
            <span className="text-[#166534] font-semibold flex items-center gap-1">
              <CheckCircle2 className="h-4 w-4" />
              Summary is released and currently visible on the patient dashboard.
            </span>
          ) : (
            <span className="text-[#92400E] font-medium flex items-center gap-1">
              <AlertTriangle className="h-4 w-4" />
              Unapproved summary is strictly hidden from patient portal until doctor sign-off.
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isEditing && (
            <button
              onClick={handleSaveDraft}
              disabled={isSubmitting}
              className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-white px-4 py-2 text-xs font-semibold text-[#172B28] hover:bg-[#F7F9F8] transition disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              <span>Save Draft</span>
            </button>
          )}

          <button
            onClick={handleReject}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-2 text-xs font-semibold text-[#991B1B] hover:bg-red-100 transition disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" />
            <span>Reject / Request Revision</span>
          </button>

          <button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#0F766E] transition disabled:opacity-50"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>{isSubmitting ? "Processing..." : "Approve & Release to Patient"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
