"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import { CheckCircle2, Clock, FileCheck, ChevronRight, RefreshCw } from "lucide-react";

export default function DoctorSummaryReviewsPage() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.doctorQueue({ filter_type: "pending_review" }),
    queryFn: () => doctorApi.listConsultations({ filter_type: "pending_review", page: 1, page_size: 50 }),
  });

  const pendingList = data?.consultations || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Patient Summary Review Queue
          </h2>
          <p className="text-xs text-[#5F736F]">
            Verify and approve AI-generated summaries before releasing them to the patient portal.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
        >
          <RefreshCw className={`h-4 w-4 ${isRefetching ? "animate-spin text-[#0D9488]" : ""}`} />
        </button>
      </div>

      <div className="rounded-2xl border border-[#E3ECE9] bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-xs text-[#5F736F]">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto text-[#0D9488] mb-2" />
            Loading summary review queue...
          </div>
        ) : pendingList.length === 0 ? (
          <div className="p-12 text-center text-xs text-[#5F736F]">
            <CheckCircle2 className="h-8 w-8 mx-auto text-[#16A34A] mb-2" />
            <p className="font-semibold text-[#172B28] mb-1">All summaries up to date</p>
            <p>There are no pending patient summaries requiring review right now.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#E3ECE9]">
            {pendingList.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between p-4 hover:bg-[#F8FAFC] transition"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FEF3C7] text-[#92400E]">
                    <Clock className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="font-semibold text-xs text-[#172B28] block">
                      {c.patient_name || "Jane Doe"}
                    </span>
                    <span className="text-[11px] text-[#5F736F]">
                      Encounter Date: {formatDate(c.created_at)} • MRN: {c.patient_id || "PT-89241"}
                    </span>
                  </div>
                </div>

                <Link
                  href={`/doctor/consultations/${c.id}`}
                  className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-[#0F766E] transition"
                >
                  <span>Review & Release</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
