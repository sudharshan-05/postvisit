"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import {
  FlaskConical,
  Search,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileText,
  X,
  RefreshCw,
} from "lucide-react";
import { LabReportItem } from "@/types";
import { toast } from "sonner";

export default function DoctorLabReportsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedReport, setSelectedReport] = useState<LabReportItem | null>(null);
  const [verifiedValue, setVerifiedValue] = useState("");
  const [verifiedUnit, setVerifiedUnit] = useState("");
  const [doctorNotes, setDoctorNotes] = useState("");
  const [clarificationText, setClarificationText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.doctorLabReports(),
    queryFn: () => doctorApi.listLabReports().catch(() => ({ lab_reports: [], total: 0 })),
  });

  const reports = data?.lab_reports || [];

  const handleOpenReview = (report: any) => {
    setSelectedReport(report);
    setVerifiedValue(report.verified_value || report.patient_value || report.test_value || "");
    setVerifiedUnit(report.verified_unit || report.patient_unit || report.unit || "");
    setDoctorNotes(report.doctor_notes || "");
    setClarificationText("");
  };

  const handleReviewAction = async (decision: "verified" | "rejected" | "clarification_needed") => {
    if (!selectedReport) return;
    setIsSubmitting(true);

    try {
      await doctorApi.reviewLabReport(selectedReport.id, {
        decision,
        verified_value: verifiedValue,
        verified_unit: verifiedUnit,
        doctor_notes: doctorNotes,
        clarification_request: clarificationText,
      });
      toast.success(
        decision === "verified"
          ? "Lab report verified and committed to clinical record!"
          : decision === "clarification_needed"
          ? "Clarification request sent to patient portal."
          : "Lab report marked as rejected."
      );
      setSelectedReport(null);
      refetch();
    } catch (err: any) {
      toast.error(err?.message || `Failed to update report status: ${decision}`);
      setSelectedReport(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Lab Report Management
          </h2>
          <p className="text-xs text-[#5F736F]">
            Review patient-submitted and hospital lab documents with audit provenance.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
        >
          <RefreshCw className={`h-4 w-4 ${isRefetching ? "animate-spin text-[#0D9488]" : ""}`} />
        </button>
      </div>

      {/* Reports Table */}
      <div className="rounded-2xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="h-6 w-6 animate-spin text-[#0D9488]" />
            <span className="ml-3 text-xs text-[#5F736F]">Loading lab reports...</span>
          </div>
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <FlaskConical className="h-10 w-10 text-[#CBD5E1] mb-3" />
            <h3 className="text-sm font-semibold text-[#172B28] mb-1">No lab reports found</h3>
            <p className="text-xs text-[#5F736F] max-w-md">
              Lab reports uploaded by patients or received from diagnostic facilities will appear here for review and verification.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#E3ECE9] bg-[#F7F9F8] text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider">
              <tr>
                <th className="px-5 py-3.5">Patient / MRN</th>
                <th className="px-4 py-3.5">Test Name</th>
                <th className="px-4 py-3.5">Reported Value</th>
                <th className="px-4 py-3.5">Reference Range</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-5 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3ECE9]">
              {reports.map((r: any) => {
                const statusStr = (r.review_status || r.status || "").toLowerCase();
                const isPending =
                  statusStr.includes("pending") ||
                  statusStr.includes("awaiting") ||
                  statusStr.includes("submitted") ||
                  statusStr === "unreviewed";
                const isVerified =
                  statusStr.includes("verified") ||
                  statusStr.includes("reviewed");
                const val = r.patient_value || r.test_value || r.verified_value || "—";
                const unitStr = r.patient_unit || r.unit || r.verified_unit || "";

                return (
                  <tr key={r.id} className="hover:bg-[#F8FAFC] transition">
                    <td className="px-5 py-3.5">
                      <span className="font-semibold text-[#172B28] block">
                        {r.patient_id}
                      </span>
                      <span className="text-[10px] text-[#5F736F]">
                        {r.facility_name || r.file_name || "Diagnostic Center"}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-medium text-[#172B28]">
                      {r.test_name || r.report_name}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[#172B28]">
                      <strong>{val}</strong> {unitStr}
                    </td>
                    <td className="px-4 py-3.5 text-[#5F736F]">
                      {r.reference_range || "N/A"}
                    </td>
                    <td className="px-4 py-3.5">
                      {isPending ? (
                        <span className="rounded-full bg-[#FEF3C7] px-2.5 py-1 text-[10px] font-semibold text-[#92400E] border border-[#FDE68A]">
                          Awaiting Review
                        </span>
                      ) : isVerified ? (
                        <span className="rounded-full bg-[#DCFCE7] px-2.5 py-1 text-[10px] font-semibold text-[#166534] border border-[#BBF7D0]">
                          Verified
                        </span>
                      ) : (
                        <span className="rounded-full bg-[#FEE2E2] px-2.5 py-1 text-[10px] font-semibold text-[#991B1B] border border-[#FECACA]">
                          Rejected
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => handleOpenReview(r)}
                        className="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-[#123B35] border border-[#E3ECE9] hover:bg-[#E7F5F1] hover:text-[#0D9488] transition shadow-2xs"
                      >
                        {isPending ? "Review & Verify" : "View Details"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Doctor Review Dialog */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl border border-[#E3ECE9] space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
              <div>
                <h3 className="text-sm font-bold text-[#172B28]">
                  Review Lab Report: {selectedReport.test_name}
                </h3>
                <p className="text-[11px] text-[#5F736F]">
                  Patient MRN: {selectedReport.patient_id} • Reported on {selectedReport.report_date}
                </p>
              </div>
              <button
                onClick={() => setSelectedReport(null)}
                className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#F7F9F8]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Patient notes callout */}
            {selectedReport.patient_notes && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 text-xs text-[#5F736F] border border-[#E3ECE9]">
                <strong className="text-[#172B28] block mb-0.5">Patient Notes:</strong>
                "{selectedReport.patient_notes}"
              </div>
            )}

            {/* Clinician verification fields */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                  Verified Metric Value
                </label>
                <input
                  type="text"
                  value={verifiedValue}
                  onChange={(e) => setVerifiedValue(e.target.value)}
                  className="w-full rounded-xl border border-[#E3ECE9] p-2 text-xs font-mono"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                  Unit
                </label>
                <input
                  type="text"
                  value={verifiedUnit}
                  onChange={(e) => setVerifiedUnit(e.target.value)}
                  className="w-full rounded-xl border border-[#E3ECE9] p-2 text-xs font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                Clinician Annotation / Notes
              </label>
              <textarea
                rows={2}
                value={doctorNotes}
                onChange={(e) => setDoctorNotes(e.target.value)}
                placeholder="Add clinical observations or medication adjustments..."
                className="w-full rounded-xl border border-[#E3ECE9] p-2 text-xs"
              />
            </div>

            {/* Action buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-[#E3ECE9]">
              <button
                onClick={() => handleReviewAction("rejected")}
                disabled={isSubmitting}
                className="rounded-xl border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"
              >
                Reject Report
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleReviewAction("clarification_needed")}
                  disabled={isSubmitting}
                  className="rounded-xl border border-amber-200 px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50"
                >
                  Request Clarification
                </button>
                <button
                  onClick={() => handleReviewAction("verified")}
                  disabled={isSubmitting}
                  className="rounded-xl bg-[#0D9488] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#0F766E]"
                >
                  Verify & Commit
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
