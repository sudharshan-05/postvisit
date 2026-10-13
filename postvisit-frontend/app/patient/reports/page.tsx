"use client";

import React, { useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { patientApi } from "@/lib/api/patient";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import {
  FlaskConical,
  Upload,
  Plus,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileText,
  X,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

export default function PatientReportsPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showManualModal, setShowManualModal] = useState(false);
  const [testName, setTestName] = useState("");
  const [testValue, setTestValue] = useState("");
  const [unit, setUnit] = useState("");
  const [facility, setFacility] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [ocrReport, setOcrReport] = useState<any | null>(null);
  const [ocrResults, setOcrResults] = useState<any[]>([]);

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.patientLabReports(),
    queryFn: () => patientApi.listLabReports().catch(() => ({ lab_reports: [], total: 0 })),
  });

  const reports = data?.lab_reports || [];

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const toastId = toast.loading("Uploading and extracting report with clinical OCR...");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", "lab_report");

      const res = await patientApi.uploadLabReport(formData);
      const rep = Array.isArray(res) ? res[0] : res?.lab_reports?.[0] || res;
      
      if (rep && (rep.results?.length > 0 || rep.ocr_results?.length > 0)) {
        const extracted = rep.results || rep.ocr_results || [];
        setOcrReport(rep);
        setOcrResults(extracted);
        toast.success(`OCR Extracted ${extracted.length} test result(s). Please verify before submitting.`, { id: toastId });
      } else {
        toast.success("Lab report uploaded successfully and queued for doctor review!", { id: toastId });
      }
      refetch();
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail?.message ||
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to upload lab report. Please check file format and try again.",
        { id: toastId }
      );
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleConfirmOcr = async () => {
    if (!ocrReport?.id) return;
    setIsSubmitting(true);
    try {
      await patientApi.confirmLabReport(ocrReport.id, {
        patient_confirmed: true,
        corrected_results: ocrResults,
      });
      toast.success("Extracted test results verified and submitted to your doctor!");
      setOcrReport(null);
      refetch();
    } catch (err: any) {
      toast.error(err?.message || "Failed to confirm extracted results.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testName.trim()) return;

    setIsSubmitting(true);
    try {
      await patientApi.createManualLabReport({
        test_name: testName,
        test_value: testValue,
        unit: unit,
        facility_name: facility,
        patient_notes: notes,
      });
      toast.success("Lab report summary submitted for doctor review!");
      setShowManualModal(false);
      setTestName("");
      setTestValue("");
      setUnit("");
      setFacility("");
      setNotes("");
      refetch();
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail?.message ||
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to submit test results. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Your Lab Reports & Tests
          </h2>
          <p className="text-xs text-[#5F736F]">
            View verified reports, submit test results, or upload documentation for clinician review.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1.5 rounded-xl border border-[#0D9488] bg-[#E7F5F1] px-4 py-2 text-xs font-semibold text-[#123B35] hover:bg-[#0D9488] hover:text-white transition disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            <span>{isUploading ? "Uploading..." : "Upload Document"}</span>
          </button>
          <button
            onClick={() => setShowManualModal(true)}
            className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#0F766E] transition"
          >
            <Plus className="h-4 w-4" />
            <span>Enter Test Results</span>
          </button>
          <button
            onClick={() => refetch()}
            className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? "animate-spin text-[#0D9488]" : ""}`} />
          </button>
        </div>
      </div>

      {/* Reports List */}
      {isLoading ? (
        <div className="p-8 text-center bg-white rounded-3xl border border-[#E3ECE9] text-xs text-[#5F736F]">
          Loading laboratory records...
        </div>
      ) : reports.length === 0 ? (
        <div className="p-8 text-center bg-white rounded-3xl border border-[#E3ECE9] text-xs text-[#5F736F]">
          No lab reports uploaded yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reports.map((r: any) => {
            const isVerified = r.status === "verified" || r.status === "reviewed" || r.doctor_reviewed;
            return (
              <div
                key={r.id || r.report_id}
                className="rounded-3xl border border-[#E3ECE9] bg-white p-5 shadow-xs space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-[#172B28]">{r.test_name}</h3>
                    <span className="text-[11px] text-[#5F736F]">
                      {r.facility_name || "Diagnostic Laboratory"} • {formatDate(r.report_date || r.created_at)}
                    </span>
                  </div>
                  {isVerified ? (
                    <span className="flex items-center gap-1 rounded-full bg-[#DCFCE7] px-2.5 py-1 text-[10px] font-semibold text-[#166534] border border-[#BBF7D0]">
                      <CheckCircle2 className="h-3 w-3" />
                      Verified by Doctor
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 rounded-full bg-[#FEF3C7] px-2.5 py-1 text-[10px] font-semibold text-[#92400E] border border-[#FDE68A]">
                      <Clock className="h-3 w-3" />
                      Awaiting Doctor Review
                    </span>
                  )}
                </div>

                <div className="rounded-2xl bg-[#F7F9F8] p-3 border border-[#E3ECE9] flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-[#5F736F] uppercase tracking-wider block">
                      Result Value
                    </span>
                    <span className="text-lg font-bold text-[#172B28]">
                      {r.test_value || r.value || "Recorded"}{" "}
                      <span className="text-xs font-normal text-[#5F736F]">{r.unit}</span>
                    </span>
                  </div>
                  {r.reference_range && (
                    <div className="text-right">
                      <span className="text-[10px] text-[#5F736F] uppercase tracking-wider block">
                        Target Range
                      </span>
                      <span className="text-xs font-semibold text-[#0D9488]">
                        {r.reference_range}
                      </span>
                    </div>
                  )}
                </div>

                {r.doctor_notes && (
                  <div className="rounded-xl bg-[#E7F5F1] p-3 text-xs text-[#123B35]">
                    <strong className="block mb-0.5 font-semibold">Doctor Annotation:</strong>
                    "{r.doctor_notes}"
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}


      {/* Manual Entry Modal */}
      {showManualModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border border-[#E3ECE9] space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
              <h3 className="text-sm font-bold text-[#172B28]">Submit Lab Test Summary</h3>
              <button
                onClick={() => setShowManualModal(false)}
                className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#F7F9F8]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleManualSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                  Test Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Fasting Blood Sugar, HbA1c"
                  value={testName}
                  onChange={(e) => setTestName(e.target.value)}
                  className="w-full rounded-xl border border-[#E3ECE9] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                    Value
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 118"
                    value={testValue}
                    onChange={(e) => setTestValue(e.target.value)}
                    className="w-full rounded-xl border border-[#E3ECE9] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                    Unit
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. mg/dL, %"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className="w-full rounded-xl border border-[#E3ECE9] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                  Diagnostic Lab / Facility Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Apollo Diagnostics"
                  value={facility}
                  onChange={(e) => setFacility(e.target.value)}
                  className="w-full rounded-xl border border-[#E3ECE9] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-[#172B28] block mb-1">
                  Patient Notes (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. Fasting 10 hours overnight"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full rounded-xl border border-[#E3ECE9] p-2.5 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#E3ECE9]">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="rounded-xl border border-[#E3ECE9] px-4 py-2 text-xs font-semibold text-[#5F736F]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-xl bg-[#0D9488] px-5 py-2 text-xs font-semibold text-white hover:bg-[#0F766E]"
                >
                  {isSubmitting ? "Submitting..." : "Submit for Doctor Review"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* OCR Extracted Results Verification Modal */}
      {ocrReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-2xl rounded-3xl bg-white p-6 shadow-2xl border border-[#CCFBF1] space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#E7F5F1] text-[#0D9488]">
                  <FlaskConical className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#172B28]">
                    Verify OCR Extracted Test Results
                  </h3>
                  <p className="text-[11px] text-[#5F736F]">
                    Our clinical document engine extracted these results. Please confirm or correct any fields before physician review.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setOcrReport(null)}
                className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#F7F9F8]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[350px] overflow-y-auto space-y-3 p-1">
              {ocrResults.map((item, idx) => (
                <div key={idx} className="p-3.5 rounded-2xl bg-[#F7F9F8] border border-[#E3ECE9] grid grid-cols-1 sm:grid-cols-12 gap-3 text-xs items-center">
                  <div className="sm:col-span-4">
                    <label className="text-[10px] font-semibold text-[#5F736F] uppercase block mb-0.5">Test Name</label>
                    <input
                      type="text"
                      value={item.test_name}
                      onChange={(e) => {
                        const copy = [...ocrResults];
                        copy[idx].test_name = e.target.value;
                        setOcrResults(copy);
                      }}
                      className="w-full rounded-xl border border-[#CBD5E1] bg-white p-2 text-xs font-semibold text-[#172B28]"
                    />
                  </div>
                  <div className="sm:col-span-3">
                    <label className="text-[10px] font-semibold text-[#5F736F] uppercase block mb-0.5">Value</label>
                    <input
                      type="text"
                      value={item.value}
                      onChange={(e) => {
                        const copy = [...ocrResults];
                        copy[idx].value = e.target.value;
                        setOcrResults(copy);
                      }}
                      className="w-full rounded-xl border border-[#CBD5E1] bg-white p-2 text-xs font-mono font-bold text-[#172B28]"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-[10px] font-semibold text-[#5F736F] uppercase block mb-0.5">Unit</label>
                    <input
                      type="text"
                      value={item.unit}
                      onChange={(e) => {
                        const copy = [...ocrResults];
                        copy[idx].unit = e.target.value;
                        setOcrResults(copy);
                      }}
                      className="w-full rounded-xl border border-[#CBD5E1] bg-white p-2 text-xs text-[#5F736F]"
                    />
                  </div>
                  <div className="sm:col-span-3">
                    <label className="text-[10px] font-semibold text-[#5F736F] uppercase block mb-0.5">Reference Range</label>
                    <input
                      type="text"
                      value={item.reference_range || ""}
                      onChange={(e) => {
                        const copy = [...ocrResults];
                        copy[idx].reference_range = e.target.value;
                        setOcrResults(copy);
                      }}
                      className="w-full rounded-xl border border-[#CBD5E1] bg-white p-2 text-xs text-[#5F736F]"
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-[#E3ECE9]">
              <span className="text-[11px] text-[#5F736F]">
                {ocrResults.length} test{ocrResults.length !== 1 ? "s" : ""} detected from report
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setOcrReport(null)}
                  className="rounded-xl border border-[#E3ECE9] px-4 py-2 text-xs font-semibold text-[#5F736F] hover:bg-[#F7F9F8]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmOcr}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#0F766E] disabled:opacity-50"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{isSubmitting ? "Submitting..." : "Confirm & Send to Doctor"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
