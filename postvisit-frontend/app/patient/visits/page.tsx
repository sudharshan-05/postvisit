"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { patientApi } from "@/lib/api/patient";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import { Calendar, CheckCircle2, Clock, ChevronRight, FileText, AlertCircle, RefreshCw } from "lucide-react";

export default function PatientVisitsPage() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.patientHistory(1, 20),
    queryFn: () => patientApi.getHistory(1, 20).catch(() => ({ consultations: [], total: 0 })),
  });

  const visits = data?.consultations || [];


  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Your Visit History
          </h2>
          <p className="text-xs text-[#5F736F]">
            Chronological clinical consultations. Only doctor-approved summaries are accessible.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
        >
          <RefreshCw className={`h-4 w-4 ${isRefetching ? "animate-spin text-[#0D9488]" : ""}`} />
        </button>
      </div>

      {isLoading ? (
        <div className="p-8 text-center bg-white rounded-3xl border border-[#E3ECE9] text-xs text-[#5F736F]">
          Loading consultation history...
        </div>
      ) : visits.length === 0 ? (
        <div className="p-8 text-center bg-white rounded-3xl border border-[#E3ECE9] text-xs text-[#5F736F]">
          No previous visits available.
        </div>
      ) : (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden divide-y divide-[#E3ECE9]">
          {visits.map((v: any) => {
            const isApproved = v.summary_status === "approved" || v.summary_approved;
            return (
              <div
                key={v.id || v.consultation_id}
                className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 hover:bg-[#F8FAFC] transition gap-4"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#E7F5F1] text-[#0D9488]">
                    <Calendar className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-[#172B28]">
                        {formatDate(v.visit_date)}
                      </span>
                      <span className="text-xs text-[#5F736F]">
                        • {v.doctor_name || "Attending Physician"}
                      </span>
                    </div>
                    <p className="text-xs text-[#5F736F] mt-0.5">
                      {v.reason || "Clinical Consultation"}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
                  {isApproved ? (
                    <span className="flex items-center gap-1 rounded-full bg-[#DCFCE7] px-3 py-1 text-xs font-semibold text-[#166534] border border-[#BBF7D0]">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Summary Approved
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 rounded-full bg-[#FEF3C7] px-3 py-1 text-xs font-semibold text-[#92400E] border border-[#FDE68A]">
                      <Clock className="h-3.5 w-3.5" />
                      Pending Doctor Review
                    </span>
                  )}

                  {isApproved && (
                    <Link
                      href={`/patient/dashboard?consultation_id=${v.consultation_id || v.id}`}
                      className="flex items-center gap-1 rounded-xl bg-white px-3.5 py-2 text-xs font-semibold text-[#123B35] border border-[#E3ECE9] hover:bg-[#E7F5F1] hover:text-[#0D9488] transition shadow-2xs"
                    >
                      <span>View Summary</span>
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

