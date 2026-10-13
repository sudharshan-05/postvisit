"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { consultationsApi } from "@/lib/api/consultations";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import {
  Upload,
  Search,
  Clock,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  FileAudio,
  ChevronRight,
  Mic,
} from "lucide-react";
import { AudioRecorder } from "@/components/clinical/AudioRecorder";
import { toast } from "sonner";

export default function DoctorConsultationsPage() {
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.doctorQueue({ filter_type: filterType }),
    queryFn: () => doctorApi.listConsultations({ filter_type: filterType, page: 1, page_size: 50 }),
  });

  const consultations = data?.consultations || [];
  const filtered = consultations.filter((c) => {
    const q = searchQuery.toLowerCase();
    const cid = c.consultation_id || c.id || "";
    return (
      c.patient_id?.toLowerCase().includes(q) ||
      c.patient_name?.toLowerCase().includes(q) ||
      cid.toLowerCase().includes(q)
    );
  });

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    toast.info(`Uploading encounter audio: ${file.name}...`);
    try {
      const res = await consultationsApi.upload(file, false);
      toast.success(`Encounter queued for processing! ID: ${res.consultation_id.substring(0, 8)}...`);
      refetch();
    } catch (err: any) {
      toast.error(err?.message || "Upload failed.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Clinical Consultations Queue
          </h2>
          <p className="text-xs text-[#5F736F]">
            Upload encounter audio or review clinical extractions awaiting sign-off.
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
                toast.success(`Consultation ${cid.substring(0, 8)}... created!`);
                refetch();
              }}
            />
          </div>
        </div>
      )}

      {/* Main List Card */}
      <div className="rounded-2xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden">
        {/* Controls */}
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
              placeholder="Search MRN or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-[#E3ECE9] bg-white py-1.5 pl-8 pr-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
            />
          </div>
        </div>

        {/* List items */}
        <div className="divide-y divide-[#E3ECE9]">
          {isLoading ? (
            <div className="p-12 text-center text-xs text-[#5F736F]">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto text-[#0D9488] mb-2" />
              Loading consultations...
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center text-xs text-[#5F736F]">
              <FileAudio className="h-8 w-8 mx-auto text-[#CBD5E1] mb-2" />
              <p className="font-semibold text-[#172B28] mb-1">No consultations found</p>
              <p>No encounters match your current filter criteria.</p>
            </div>
          ) : (
            filtered.map((c) => {
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
                <div
                  key={targetId}
                  className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 hover:bg-[#F8FAFC] transition gap-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#E7F5F1] text-[#0D9488] shrink-0">
                      <FileAudio className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-[#172B28]">
                          {c.patient_name || "Ananya Patel"}
                        </span>
                        <span className="text-[11px] text-[#5F736F] font-mono">
                          MRN: {c.patient_id || "PT-89241"}
                        </span>
                      </div>
                      <p className="text-xs text-[#5F736F] mt-0.5">
                        {c.chief_complaint || "Routine Clinical Review"} • {formatDate(c.consultation_date || c.created_at || "")}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
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

                    <Link
                      href={`/doctor/consultations/${targetId}`}
                      className="inline-flex items-center gap-1 rounded-xl bg-white px-3.5 py-1.5 text-xs font-semibold text-[#123B35] border border-[#E3ECE9] hover:bg-[#E7F5F1] hover:text-[#0D9488] transition shadow-2xs"
                    >
                      <span>{isPending || isNeedsReview ? "Review" : "View"}</span>
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
