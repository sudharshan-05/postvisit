"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import {
  Activity,
  Calendar,
  Pill,
  FlaskConical,
  Shield,
  History,
  Sparkles,
  ArrowRight,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Clock,
  User,
  Heart,
  FileText,
  Search,
} from "lucide-react";
import { AskAIDrawer } from "@/components/assistant/AskAIDrawer";
import { PatientClinicalOverview } from "@/types";

interface DoctorEHRViewProps {
  patientId: string;
  consultationId?: string;
  onSelectVisit?: (consultationId: string) => void;
}

type EHRTab = "overview" | "timeline" | "medications" | "reports" | "guidelines" | "audit";

export function DoctorEHRView({ patientId, consultationId, onSelectVisit }: DoctorEHRViewProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<EHRTab>("overview");
  const [isAIOpen, setIsAIOpen] = useState(false);
  const [aiContextPrompt, setAiContextPrompt] = useState<string | undefined>(undefined);

  const { data: ehr, isLoading, error } = useQuery({
    queryKey: queryKeys.doctorOverview(patientId, consultationId),
    queryFn: () => doctorApi.getPatientClinicalOverview(patientId, consultationId),
    enabled: !!patientId,
  });

  const handleAskAIAboutContext = (contextDesc: string) => {
    setAiContextPrompt(contextDesc);
    setIsAIOpen(true);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 bg-white rounded-3xl border border-[#E3ECE9]">
        <Activity className="h-8 w-8 text-[#0D9488] animate-spin mb-3" />
        <span className="text-xs font-semibold text-[#172B28]">Loading Patient Longitudinal EHR...</span>
      </div>
    );
  }

  if (error || !ehr) {
    return (
      <div className="p-12 text-center bg-white rounded-3xl border border-[#E3ECE9]">
        <AlertCircle className="h-10 w-10 text-[#CBD5E1] mx-auto mb-3" />
        <h3 className="text-sm font-bold text-[#172B28] mb-1">Clinical Record Not Available</h3>
        <p className="text-xs text-[#5F736F]">
          Unable to retrieve electronic health record for patient {patientId}.
        </p>
      </div>
    );
  }

  const visits = ehr.visit_history || [];
  const lastVisit = ehr.last_visit;
  const medications = ehr.medications || [];
  const labReports = ehr.lab_reports || [];
  const guidelines = ehr.guideline_findings || [];
  const auditTrail = ehr.audit_history || [];

  return (
    <div className="space-y-6">
      {/* Patient Header Banner */}
      <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-5 border-b border-[#E3ECE9]">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#123B35] text-white text-xl font-bold shadow-xs">
              {ehr.name ? ehr.name.charAt(0) : "P"}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-[#172B28]">{ehr.name}</h2>
                <span className="rounded-lg bg-[#E7F5F1] px-2.5 py-1 text-xs font-bold text-[#123B35]">
                  Patient ID: {ehr.patient_id}
                </span>
                {ehr.blood_group && (
                  <span className="rounded-lg bg-[#FEE2E2] px-2.5 py-1 text-xs font-semibold text-[#991B1B]">
                    {ehr.blood_group}
                  </span>
                )}
              </div>
              <p className="text-xs text-[#5F736F] mt-1">
                {ehr.age ? `${ehr.age} y.o.` : ""} {ehr.gender ? `• ${ehr.gender}` : ""} • Outpatient Longitudinal Record
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleAskAIAboutContext(`Ask about ${ehr.name}'s complete clinical record (ID: ${ehr.patient_id})`)}
              className="flex items-center gap-1.5 rounded-full border border-[#0D9488] bg-[#E7F5F1] px-4 py-2 text-xs font-semibold text-[#123B35] hover:bg-[#0D9488] hover:text-white transition shadow-2xs"
            >
              <Sparkles className="h-3.5 w-3.5 text-[#0D9488]" />
              <span>Ask PostVisit AI About Patient</span>
            </button>
          </div>
        </div>

        {/* Chronic Conditions & Allergies Badges */}
        <div className="pt-4 flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[#5F736F] text-[11px] uppercase tracking-wider">Conditions:</span>
            {ehr.chronic_conditions && ehr.chronic_conditions.length > 0 ? (
              ehr.chronic_conditions.map((c, i) => (
                <span key={i} className="rounded-md bg-[#EFF6FF] px-2 py-0.5 text-[11px] font-medium text-[#1E40AF] border border-[#BFDBFE]">
                  {c}
                </span>
              ))
            ) : (
              <span className="text-[#5F736F] italic">No chronic conditions documented</span>
            )}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <span className="font-semibold text-[#5F736F] text-[11px] uppercase tracking-wider">Allergies:</span>
            {ehr.allergies && ehr.allergies.length > 0 ? (
              ehr.allergies.map((a, i) => (
                <span key={i} className="rounded-md bg-[#FEF2F2] px-2 py-0.5 text-[11px] font-medium text-[#991B1B] border border-[#FECACA]">
                  {a}
                </span>
              ))
            ) : (
              <span className="text-[#5F736F] italic">NKDA (No known drug allergies)</span>
            )}
          </div>
        </div>
      </div>

      {/* EHR Section Navigation Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-[#E3ECE9] pb-0">
        {[
          { key: "overview", label: "Overview", icon: <Activity className="h-4 w-4" /> },
          { key: "timeline", label: "Health Timeline", icon: <Calendar className="h-4 w-4" /> },
          { key: "medications", label: `Medications (${medications.length})`, icon: <Pill className="h-4 w-4" /> },
          { key: "reports", label: `Lab Reports (${labReports.length})`, icon: <FlaskConical className="h-4 w-4" /> },
          { key: "guidelines", label: `Guidelines (${guidelines.length})`, icon: <Shield className="h-4 w-4" /> },
          { key: "audit", label: `Audit Trail (${auditTrail.length})`, icon: <History className="h-4 w-4" /> },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as EHRTab)}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold whitespace-nowrap border-b-2 transition -mb-px ${
              activeTab === tab.key
                ? "border-[#0D9488] text-[#0D9488] bg-white rounded-t-xl"
                : "border-transparent text-[#5F736F] hover:text-[#172B28] hover:border-[#E3ECE9]"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB CONTENT: 1. OVERVIEW */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 space-y-6">
            {/* Last Visit Card */}
            {lastVisit ? (
              <div className="rounded-3xl border border-[#CCFBF1] bg-white p-6 shadow-xs space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
                  <div>
                    <span className="text-[10px] font-bold text-[#0D9488] uppercase tracking-wider block">
                      Most Recent Consultation
                    </span>
                    <h3 className="text-base font-bold text-[#172B28]">
                      {formatDate(lastVisit.date)}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    {lastVisit.summary_approved && (
                      <span className="flex items-center gap-1 rounded-full bg-[#DCFCE7] px-2.5 py-1 text-[11px] font-semibold text-[#166534] border border-[#BBF7D0]">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Summary Approved
                      </span>
                    )}
                    <button
                      onClick={() => {
                        if (onSelectVisit) onSelectVisit(lastVisit.consultation_id);
                        else router.push(`/doctor/consultations/${lastVisit.consultation_id}`);
                      }}
                      className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#0F766E] transition shadow-2xs"
                    >
                      <span>View Visit Record</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                <div className="space-y-3 text-xs">
                  {lastVisit.reason_for_visit && (
                    <div>
                      <span className="font-semibold text-[#172B28] block mb-0.5">Reason for Visit:</span>
                      <p className="text-[#5F736F]">{lastVisit.reason_for_visit}</p>
                    </div>
                  )}

                  {lastVisit.reported_symptoms && lastVisit.reported_symptoms.length > 0 && (
                    <div>
                      <span className="font-semibold text-[#172B28] block mb-1">Reported Symptoms:</span>
                      <div className="flex flex-wrap gap-1.5">
                        {lastVisit.reported_symptoms.map((s, idx) => (
                          <span key={idx} className="rounded-md bg-[#F7F9F8] px-2 py-0.5 text-xs text-[#172B28] border border-[#E3ECE9]">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {lastVisit.doctor_recommendations && lastVisit.doctor_recommendations.length > 0 && (
                    <div>
                      <span className="font-semibold text-[#172B28] block mb-1">Doctor Recommendations:</span>
                      <ul className="space-y-1">
                        {lastVisit.doctor_recommendations.map((rec, idx) => (
                          <li key={idx} className="flex items-start gap-1.5 text-[#5F736F]">
                            <span className="text-[#0D9488] font-bold">•</span>
                            <span>{rec}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-3xl border border-[#E3ECE9] bg-white p-8 text-center text-xs text-[#5F736F]">
                No previous visits available.
              </div>
            )}

            {/* Current Consultation Clinical Findings (HPI, Examination, Recommendations) */}
            {ehr.history_of_present_illness && (
              <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-3">
                <h4 className="text-xs font-bold text-[#172B28] uppercase tracking-wider">
                  History of Present Illness (HPI)
                </h4>
                <p className="text-xs text-[#172B28] leading-relaxed bg-[#F7F9F8] p-4 rounded-2xl border border-[#E3ECE9]">
                  {ehr.history_of_present_illness}
                </p>
              </div>
            )}

            {ehr.follow_up_instructions && (
              <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-2">
                <h4 className="text-xs font-bold text-[#172B28] uppercase tracking-wider">
                  Doctor Follow-up Directives
                </h4>
                <p className="text-xs text-[#172B28] leading-relaxed">
                  {ehr.follow_up_instructions}
                </p>
              </div>
            )}
          </div>

          {/* Right Column: Vitals, Quick Links, Actions */}
          <div className="lg:col-span-4 space-y-6">
            {/* Vital Signs Card */}
            {ehr.vitals && Object.keys(ehr.vitals).length > 0 && (
              <div className="rounded-3xl border border-[#E3ECE9] bg-white p-5 shadow-xs space-y-3">
                <h4 className="text-xs font-bold text-[#172B28] uppercase tracking-wider">
                  Recorded Vital Signs
                </h4>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {ehr.vitals.blood_pressure && (
                    <div className="rounded-xl bg-[#F7F9F8] p-2.5 border border-[#E3ECE9]">
                      <span className="text-[10px] text-[#5F736F] block">Blood Pressure</span>
                      <strong className="text-xs text-[#172B28]">{ehr.vitals.blood_pressure}</strong>
                    </div>
                  )}
                  {ehr.vitals.pulse && (
                    <div className="rounded-xl bg-[#F7F9F8] p-2.5 border border-[#E3ECE9]">
                      <span className="text-[10px] text-[#5F736F] block">Pulse</span>
                      <strong className="text-xs text-[#172B28]">{ehr.vitals.pulse} bpm</strong>
                    </div>
                  )}
                  {ehr.vitals.fasting_glucose && (
                    <div className="rounded-xl bg-[#F7F9F8] p-2.5 border border-[#E3ECE9]">
                      <span className="text-[10px] text-[#5F736F] block">Fasting Glucose</span>
                      <strong className="text-xs text-[#172B28]">{ehr.vitals.fasting_glucose} mg/dL</strong>
                    </div>
                  )}
                  {ehr.vitals.weight_kg && (
                    <div className="rounded-xl bg-[#F7F9F8] p-2.5 border border-[#E3ECE9]">
                      <span className="text-[10px] text-[#5F736F] block">Weight</span>
                      <strong className="text-xs text-[#172B28]">{ehr.vitals.weight_kg} kg</strong>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Longitudinal Summary Quick Stats */}
            <div className="rounded-3xl border border-[#E3ECE9] bg-[#F7F9F8] p-5 space-y-3 text-xs">
              <h4 className="text-xs font-bold text-[#123B35] uppercase tracking-wider">
                EHR Summary Overview
              </h4>
              <div className="space-y-2">
                <div className="flex justify-between py-1 border-b border-[#E3ECE9]">
                  <span className="text-[#5F736F]">Total Encounters</span>
                  <strong className="text-[#172B28]">{visits.length}</strong>
                </div>
                <div className="flex justify-between py-1 border-b border-[#E3ECE9]">
                  <span className="text-[#5F736F]">Active Prescriptions</span>
                  <strong className="text-[#172B28]">{medications.length}</strong>
                </div>
                <div className="flex justify-between py-1 border-b border-[#E3ECE9]">
                  <span className="text-[#5F736F]">Lab Reports on File</span>
                  <strong className="text-[#172B28]">{labReports.length}</strong>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-[#5F736F]">Audit Events</span>
                  <strong className="text-[#172B28]">{auditTrail.length}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: 2. CHRONOLOGICAL HEALTH TIMELINE */}
      {activeTab === "timeline" && (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
            <div>
              <h3 className="text-sm font-bold text-[#172B28]">Chronological Visit Timeline</h3>
              <p className="text-xs text-[#5F736F]">
                Click any visit to load the complete authoritative encounter details.
              </p>
            </div>
            <span className="text-xs text-[#5F736F] font-semibold">{visits.length} encounters documented</span>
          </div>

          {visits.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#5F736F]">
              No previous visits available.
            </div>
          ) : (
            <div className="relative pl-6 space-y-6 border-l-2 border-[#E7F5F1]">
              {visits.map((v, i) => (
                <div key={v.consultation_id || i} className="relative group">
                  {/* Timeline dot */}
                  <div className={`absolute -left-[31px] top-1.5 h-4 w-4 rounded-full border-2 border-white ${
                    i === 0 ? "bg-[#0D9488] ring-4 ring-[#E7F5F1]" : "bg-[#CBD5E1]"
                  }`} />

                  <div className="rounded-2xl border border-[#E3ECE9] bg-[#F7F9F8] p-5 group-hover:border-[#0D9488] group-hover:bg-white transition shadow-2xs">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-[#172B28]">{formatDate(v.date)}</span>
                        {i === 0 && (
                          <span className="rounded-md bg-[#E7F5F1] px-2 py-0.5 text-[10px] font-bold text-[#123B35]">
                            Latest Encounter
                          </span>
                        )}
                        {v.summary_approved && (
                          <span className="rounded-full bg-[#DCFCE7] px-2.5 py-0.5 text-[10px] font-semibold text-[#166534] border border-[#BBF7D0]">
                            Summary Approved
                          </span>
                        )}
                      </div>

                      <button
                        onClick={() => {
                          if (onSelectVisit) onSelectVisit(v.consultation_id);
                          else router.push(`/doctor/consultations/${v.consultation_id}`);
                        }}
                        className="flex items-center gap-1 rounded-xl bg-white px-3 py-1.5 text-xs font-semibold text-[#123B35] border border-[#E3ECE9] hover:bg-[#0D9488] hover:text-white transition shadow-2xs"
                      >
                        <span>Open Consultation</span>
                        <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    {v.reason_for_visit && (
                      <p className="text-xs text-[#172B28] font-medium mb-1">
                        Reason: {v.reason_for_visit}
                      </p>
                    )}

                    {v.reported_symptoms && v.reported_symptoms.length > 0 && (
                      <p className="text-xs text-[#5F736F]">
                        Symptoms: {v.reported_symptoms.join(", ")}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: 3. MEDICATIONS */}
      {activeTab === "medications" && (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
            <div>
              <h3 className="text-sm font-bold text-[#172B28]">Prescribed Medications</h3>
              <p className="text-xs text-[#5F736F]">
                Active pharmacotherapy extracted from doctor-verified consultations.
              </p>
            </div>
          </div>

          {medications.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#5F736F]">
              No active medications documented in this patient's record.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#E3ECE9] bg-[#F7F9F8] text-[11px] font-semibold text-[#5F736F] uppercase">
                  <tr>
                    <th className="px-4 py-3">Medicine</th>
                    <th className="px-4 py-3">Strength / Dose</th>
                    <th className="px-4 py-3">Frequency</th>
                    <th className="px-4 py-3">Timing</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Copilot Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E3ECE9]">
                  {medications.map((m, idx) => (
                    <tr key={idx} className="hover:bg-[#F8FAFC] transition">
                      <td className="px-4 py-3.5 font-bold text-[#172B28]">
                        {m.name || m.medicine_name}
                      </td>
                      <td className="px-4 py-3.5 text-[#5F736F]">
                        {m.strength || m.dose || "—"}
                      </td>
                      <td className="px-4 py-3.5 text-[#5F736F]">{m.frequency || "—"}</td>
                      <td className="px-4 py-3.5 text-[#5F736F]">{m.timing || "—"}</td>
                      <td className="px-4 py-3.5 text-[#5F736F]">{m.duration || "Ongoing"}</td>
                      <td className="px-4 py-3.5">
                        <span className="rounded-full bg-[#E7F5F1] px-2.5 py-0.5 text-[10px] font-semibold text-[#123B35]">
                          {m.review_status || m.approval_status || "Approved"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          onClick={() => handleAskAIAboutContext(`Explain clinical justification and precautions for ${m.name || m.medicine_name} (${m.strength || ""}) for patient ${ehr.name}`)}
                          className="rounded-lg bg-white px-2.5 py-1 text-[11px] font-semibold text-[#0D9488] border border-[#0D9488] hover:bg-[#E7F5F1] transition shadow-2xs"
                        >
                          Ask AI
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: 4. LAB REPORTS */}
      {activeTab === "reports" && (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
            <div>
              <h3 className="text-sm font-bold text-[#172B28]">Diagnostic & Lab Reports</h3>
              <p className="text-xs text-[#5F736F]">
                Verified and patient-submitted lab reports with doctor provenance.
              </p>
            </div>
          </div>

          {labReports.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#5F736F]">
              No lab reports uploaded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#E3ECE9] bg-[#F7F9F8] text-[11px] font-semibold text-[#5F736F] uppercase">
                  <tr>
                    <th className="px-4 py-3">Test Name</th>
                    <th className="px-4 py-3">Value</th>
                    <th className="px-4 py-3">Reference Range</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E3ECE9]">
                  {labReports.map((r, idx) => (
                    <tr key={r.id || idx} className="hover:bg-[#F8FAFC] transition">
                      <td className="px-4 py-3.5 font-bold text-[#172B28]">{r.test_name}</td>
                      <td className="px-4 py-3.5 font-mono text-[#172B28]">
                        {r.verified_value || r.test_value || "—"} {r.verified_unit || r.unit || ""}
                      </td>
                      <td className="px-4 py-3.5 text-[#5F736F]">{r.reference_range || "—"}</td>
                      <td className="px-4 py-3.5 text-[#5F736F]">{r.report_date ? formatDate(r.report_date) : "—"}</td>
                      <td className="px-4 py-3.5">
                        <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold border ${
                          (r.status === "verified" || r.review_status === "REPORT_REVIEWED")
                            ? "bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]"
                            : "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                        }`}>
                          {r.status || r.review_status || "Pending Review"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          onClick={() => handleAskAIAboutContext(`Analyze lab report ${r.test_name} (result: ${r.verified_value || r.test_value} ${r.unit || ""}) for patient ${ehr.name}`)}
                          className="rounded-lg bg-white px-2.5 py-1 text-[11px] font-semibold text-[#0D9488] border border-[#0D9488] hover:bg-[#E7F5F1] transition shadow-2xs"
                        >
                          Ask AI
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: 5. GUIDELINE FINDINGS */}
      {activeTab === "guidelines" && (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
            <div>
              <h3 className="text-sm font-bold text-[#172B28]">Guideline Cross-Reference Findings</h3>
              <p className="text-xs text-[#5F736F]">
                Evidence-backed clinical decision support findings from Indian guidelines (ICMR, RSSDI, CSI).
              </p>
            </div>
          </div>

          {guidelines.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#5F736F]">
              No verified guideline information available.
            </div>
          ) : (
            <div className="space-y-3">
              {guidelines.map((g, idx) => (
                <div key={g.id || idx} className="rounded-2xl border border-[#E3ECE9] bg-[#F7F9F8] p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-[#172B28]">{g.finding_title}</span>
                    <span className="rounded-md bg-[#E7F5F1] px-2 py-0.5 text-[10px] font-bold text-[#123B35]">
                      {g.organization}
                    </span>
                    {g.decision && (
                      <span className="rounded-full bg-[#DCFCE7] px-2 py-0.5 text-[10px] font-semibold text-[#166534]">
                        Decision: {g.decision.replace("_", " ")}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#5F736F] leading-relaxed">{g.evidence}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: 6. AUDIT TRAIL */}
      {activeTab === "audit" && (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
            <div>
              <h3 className="text-sm font-bold text-[#172B28]">Clinical Audit History</h3>
              <p className="text-xs text-[#5F736F]">
                Immutable chronological log of all ingestion, modifications, and clinician reviews.
              </p>
            </div>
          </div>

          {auditTrail.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#5F736F]">
              No audit history recorded.
            </div>
          ) : (
            <div className="space-y-3">
              {auditTrail.map((ev, idx) => (
                <div key={ev.id || idx} className="flex items-start gap-3 p-3 rounded-xl bg-[#F7F9F8] border border-[#E3ECE9] text-xs">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#E7F5F1] text-[#0D9488] shrink-0 mt-0.5">
                    <History className="h-3 w-3" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#172B28]">{ev.event_type || ev.action || "Action"}</span>
                      {ev.actor_role && (
                        <span className="text-[10px] text-[#5F736F]">by {ev.actor_role}</span>
                      )}
                      {ev.timestamp && (
                        <span className="text-[10px] text-[#5F736F] ml-auto">
                          {new Date(ev.timestamp).toLocaleString()}
                        </span>
                      )}
                    </div>
                    {ev.action_description && (
                      <p className="text-[#5F736F] mt-0.5">{ev.action_description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Ask AI Drawer */}
      <AskAIDrawer
        isOpen={isAIOpen}
        onClose={() => {
          setIsAIOpen(false);
          setAiContextPrompt(undefined);
        }}
        patientId={patientId}
        consultationId={consultationId || lastVisit?.consultation_id}
        initialPrompt={aiContextPrompt}
      />
    </div>
  );
}
