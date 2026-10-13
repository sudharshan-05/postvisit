"use client";

import React, { useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { consultationsApi } from "@/lib/api/consultations";
import { summariesApi } from "@/lib/api/summaries";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  Sparkles,
  RefreshCw,
  FileText,
  Activity,
  FlaskConical,
  Shield,
  ClipboardList,
  History,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Edit,
  X,
  Mic,
  Square,
  Play,
  Pause,
  Trash2,
  Check,
  Send,
} from "lucide-react";
import { DiarizedTranscript } from "@/components/clinical/DiarizedTranscript";
import { MedicationCard } from "@/components/clinical/MedicationCard";
import { AssessmentPlanCard } from "@/components/clinical/AssessmentPlanCard";
import { SummaryReviewComparison } from "@/components/clinical/SummaryReviewComparison";
import { AskAIDrawer } from "@/components/assistant/AskAIDrawer";
import { toast } from "sonner";
import { formatDuration } from "@/lib/utils";
import { useAuth } from "@/lib/auth/context";

type Tab = "overview" | "transcript" | "clinical" | "summary" | "guidelines" | "lab-reports" | "audit";

export default function DoctorConsultationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const id = (params?.id as string) || "";
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [isAIOpen, setIsAIOpen] = useState(false);

  // === DATA FETCHING ===
  const { data: consultation, isLoading: loadingConsultation, refetch } = useQuery({
    queryKey: queryKeys.consultationDetail(id),
    queryFn: () => consultationsApi.getById(id),
    enabled: !!id,
    retry: 1,
  });

  const { data: summaryData, refetch: refetchSummary } = useQuery({
    queryKey: queryKeys.summaryDetail(id),
    queryFn: () => summariesApi.listForConsultation(id).catch(() => ({ summaries: [] })),
    enabled: !!id,
  });

  const { data: guidelinesData } = useQuery({
    queryKey: queryKeys.doctorGuidelines(id),
    queryFn: () => doctorApi.getGuidelines(id).catch(() => ({ findings: [], status: "not_available", total: 0 })),
    enabled: !!id && activeTab === "guidelines",
  });

  const { data: labReportsData } = useQuery({
    queryKey: queryKeys.doctorLabReports(undefined, id),
    queryFn: () => doctorApi.listLabReports(undefined, id).catch(() => ({ lab_reports: [], total: 0 })),
    enabled: !!id && activeTab === "lab-reports",
  });

  const { data: auditData } = useQuery({
    queryKey: queryKeys.doctorAuditTrail(id),
    queryFn: () => doctorApi.getAuditTrail(id).catch(() => ({ audit_trail: [] })),
    enabled: !!id && activeTab === "audit",
  });

  const { data: timelineData } = useQuery({
    queryKey: queryKeys.doctorTimeline(id),
    queryFn: () => doctorApi.getTimeline(id).catch(() => null),
    enabled: !!id,
  });

  const summary = summaryData?.summaries?.[0] || null;

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "Overview", icon: <Activity className="h-3.5 w-3.5" /> },
    { key: "transcript", label: "Transcript", icon: <FileText className="h-3.5 w-3.5" /> },
    { key: "clinical", label: "Clinical Data", icon: <ClipboardList className="h-3.5 w-3.5" /> },
    { key: "summary", label: "Summary", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
    { key: "guidelines", label: "Guidelines", icon: <Shield className="h-3.5 w-3.5" /> },
    { key: "lab-reports", label: "Lab Reports", icon: <FlaskConical className="h-3.5 w-3.5" /> },
    { key: "audit", label: "Audit", icon: <History className="h-3.5 w-3.5" /> },
  ];

  const handleStatusRefresh = () => {
    refetch();
    refetchSummary();
    queryClient.invalidateQueries({ queryKey: queryKeys.doctorQueue({}) });
  };

  return (
    <div className="space-y-4 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-3 border-b border-[#E3ECE9]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/doctor/dashboard")}
            className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-[#172B28]">
                {consultation?.patient_name || "Patient"}
              </h2>
              {consultation?.patient_id && (
                <span className="rounded-md bg-[#E7F5F1] px-2 py-0.5 text-[11px] font-semibold text-[#123B35]">
                  MRN: {consultation.patient_id}
                </span>
              )}
              {consultation?.status && (
                <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold border ${
                  consultation.status === "approved" || consultation.status === "completed"
                    ? "bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]"
                    : consultation.status === "pending_doctor_review" || consultation.status === "awaiting_review"
                    ? "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                    : consultation.status === "processing" || consultation.status === "queued"
                    ? "bg-[#E0F2FE] text-[#075985] border-[#BAE6FD]"
                    : "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]"
                }`}>
                  {consultation.status.replace(/_/g, " ")}
                </span>
              )}
            </div>
            <p className="text-xs text-[#5F736F]">
              Encounter: {formatDate(consultation?.created_at || "")} • Outpatient Department
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsAIOpen(true)}
            className="flex items-center gap-1.5 rounded-full border border-[#0D9488] bg-[#E7F5F1] px-3.5 py-1.5 text-xs font-semibold text-[#123B35] hover:bg-[#0D9488] hover:text-white transition shadow-2xs"
            aria-label="Open AI Copilot"
          >
            <Sparkles className="h-3.5 w-3.5 text-[#0D9488]" />
            AI Copilot
          </button>
          <button
            onClick={handleStatusRefresh}
            className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
            aria-label="Refresh consultation data"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-[#E3ECE9] pb-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3.5 py-2.5 text-xs font-semibold whitespace-nowrap border-b-2 transition -mb-px ${
              activeTab === tab.key
                ? "border-[#0D9488] text-[#0D9488]"
                : "border-transparent text-[#5F736F] hover:text-[#172B28] hover:border-[#E3ECE9]"
            }`}
            aria-selected={activeTab === tab.key}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading State */}
      {loadingConsultation && (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-[#0D9488]" />
          <span className="ml-3 text-sm text-[#5F736F]">Loading consultation...</span>
        </div>
      )}

      {/* TAB CONTENT */}
      {!loadingConsultation && (
        <>
          {/* OVERVIEW TAB */}
          {activeTab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7 space-y-5">
                <MedicationCard
                  medications={consultation?.medical_data?.medications}
                  onSave={() => toast.success("Medications noted.")}
                />
                <AssessmentPlanCard
                  hpi={consultation?.medical_data?.hpi}
                  recommendations={consultation?.medical_data?.doctor_recommendations}
                />
                <VoiceNoteSection consultationId={id} />
              </div>
              <div className="lg:col-span-5 space-y-5">
                {/* Quick Status */}
                <div className="rounded-2xl border border-[#E3ECE9] bg-white p-4 space-y-3">
                  <h3 className="text-xs font-bold text-[#172B28] uppercase tracking-wider">Consultation Status</h3>
                  {timelineData?.steps ? (
                    <div className="space-y-2">
                      {timelineData.steps.map((step: any, i: number) => (
                        <div key={i} className="flex items-center gap-2.5 text-xs">
                          {step.status === "completed" ? (
                            <CheckCircle2 className="h-4 w-4 text-[#16A34A] shrink-0" />
                          ) : step.status === "in_progress" ? (
                            <RefreshCw className="h-4 w-4 text-[#0D9488] animate-spin shrink-0" />
                          ) : step.status === "failed" ? (
                            <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                          ) : (
                            <div className="h-4 w-4 rounded-full border-2 border-[#CBD5E1] shrink-0" />
                          )}
                          <span className={step.status === "completed" ? "text-[#172B28]" : "text-[#5F736F]"}>
                            {step.name || step.step}
                          </span>
                          {step.status === "not_configured" && (
                            <span className="text-[10px] text-[#5F736F] italic">(Not configured)</span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-2 text-xs text-[#5F736F]">
                      <p>Current status: <strong className="text-[#172B28]">{consultation?.status || "Unknown"}</strong></p>
                      {consultation?.active_step && (
                        <p>Active step: <strong className="text-[#172B28]">{consultation.active_step}</strong></p>
                      )}
                    </div>
                  )}
                </div>

                {/* Key Clinical Values / Vitals */}
                <ConsultationVitalsCard
                  consultationId={id}
                  vitals={consultation?.medical_data?.vital_signs}
                  onVitalsUpdated={() => {
                    refetch();
                    queryClient.invalidateQueries({ queryKey: queryKeys.consultationDetail(id) });
                  }}
                />
              </div>
            </div>
          )}

          {/* TRANSCRIPT TAB */}
          {activeTab === "transcript" && (
            <div className="h-[650px]">
              <DiarizedTranscript
                consultationId={id}
                turns={consultation?.diarized_transcript}
                rawTranscript={consultation?.transcript}
                language="ta"
                isEdited={Boolean((consultation as any)?.is_transcript_edited)}
                onTranscriptSaved={() => {
                  refetch();
                  queryClient.invalidateQueries({ queryKey: queryKeys.consultationDetail(id) });
                }}
              />
            </div>
          )}

          {/* CLINICAL DATA TAB */}
          {activeTab === "clinical" && (
            <ClinicalDataView medicalData={consultation?.medical_data} />
          )}

          {/* SUMMARY TAB */}
          {activeTab === "summary" && (
            <SummaryReviewComparison
              summary={summary}
              medicalRecord={consultation?.medical_data}
              consultationId={id}
              onStatusChange={handleStatusRefresh}
            />
          )}

          {/* GUIDELINES TAB */}
          {activeTab === "guidelines" && (
            <GuidelinesView consultationId={id} data={guidelinesData} />
          )}

          {/* LAB REPORTS TAB */}
          {activeTab === "lab-reports" && (
            <LabReportsView data={labReportsData} />
          )}

          {/* AUDIT TAB */}
          {activeTab === "audit" && (
            <AuditView data={auditData} />
          )}
        </>
      )}

      {/* AI Copilot Drawer */}
      <AskAIDrawer
        isOpen={isAIOpen}
        onClose={() => setIsAIOpen(false)}
        consultationId={id}
        patientId={consultation?.patient_id}
      />
    </div>
  );
}

// =================== SUB-COMPONENTS ===================

function ClinicalDataView({ medicalData }: { medicalData?: any }) {
  if (!medicalData) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-12 text-center">
        <ClipboardList className="h-8 w-8 mx-auto text-[#CBD5E1] mb-3" />
        <p className="text-sm font-semibold text-[#172B28] mb-1">Clinical data not available</p>
        <p className="text-xs text-[#5F736F]">No structured clinical data has been extracted yet.</p>
      </div>
    );
  }

  const sections = [
    { label: "Reported Symptoms", value: medicalData.symptoms, type: "list" },
    { label: "History of Present Illness", value: medicalData.hpi, type: "text" },
    { label: "Examination Findings", value: medicalData.examination_findings, type: "list" },
    { label: "Tests Recommended", value: medicalData.investigations || medicalData.tests_recommended, type: "list" },
    { label: "Doctor Recommendations", value: medicalData.doctor_recommendations || medicalData.recommendations, type: "list" },
    { label: "Follow-up Instructions", value: medicalData.follow_up || medicalData.follow_up_instructions, type: "text" },
    { label: "Warnings / Red Flags", value: medicalData.warnings || medicalData.red_flags, type: "list" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map((section, i) => {
          if (!section.value || (Array.isArray(section.value) && section.value.length === 0)) return null;
          return (
            <div key={i} className="rounded-2xl border border-[#E3ECE9] bg-white p-4">
              <h4 className="text-[11px] font-bold text-[#5F736F] uppercase tracking-wider mb-2">{section.label}</h4>
              {section.type === "list" && Array.isArray(section.value) ? (
                <ul className="space-y-1">
                  {section.value.map((item: string, idx: number) => (
                    <li key={idx} className="flex items-start gap-1.5 text-xs text-[#172B28]">
                      <span className="text-[#0D9488] font-bold mt-0.5">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[#172B28] leading-relaxed">{section.value}</p>
              )}
            </div>
          );
        })}
      </div>

      {medicalData.medications && medicalData.medications.length > 0 && (
        <div className="rounded-2xl border border-[#E3ECE9] bg-white p-4">
          <h4 className="text-[11px] font-bold text-[#5F736F] uppercase tracking-wider mb-3">Prescribed Medications</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-[11px] text-[#5F736F] uppercase border-b border-[#E3ECE9]">
                <tr>
                  <th className="py-2 pr-4 text-left font-semibold">Medicine</th>
                  <th className="py-2 pr-4 text-left font-semibold">Dose / Strength</th>
                  <th className="py-2 pr-4 text-left font-semibold">Frequency</th>
                  <th className="py-2 pr-4 text-left font-semibold">Timing</th>
                  <th className="py-2 text-left font-semibold">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3ECE9]">
                {medicalData.medications.map((med: any, i: number) => (
                  <tr key={i}>
                    <td className="py-2 pr-4 font-semibold text-[#172B28]">{med.name}</td>
                    <td className="py-2 pr-4 text-[#5F736F]">{med.dose || med.strength || "—"}</td>
                    <td className="py-2 pr-4 text-[#5F736F]">{med.frequency || "—"}</td>
                    <td className="py-2 pr-4 text-[#5F736F]">{med.timing || "—"}</td>
                    <td className="py-2 text-[#5F736F]">{med.duration || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function GuidelinesView({ consultationId, data }: { consultationId: string; data?: any }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [selectedFinding, setSelectedFinding] = useState<any>(null);
  const [decision, setDecision] = useState("relevant");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const findings = data?.findings || [];

  if (!data) {
    return (
      <div className="flex items-center justify-center py-16">
        <RefreshCw className="h-5 w-5 animate-spin text-[#0D9488]" />
        <span className="ml-3 text-sm text-[#5F736F]">Loading guidelines...</span>
      </div>
    );
  }

  if (findings.length === 0) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-12 text-center">
        <Shield className="h-8 w-8 mx-auto text-[#CBD5E1] mb-3" />
        <p className="text-sm font-semibold text-[#172B28] mb-1">No guideline findings available</p>
        <p className="text-xs text-[#5F736F]">No verified guideline information is available for this consultation.</p>
      </div>
    );
  }

  const handleReview = async () => {
    if (!selectedFinding) return;
    setIsSubmitting(true);
    try {
      await doctorApi.reviewGuidelineFinding(consultationId, selectedFinding.id, { decision: decision as any, doctor_notes: notes });
      queryClient.invalidateQueries({ queryKey: queryKeys.doctorGuidelines(consultationId) });
      toast.success("Guideline finding reviewed.");
      setSelectedFinding(null);
    } catch (err: any) {
      toast.error(err?.message || "Failed to submit review.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="text-xs text-[#5F736F] mb-2">
        {findings.length} guideline finding{findings.length !== 1 ? "s" : ""} found
      </div>
      {findings.map((finding: any) => (
        <div key={finding.id} className="rounded-2xl border border-[#E3ECE9] bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-[#172B28]">{finding.finding_title}</span>
                <span className="rounded-md bg-[#E7F5F1] px-1.5 py-0.5 text-[10px] font-semibold text-[#123B35]">
                  {finding.organization}
                </span>
                {finding.decision && (
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    finding.decision === "relevant" ? "bg-[#DCFCE7] text-[#166534]"
                    : finding.decision === "not_relevant" ? "bg-[#FEE2E2] text-[#991B1B]"
                    : "bg-[#FEF3C7] text-[#92400E]"
                  }`}>
                    {finding.decision.replace("_", " ")}
                  </span>
                )}
              </div>
              <p className="text-xs text-[#5F736F] mb-2">{finding.evidence}</p>
              {finding.section && (
                <p className="text-[10px] text-[#5F736F] italic">Section: {finding.section}</p>
              )}
            </div>
            <button
              onClick={() => { setSelectedFinding(finding); setDecision("relevant"); setNotes(finding.doctor_notes || ""); }}
              className="shrink-0 rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs font-semibold text-[#123B35] hover:bg-[#E7F5F1] transition"
            >
              Review
            </button>
          </div>
        </div>
      ))}

      {selectedFinding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl space-y-4 border border-[#E3ECE9]">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#172B28]">Review Guideline Finding</h3>
              <button onClick={() => setSelectedFinding(null)} className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#F7F9F8]">
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-xs text-[#5F736F]">{selectedFinding.finding_title}</p>
            <div>
              <label className="text-[11px] font-semibold text-[#172B28] block mb-1">Decision</label>
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
                className="w-full rounded-xl border border-[#E3ECE9] p-2 text-xs"
              >
                <option value="relevant">Relevant — apply to care</option>
                <option value="not_relevant">Not Relevant — dismiss</option>
                <option value="review_later">Review Later</option>
                <option value="add_note">Add Note</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-semibold text-[#172B28] block mb-1">Clinical Notes</label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-xl border border-[#E3ECE9] p-2 text-xs"
                placeholder="Add a clinical observation..."
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-[#E3ECE9]">
              <button onClick={() => setSelectedFinding(null)} className="rounded-xl border border-[#E3ECE9] px-4 py-2 text-xs font-semibold text-[#5F736F]">
                Cancel
              </button>
              <button onClick={handleReview} disabled={isSubmitting} className="rounded-xl bg-[#0D9488] px-4 py-2 text-xs font-semibold text-white hover:bg-[#0F766E] disabled:opacity-50">
                {isSubmitting ? "Saving..." : "Save Review"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LabReportsView({ data }: { data?: any }) {
  const reports = data?.lab_reports || [];

  if (!data) {
    return (
      <div className="flex items-center justify-center py-16">
        <RefreshCw className="h-5 w-5 animate-spin text-[#0D9488]" />
        <span className="ml-3 text-sm text-[#5F736F]">Loading lab reports...</span>
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-12 text-center">
        <FlaskConical className="h-8 w-8 mx-auto text-[#CBD5E1] mb-3" />
        <p className="text-sm font-semibold text-[#172B28] mb-1">No lab reports</p>
        <p className="text-xs text-[#5F736F]">No lab reports have been uploaded for this consultation yet.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white overflow-hidden">
      <table className="w-full text-xs">
        <thead className="border-b border-[#E3ECE9] bg-[#F7F9F8] text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider">
          <tr>
            <th className="px-5 py-3.5 text-left">Test Name</th>
            <th className="px-4 py-3.5 text-left">Value</th>
            <th className="px-4 py-3.5 text-left">Reference Range</th>
            <th className="px-4 py-3.5 text-left">Status</th>
            <th className="px-4 py-3.5 text-left">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#E3ECE9]">
          {reports.map((r: any) => (
            <tr key={r.id} className="hover:bg-[#F8FAFC] transition">
              <td className="px-5 py-3.5 font-semibold text-[#172B28]">{r.test_name}</td>
              <td className="px-4 py-3.5 font-mono">
                {r.verified_value || r.test_value || "—"} {r.verified_unit || r.unit || ""}
              </td>
              <td className="px-4 py-3.5 text-[#5F736F]">{r.reference_range || "—"}</td>
              <td className="px-4 py-3.5">
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold border ${
                  r.status === "verified" || r.status === "reviewed"
                    ? "bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]"
                    : r.status === "awaiting_doctor_review" || r.status === "pending"
                    ? "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                    : "bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]"
                }`}>
                  {r.status.replace(/_/g, " ")}
                </span>
              </td>
              <td className="px-4 py-3.5 text-[#5F736F]">{r.report_date ? formatDate(r.report_date) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditView({ data }: { data?: any }) {
  const trail = data?.audit_trail || [];

  if (!data) {
    return (
      <div className="flex items-center justify-center py-16">
        <RefreshCw className="h-5 w-5 animate-spin text-[#0D9488]" />
        <span className="ml-3 text-sm text-[#5F736F]">Loading audit trail...</span>
      </div>
    );
  }

  if (trail.length === 0) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-12 text-center">
        <History className="h-8 w-8 mx-auto text-[#CBD5E1] mb-3" />
        <p className="text-sm font-semibold text-[#172B28] mb-1">No audit events</p>
        <p className="text-xs text-[#5F736F]">The audit trail is empty for this consultation.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-5">
      <div className="space-y-3">
        {trail.map((event: any, i: number) => (
          <div key={i} className="flex items-start gap-3 text-xs border-b border-[#E3ECE9] pb-3 last:border-0 last:pb-0">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#E7F5F1] text-[#0D9488] shrink-0 mt-0.5">
              <History className="h-3.5 w-3.5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-[#172B28]">{event.action || event.event_type || "Event"}</span>
                {event.actor && <span className="text-[#5F736F]">by {event.actor}</span>}
              </div>
              {event.details && (
                <p className="text-[#5F736F] mt-0.5 leading-relaxed">{typeof event.details === "string" ? event.details : JSON.stringify(event.details)}</p>
              )}
              {event.timestamp && (
                <span className="text-[10px] text-[#5F736F]">{new Date(event.timestamp).toLocaleString()}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoiceNoteSection({ consultationId }: { consultationId: string }) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [draftId, setDraftId] = useState("");
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const queryClient = useQueryClient();

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioPlaybackRef = useRef<HTMLAudioElement | null>(null);

  React.useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => setRecordSeconds((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/ogg";
      mediaRecorderRef.current = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      mediaRecorderRef.current.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
      };
      mediaRecorderRef.current.start();
      setIsRecording(true);
      setRecordSeconds(0);
      setAudioUrl(null);
      setAudioBlob(null);
      setTranscript("");
      setIsConfirmed(false);
    } catch {
      toast.error("Microphone access denied or browser not supported.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
      setIsRecording(false);
    }
  };

  const deleteRecording = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setAudioBlob(null);
    setRecordSeconds(0);
    setTranscript("");
    setIsConfirmed(false);
  };

  const handleTranscribe = async () => {
    if (!audioBlob) { toast.error("No audio recording found."); return; }
    setIsTranscribing(true);
    try {
      // Upload the actual audio blob as a file
      const formData = new FormData();
      const ext = audioBlob.type.includes("webm") ? "webm" : "ogg";
      // Use the doctor voice transcribe endpoint with the actual audio blob
      const res = await doctorApi.transcribeVoiceNote(consultationId, audioBlob);
      setTranscript(res.draft_transcript || "");
      setDraftId(res.draft_id || "");
      toast.success("Audio transcribed. Please review before confirming.");
    } catch (err: any) {
      toast.error(err?.message || "Transcription failed. Check that the consultation exists and audio is valid.");
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleConfirm = async () => {
    if (!transcript.trim()) { toast.error("Transcript is empty."); return; }
    try {
      await doctorApi.confirmVoiceNote(consultationId, {
        draft_id: draftId || "voice-draft",
        final_note_text: transcript,
        category: "clinical_observation",
      });
      setIsConfirmed(true);
      queryClient.invalidateQueries({ queryKey: queryKeys.doctorAuditTrail(consultationId) });
      toast.success("Voice note confirmed and saved to clinical record.");
    } catch (err: any) {
      toast.error(err?.message || "Failed to confirm voice note.");
    }
  };

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-5 shadow-xs">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#E3ECE9]">
        <h4 className="text-xs font-bold text-[#172B28]">Doctor Voice Dictation</h4>
        <span className="text-[10px] text-[#5F736F] font-mono">{formatDuration(recordSeconds)}</span>
      </div>

      <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-[#F7F9F8] border border-[#E3ECE9] mb-4">
        {isRecording ? (
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 animate-pulse text-red-600">
              <Mic className="h-8 w-8" />
            </div>
            <span className="text-xs font-semibold text-red-600">● Recording ({formatDuration(recordSeconds)})</span>
            <button onClick={stopRecording} className="flex items-center gap-1.5 rounded-full bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700 transition">
              <Square className="h-3.5 w-3.5" />Stop Recording
            </button>
          </div>
        ) : !audioUrl ? (
          <button onClick={startRecording} className="flex flex-col items-center gap-2 group">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#E7F5F1] text-[#0D9488] group-hover:scale-105 transition shadow-xs">
              <Mic className="h-7 w-7" />
            </div>
            <span className="text-xs font-semibold text-[#172B28]">Click to Record</span>
            <span className="text-[10px] text-[#5F736F]">Tamil or English spoken notes</span>
          </button>
        ) : (
          <div className="w-full flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => { if (audioPlaybackRef.current) { if (isPlaying) audioPlaybackRef.current.pause(); else audioPlaybackRef.current.play(); setIsPlaying(!isPlaying); } }}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-[#0D9488] text-white hover:bg-[#0F766E] transition"
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
              </button>
              <span className="text-xs font-medium text-[#172B28]">Playback ({formatDuration(recordSeconds)})</span>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={deleteRecording} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="Delete">
                <Trash2 className="h-4 w-4" />
              </button>
              <button onClick={handleTranscribe} disabled={isTranscribing} className="flex items-center gap-1.5 rounded-lg bg-[#123B35] px-3 py-2 text-xs font-semibold text-white hover:bg-[#1A4D45] disabled:opacity-50">
                {isTranscribing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Mic className="h-3.5 w-3.5" />}
                {isTranscribing ? "Transcribing..." : "Transcribe"}
              </button>
            </div>
            <audio ref={audioPlaybackRef} src={audioUrl} onEnded={() => setIsPlaying(false)} className="hidden" />
          </div>
        )}
      </div>

      {transcript && (
        <div className="space-y-3">
          <label className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider block">
            Draft Transcript — Review before confirming
          </label>
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-[#E3ECE9] bg-[#F7F9F8] p-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
          />
          <div className="flex justify-end">
            <button
              onClick={handleConfirm}
              disabled={isConfirmed}
              className={`flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                isConfirmed ? "bg-[#DCFCE7] text-[#166534] border border-[#BBF7D0]" : "bg-[#0D9488] text-white hover:bg-[#0F766E] shadow-sm"
              }`}
            >
              <Check className="h-4 w-4" />
              {isConfirmed ? "Confirmed & Saved" : "Confirm & Save Note"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

interface ConsultationVitalsCardProps {
  consultationId: string;
  vitals?: any;
  onVitalsUpdated: () => void;
}

function ConsultationVitalsCard({ consultationId, vitals, onVitalsUpdated }: ConsultationVitalsCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    height: vitals?.height || vitals?.height_cm || "",
    weight: vitals?.weight || vitals?.weight_kg || "",
    blood_pressure: vitals?.blood_pressure || "",
    pulse: vitals?.pulse || vitals?.pulse_rate || "",
    temperature: vitals?.temperature || vitals?.temperature_f || "",
    oxygen_saturation: vitals?.oxygen_saturation || vitals?.spo2 || "",
    fasting_glucose: vitals?.fasting_glucose || "",
    measurement_source: vitals?.measurement_source || "clinician_entry",
  });

  React.useEffect(() => {
    if (vitals) {
      setFormData({
        height: vitals?.height || vitals?.height_cm || "",
        weight: vitals?.weight || vitals?.weight_kg || "",
        blood_pressure: vitals?.blood_pressure || "",
        pulse: vitals?.pulse || vitals?.pulse_rate || "",
        temperature: vitals?.temperature || vitals?.temperature_f || "",
        oxygen_saturation: vitals?.oxygen_saturation || vitals?.spo2 || "",
        fasting_glucose: vitals?.fasting_glucose || "",
        measurement_source: vitals?.measurement_source || "clinician_entry",
      });
    }
  }, [vitals]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await doctorApi.updateVitals(consultationId, {
        height: formData.height ? String(formData.height) : undefined,
        weight: formData.weight ? String(formData.weight) : undefined,
        blood_pressure: formData.blood_pressure || undefined,
        pulse: formData.pulse ? String(formData.pulse) : undefined,
        temperature: formData.temperature ? String(formData.temperature) : undefined,
        oxygen_saturation: formData.oxygen_saturation ? String(formData.oxygen_saturation) : undefined,
        fasting_glucose: formData.fasting_glucose ? String(formData.fasting_glucose) : undefined,
        measurement_source: formData.measurement_source,
      });
      toast.success("Vitals updated and saved to clinical record");
      setIsEditing(false);
      onVitalsUpdated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to update vitals");
    } finally {
      setIsSaving(false);
    }
  };

  const hasAnyVitals = Boolean(
    vitals &&
    (vitals.height ||
      vitals.height_cm ||
      vitals.weight ||
      vitals.weight_kg ||
      vitals.blood_pressure ||
      vitals.pulse ||
      vitals.pulse_rate ||
      vitals.temperature ||
      vitals.temperature_f ||
      vitals.oxygen_saturation ||
      vitals.spo2 ||
      vitals.fasting_glucose)
  );

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-[#0D9488]" />
          <h3 className="text-sm font-semibold text-[#172B28]">Current-Visit Vitals</h3>
        </div>
        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            className="flex items-center gap-1.5 rounded-lg border border-[#E3ECE9] px-2.5 py-1 text-xs font-medium text-[#123B35] hover:bg-[#F7F9F8] transition"
          >
            <Edit className="h-3 w-3" />
            {hasAnyVitals ? "Edit Vitals" : "Record Vitals"}
          </button>
        ) : (
          <button
            onClick={() => setIsEditing(false)}
            className="flex items-center gap-1 text-xs text-[#5F736F] hover:text-[#172B28]"
          >
            <X className="h-3.5 w-3.5" />
            Cancel
          </button>
        )}
      </div>

      {!isEditing ? (
        hasAnyVitals ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {Boolean(vitals?.blood_pressure) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">Blood Pressure</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.blood_pressure}</span>
                <span className="text-[10px] text-[#5F736F] block">mmHg</span>
              </div>
            )}
            {Boolean(vitals?.pulse || vitals?.pulse_rate) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">Pulse</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.pulse || vitals.pulse_rate}</span>
                <span className="text-[10px] text-[#5F736F] block">bpm</span>
              </div>
            )}
            {Boolean(vitals?.oxygen_saturation || vitals?.spo2) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">SpO2</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.oxygen_saturation || vitals.spo2}</span>
                <span className="text-[10px] text-[#5F736F] block">%</span>
              </div>
            )}
            {Boolean(vitals?.temperature || vitals?.temperature_f) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">Temperature</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.temperature || vitals.temperature_f}</span>
                <span className="text-[10px] text-[#5F736F] block">°F</span>
              </div>
            )}
            {Boolean(vitals?.weight || vitals?.weight_kg) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">Weight</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.weight || vitals.weight_kg}</span>
                <span className="text-[10px] text-[#5F736F] block">kg</span>
              </div>
            )}
            {Boolean(vitals?.height || vitals?.height_cm) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">Height</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.height || vitals.height_cm}</span>
                <span className="text-[10px] text-[#5F736F] block">cm</span>
              </div>
            )}
            {Boolean(vitals?.fasting_glucose) && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 border border-[#E3ECE9]/50">
                <span className="text-[11px] font-medium text-[#5F736F] block">Fasting Glucose</span>
                <span className="text-sm font-bold text-[#172B28]">{vitals.fasting_glucose}</span>
                <span className="text-[10px] text-[#5F736F] block">mg/dL</span>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[#CBD5E1] p-4 text-center">
            <p className="text-xs text-[#5F736F]">No vital signs recorded for this visit yet.</p>
            <p className="text-[11px] text-[#94A3B8] mt-0.5">Click &ldquo;Record Vitals&rdquo; above to record verified measurements.</p>
          </div>
        )
      ) : (
        <form onSubmit={handleSave} className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Blood Pressure</label>
              <input
                type="text"
                placeholder="e.g. 120/80"
                value={formData.blood_pressure}
                onChange={(e) => setFormData({ ...formData, blood_pressure: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Pulse (bpm)</label>
              <input
                type="text"
                placeholder="e.g. 72"
                value={formData.pulse}
                onChange={(e) => setFormData({ ...formData, pulse: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">SpO2 (%)</label>
              <input
                type="text"
                placeholder="e.g. 98"
                value={formData.oxygen_saturation}
                onChange={(e) => setFormData({ ...formData, oxygen_saturation: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Temperature (°F)</label>
              <input
                type="text"
                placeholder="e.g. 98.6"
                value={formData.temperature}
                onChange={(e) => setFormData({ ...formData, temperature: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Weight (kg)</label>
              <input
                type="text"
                placeholder="e.g. 70"
                value={formData.weight}
                onChange={(e) => setFormData({ ...formData, weight: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Height (cm)</label>
              <input
                type="text"
                placeholder="e.g. 175"
                value={formData.height}
                onChange={(e) => setFormData({ ...formData, height: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Fasting Glucose (mg/dL)</label>
              <input
                type="text"
                placeholder="e.g. 95"
                value={formData.fasting_glucose}
                onChange={(e) => setFormData({ ...formData, fasting_glucose: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#5F736F] mb-1">Measurement Source</label>
              <select
                value={formData.measurement_source}
                onChange={(e) => setFormData({ ...formData, measurement_source: e.target.value })}
                className="w-full rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
              >
                <option value="clinician_entry">Clinician Entry</option>
                <option value="triage_nurse">Triage Nurse</option>
                <option value="patient_reported">Patient Reported</option>
                <option value="connected_device">Connected Device</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              className="rounded-lg border border-[#E3ECE9] px-3 py-1.5 text-xs font-medium text-[#5F736F] hover:bg-[#F7F9F8]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="flex items-center gap-1.5 rounded-lg bg-[#0D9488] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#0F766E] disabled:opacity-50"
            >
              {isSaving ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              Save Vitals
            </button>
          </div>
        </form>
      )}

      {vitals?.measurement_source && (
        <div className="mt-3 flex items-center justify-between text-[10px] text-[#94A3B8] border-t border-[#F1F5F9] pt-2">
          <span>Source: {vitals.measurement_source}</span>
          {vitals.recorded_by && <span>Recorded by: {vitals.recorded_by}</span>}
        </div>
      )}
    </div>
  );
}
