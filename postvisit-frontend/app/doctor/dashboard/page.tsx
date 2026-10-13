"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { consultationsApi, WorkflowProgressResponse } from "@/lib/api/consultations";
import { queryKeys } from "@/lib/query/keys";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  Activity,
  Clock,
  AlertCircle,
  CheckCircle2,
  Search,
  Upload,
  RefreshCw,
  FileAudio,
  ChevronRight,
  X,
  Mic,
} from "lucide-react";
import { AudioRecorder } from "@/components/clinical/AudioRecorder";
import { toast } from "sonner";

export default function DoctorDashboardPage() {
  const queryClient = useQueryClient();
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [activeUploadId, setActiveUploadId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<WorkflowProgressResponse | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  // Fetch consultations queue from backend
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.doctorQueue({ filter_type: filterType }),
    queryFn: () => doctorApi.listConsultations({ filter_type: filterType, page: 1, page_size: 50 }),
  });

  const consultations = data?.consultations || [];

  // Filter consultations based on search input
  const filteredConsultations = consultations.filter((c) => {
    const q = searchQuery.toLowerCase();
    const cid = c.consultation_id || c.id || "";
    return (
      c.patient_id?.toLowerCase().includes(q) ||
      c.patient_name?.toLowerCase().includes(q) ||
      cid.toLowerCase().includes(q)
    );
  });

  // Calculate truthful statistics directly from backend response
  const totalCount = data?.total ?? consultations.length;
  const pendingCount =
    data?.pending_review_count ??
    consultations.filter(
      (c) =>
        c.status === "PENDING REVIEW" ||
        c.status === "awaiting_review" ||
        c.status === "pending_doctor_review"
    ).length;
  const needsAttentionCount =
    data?.needs_attention_count ??
    consultations.filter((c) => c.status === "NEEDS REVIEW" || c.needs_attention).length;
  const approvedCount =
    data?.completed_count ??
    consultations.filter(
      (c) =>
        c.status === "APPROVED" ||
        c.status === "approved" ||
        c.status === "completed"
    ).length;

  // Poll workflow progress if an upload is active
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (activeUploadId) {
      const pollProgress = async () => {
        try {
          const prog = await consultationsApi.getProgress(activeUploadId);
          setUploadProgress(prog);
          if (prog.is_completed || prog.status === "completed" || prog.status === "failed") {
            if (interval) clearInterval(interval);
            refetch();
            queryClient.invalidateQueries({ queryKey: queryKeys.consultationDetail(activeUploadId) });
            toast.success("Consultation processing completed!");
          }
        } catch {
          // Keep polling
        }
      };
      pollProgress();
      interval = setInterval(pollProgress, 2500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeUploadId, refetch, queryClient]);

  // Audio Upload handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    toast.info(`Uploading ${file.name} for clinical processing...`);

    try {
      const res = await consultationsApi.upload(file, false);
      setActiveUploadId(res.consultation_id);
      toast.success(`Consultation queued! ID: ${res.consultation_id.substring(0, 8)}...`);
      refetch();
    } catch (err: any) {
      toast.error(err?.message || "Failed to upload encounter audio.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Welcome Banner & Action Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Good morning, Dr. Ramanathan
          </h2>
          <p className="text-xs text-[#5F736F] mt-0.5">
            Here is your daily clinical queue and AI-transcribed consultations overview.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsRecordModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-[#123B35] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#1A4D45] transition"
          >
            <Mic className="h-4 w-4 text-[#0D9488]" />
            <span>Record Consultation</span>
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".wav,.mp3,.mp4,.m4a,.aac,.webm,.ogg"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-2 rounded-xl border border-[#CBD5E1] bg-white px-3.5 py-2 text-xs font-semibold text-[#172B28] shadow-2xs hover:bg-[#F7F9F8] transition disabled:opacity-50"
          >
            <Upload className="h-4 w-4 text-[#0D9488]" />
            <span>{isUploading ? "Uploading..." : "Upload Audio"}</span>
          </button>
          <button
            onClick={() => refetch()}
            className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
            title="Refresh queue"
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? "animate-spin text-[#0D9488]" : ""}`} />
          </button>
        </div>
      </div>

      {/* Record Consultation Encounter Modal */}
      {isRecordModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-xl">
            <AudioRecorder
              mode="consultation_encounter"
              onClose={() => setIsRecordModalOpen(false)}
              onConsultationCreated={(cid) => {
                setIsRecordModalOpen(false);
                setActiveUploadId(cid);
                refetch();
              }}
            />
          </div>
        </div>
      )}

      {/* Real-time processing progress modal / drawer */}
      {activeUploadId && uploadProgress && (
        <div className="rounded-3xl border border-[#0D9488] bg-[#F7F9F8] p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-[#E3ECE9] pb-2">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-[#0D9488] animate-spin" />
              <h3 className="text-xs font-bold text-[#172B28]">
                Active Ingestion Pipeline: Consultation {activeUploadId.substring(0, 8)}...
              </h3>
            </div>
            <button
              onClick={() => setActiveUploadId(null)}
              className="rounded-lg p-1 text-[#5F736F] hover:bg-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
            {uploadProgress.steps?.map((step, idx) => (
              <div
                key={idx}
                className={`p-2.5 rounded-xl border text-[11px] font-medium transition ${
                  step.status === "completed"
                    ? "bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]"
                    : step.status === "in_progress"
                    ? "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A] animate-pulse"
                    : step.status === "failed"
                    ? "bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]"
                    : "bg-white text-[#5F736F] border-[#E3ECE9]"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1 font-semibold">
                  {step.status === "completed" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  ) : step.status === "in_progress" ? (
                    <RefreshCw className="h-3 w-3 animate-spin shrink-0" />
                  ) : (
                    <div className="h-2 w-2 rounded-full bg-slate-300" />
                  )}
                  <span className="truncate">{step.name}</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider block opacity-75">
                  {step.status.replace("_", " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Statistics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-[#E3ECE9] bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-[#5F736F] mb-2">
            <span className="text-xs font-medium">Total Consultations</span>
            <Activity className="h-4 w-4 text-[#0D9488]" />
          </div>
          <span className="text-2xl font-bold text-[#172B28]">{totalCount}</span>
          <span className="text-[10px] text-[#5F736F] block mt-1">Across all departments</span>
        </div>

        <div className="rounded-2xl border border-[#FDE68A] bg-[#FEF3C7] p-4 shadow-xs">
          <div className="flex items-center justify-between text-[#92400E] mb-2">
            <span className="text-xs font-semibold">Pending Review</span>
            <Clock className="h-4 w-4 text-[#92400E]" />
          </div>
          <span className="text-2xl font-bold text-[#92400E]">{pendingCount}</span>
          <span className="text-[10px] text-[#92400E] block mt-1">Awaiting clinician sign-off</span>
        </div>

        <div className="rounded-2xl border border-[#FECACA] bg-[#FEE2E2] p-4 shadow-xs">
          <div className="flex items-center justify-between text-[#991B1B] mb-2">
            <span className="text-xs font-semibold">Needs Attention</span>
            <AlertCircle className="h-4 w-4 text-[#991B1B]" />
          </div>
          <span className="text-2xl font-bold text-[#991B1B]">{needsAttentionCount}</span>
          <span className="text-[10px] text-[#991B1B] block mt-1">Guideline flags & alerts</span>
        </div>

        <div className="rounded-2xl border border-[#BBF7D0] bg-[#DCFCE7] p-4 shadow-xs">
          <div className="flex items-center justify-between text-[#166534] mb-2">
            <span className="text-xs font-semibold">Approved</span>
            <CheckCircle2 className="h-4 w-4 text-[#166534]" />
          </div>
          <span className="text-2xl font-bold text-[#166534]">{approvedCount}</span>
          <span className="text-[10px] text-[#166534] block mt-1">Released to patient portal</span>
        </div>
      </div>

      {/* Consultation Queue Workspace */}
      <div className="rounded-2xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden">
        {/* Table Top Controls & Filter Tabs */}
        <div className="p-4 border-b border-[#E3ECE9] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-[#F7F9F8]">
          <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto">
            {["all", "pending_review", "needs_attention", "completed"].map((tab) => (
              <button
                key={tab}
                onClick={() => setFilterType(tab)}
                className={`rounded-xl px-3 py-1.5 text-xs font-semibold capitalize transition ${
                  filterType === tab
                    ? "bg-[#123B35] text-white shadow-xs"
                    : "bg-white text-[#5F736F] border border-[#E3ECE9] hover:bg-[#E7F5F1]"
                }`}
              >
                {tab.replace("_", " ")}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#5F736F]" />
            <input
              type="text"
              placeholder="Filter by patient name or MRN..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-[#E3ECE9] bg-white py-1.5 pl-8 pr-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
            />
          </div>
        </div>

        {/* Queue Table */}
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-12 text-center text-xs text-[#5F736F]">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto text-[#0D9488] mb-2" />
              Loading clinical consultation queue...
            </div>
          ) : filteredConsultations.length === 0 ? (
            <div className="p-12 text-center text-xs text-[#5F736F]">
              <FileAudio className="h-8 w-8 mx-auto text-[#CBD5E1] mb-2" />
              <p className="font-semibold text-[#172B28] mb-1">No consultations found</p>
              <p>Upload a new consultation audio recording to start clinical processing.</p>
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#E3ECE9] bg-[#F7F9F8] text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Patient / MRN</th>
                  <th className="px-4 py-3.5">Encounter Date</th>
                  <th className="px-4 py-3.5">Chief Complaint</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3ECE9]">
                {filteredConsultations.map((c) => {
                  const targetId = c.consultation_id || c.id;
                  const isPending =
                    c.status === "PENDING REVIEW" ||
                    c.status === "awaiting_review" ||
                    c.status === "pending_doctor_review";
                  const isApproved =
                    c.status === "APPROVED" || c.status === "approved" || c.status === "completed";
                  const isNeedsReview = c.status === "NEEDS REVIEW" || c.needs_attention;
                  const isFailed = c.status === "FAILED" || c.status === "failed";
                  const isProcessing =
                    c.status === "PROCESSING" || c.status === "processing" || c.status === "queued";

                  return (
                    <tr key={targetId} className="hover:bg-[#F8FAFC] transition">
                      <td className="px-5 py-3.5">
                        <div className="font-semibold text-[#172B28]">
                          {c.patient_name || "Ananya Patel"}
                        </div>
                        <div className="text-[11px] text-[#5F736F] font-mono">
                          MRN: {c.patient_id || "PT-89241"}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-[#5F736F]">
                        {formatDate(c.consultation_date || c.created_at || "")}
                      </td>
                      <td className="px-4 py-3.5 text-[#172B28] max-w-xs truncate">
                        {c.chief_complaint || "Routine Clinical Review"}
                      </td>
                      <td className="px-4 py-3.5">
                        {isPending && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[#FEF3C7] px-2.5 py-1 text-[11px] font-semibold text-[#92400E] border border-[#FDE68A]">
                            <Clock className="h-3 w-3" />
                            Pending Review
                          </span>
                        )}
                        {isNeedsReview && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[#FEE2E2] px-2.5 py-1 text-[11px] font-semibold text-[#991B1B] border border-[#FECACA]">
                            <AlertCircle className="h-3 w-3" />
                            Needs Review
                          </span>
                        )}
                        {isApproved && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[#DCFCE7] px-2.5 py-1 text-[11px] font-semibold text-[#166534] border border-[#BBF7D0]">
                            <CheckCircle2 className="h-3 w-3" />
                            Approved
                          </span>
                        )}
                        {isFailed && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[#FEE2E2] px-2.5 py-1 text-[11px] font-semibold text-[#991B1B] border border-[#FECACA]">
                            Failed
                          </span>
                        )}
                        {isProcessing && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[#E0F2FE] px-2.5 py-1 text-[11px] font-semibold text-[#075985] border border-[#BAE6FD]">
                            <RefreshCw className="h-3 w-3 animate-spin" />
                            Processing
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <Link
                          href={`/doctor/consultations/${targetId}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-[#123B35] border border-[#E3ECE9] hover:bg-[#E7F5F1] hover:text-[#0D9488] transition shadow-2xs"
                        >
                          <span>{isPending || isNeedsReview ? "Review" : "View"}</span>
                          <ChevronRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
