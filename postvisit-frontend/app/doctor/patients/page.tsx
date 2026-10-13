"use client";

import React, { useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

import { useQuery } from "@tanstack/react-query";
import { doctorApi } from "@/lib/api/doctor";
import { queryKeys } from "@/lib/query/keys";
import { DoctorEHRView } from "@/components/clinical/DoctorEHRView";
import { Users, Search, RefreshCw, ChevronRight, UserCheck } from "lucide-react";

function DoctorPatientsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const requestedPatientId = searchParams.get("patient_id") || "PT-89241";
  const [selectedPatientId, setSelectedPatientId] = useState<string>(requestedPatientId);
  const [search, setSearch] = useState("");


  // Fetch consultations list to extract unique real patients
  const { data: queueData, isLoading: loadingQueue, refetch } = useQuery({
    queryKey: queryKeys.doctorQueue({ page: 1, page_size: 50 }),
    queryFn: () => doctorApi.listConsultations({ page: 1, page_size: 50 }),
  });

  const consultations = queueData?.consultations || [];

  // Group consultations into unique patients from real backend records
  const patientMap = new Map<string, { id: string; name: string; lastVisit: string; count: number; status: string }>();

  // Ensure default patient PT-89241 is present
  patientMap.set("PT-89241", {
    id: "PT-89241",
    name: "Ananya Patel",
    lastVisit: "2026-10-04",
    count: consultations.filter(c => c.patient_id === "PT-89241").length || 1,
    status: "Active Monitoring",
  });

  consultations.forEach((c) => {
    if (c.patient_id) {
      const existing = patientMap.get(c.patient_id);
      if (existing) {
        existing.count += 1;
        if (c.consultation_date && c.consultation_date > existing.lastVisit) {
          existing.lastVisit = c.consultation_date;
        }
      } else {
        patientMap.set(c.patient_id, {
          id: c.patient_id,
          name: c.patient_name || `Patient ${c.patient_id}`,
          lastVisit: c.consultation_date || c.created_at || "Recent",
          count: 1,
          status: c.status || "Active",
        });
      }
    }
  });

  const patientsList = Array.from(patientMap.values());
  const filteredPatients = patientsList.filter(
    (p) => p.name.toLowerCase().includes(search.toLowerCase()) || p.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Patient Cohort Selector Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Patient Longitudinal EHR
          </h2>
          <p className="text-xs text-[#5F736F]">
            Continuous clinical record, medical history, consultations timeline, and diagnostics.
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#5F736F]" />
            <input
              type="text"
              placeholder="Search patient or MRN..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-[#E3ECE9] bg-white py-1.5 pl-8 pr-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
            />
          </div>

          <button
            onClick={() => refetch()}
            className="rounded-xl border border-[#E3ECE9] bg-white p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
            title="Refresh EHR"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Quick Patient Switcher Pills */}
      {filteredPatients.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider whitespace-nowrap">
            Select Patient:
          </span>
          {filteredPatients.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                setSelectedPatientId(p.id);
                router.replace(`/doctor/patients?patient_id=${p.id}`);
              }}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition border ${
                selectedPatientId === p.id
                  ? "bg-[#123B35] text-white border-[#123B35] shadow-xs"
                  : "bg-white text-[#5F736F] border-[#E3ECE9] hover:bg-[#E7F5F1] hover:text-[#123B35]"
              }`}
            >
              <UserCheck className="h-3.5 w-3.5" />
              <span>{p.name} ({p.id})</span>
            </button>
          ))}
        </div>
      )}

      {/* Render Longitudinal Doctor EHR */}
      <DoctorEHRView patientId={selectedPatientId} />
    </div>
  );
}

export default function DoctorPatientsPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center bg-white rounded-3xl border border-[#E3ECE9] text-xs text-[#5F736F]">
          Loading patient clinical directory...
        </div>
      }
    >
      <DoctorPatientsContent />
    </Suspense>
  );
}

