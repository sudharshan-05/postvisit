"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { patientApi } from "@/lib/api/patient";
import { queryKeys } from "@/lib/query/keys";
import { formatDate } from "@/lib/utils";
import {
  Calendar,
  Pill,
  Heart,
  Activity,
  FileText,
  ChevronRight,
  Sparkles,
  Stethoscope,
  Clock,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { HealthMetricGrid } from "@/components/patient/HealthMetricCard";
import { HealthTrendsChart } from "@/components/charts/HealthTrendsChart";
import { RecoveryChecklist } from "@/components/patient/RecoveryChecklist";

export default function PatientDashboardPage() {
  // Fetch patient overview from backend
  const { data: overview, isLoading } = useQuery({
    queryKey: queryKeys.patientOverview(),
    queryFn: () => patientApi.getOverview().catch(() => null),
  });

  // Fetch patient profile
  const { data: profile } = useQuery({
    queryKey: queryKeys.patientProfile(),
    queryFn: () => patientApi.getProfile().catch(() => null),
  });

  // Fetch last visit summary
  const { data: lastVisit } = useQuery({
    queryKey: queryKeys.patientLastVisit(),
    queryFn: () => patientApi.getLastVisit().catch(() => null),
  });

  // Fetch active medications
  const { data: medsData } = useQuery({
    queryKey: queryKeys.patientMedications(),
    queryFn: () => patientApi.getMedications().catch(() => ({ medications: [] })),
  });

  const latestTrend = overview?.health_trends?.[overview.health_trends.length - 1];
  const activeMeds = medsData?.medications || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Good morning, {profile?.full_name || overview?.patient_name || "Patient"}
          </h2>
          <p className="text-xs text-[#5F736F]">
            Here is your longitudinal health overview and doctor-approved recovery instructions.
          </p>
        </div>

        <Link
          href="/patient/assistant"
          className="flex items-center gap-1.5 rounded-full border border-[#0D9488] bg-[#E7F5F1] px-4 py-2 text-xs font-semibold text-[#123B35] hover:bg-[#0D9488] hover:text-white transition shadow-2xs"
        >
          <Sparkles className="h-3.5 w-3.5 text-[#0D9488]" />
          <span>Ask PostVisit AI</span>
        </Link>
      </div>

      {/* Main Spline Health Trends Chart */}
      <HealthTrendsChart data={overview?.health_trends} />

      {/* Health Metric Cards Grid */}
      <HealthMetricGrid
        weight={latestTrend?.weight_kg ? `${latestTrend.weight_kg} kg` : "Not recorded"}
        height={profile?.blood_group ? `Blood: ${profile.blood_group}` : "Not recorded"}
        age={profile?.age ? `${profile.age} y.o.` : "Not recorded"}
        pulse={latestTrend?.systolic_bp ? `${latestTrend.systolic_bp}/${latestTrend.diastolic_bp} mmHg` : "Not recorded"}
      />

      {/* 2-Column Section: Left Action Checklist + Last Visit; Right Attending Doctor + Treatment */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (Span 7) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Last Visit Quick Summary Card */}
          <div className="rounded-3xl border border-[#CCFBF1] bg-white p-6 shadow-xs">
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#E3ECE9]">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#E7F5F1] text-[#0D9488]">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#172B28]">Your Last Consultation</h3>
                  <p className="text-[11px] text-[#5F736F]">
                    {lastVisit?.visit_date || overview?.last_visit_date
                      ? `${formatDate(lastVisit?.visit_date || overview?.last_visit_date)} • ${lastVisit?.doctor_name || "Attending Physician"}`
                      : "No previous visits recorded"}
                  </p>
                </div>
              </div>

              {lastVisit?.approved_summary_available || lastVisit?.summary_approved ? (
                <span className="flex items-center gap-1 rounded-full bg-[#DCFCE7] px-2.5 py-1 text-[11px] font-semibold text-[#166534] border border-[#BBF7D0]">
                  <CheckCircle2 className="h-3 w-3" />
                  Summary Approved
                </span>
              ) : (
                <span className="flex items-center gap-1 rounded-full bg-[#FEF3C7] px-2.5 py-1 text-[11px] font-semibold text-[#92400E] border border-[#FDE68A]">
                  <Clock className="h-3 w-3" />
                  Review Pending
                </span>
              )}
            </div>

            {/* Approved instructions summary */}
            <div className="space-y-3 text-xs">
              <div className="rounded-2xl bg-[#F7F9F8] p-3.5 border border-[#E3ECE9]">
                <span className="font-semibold text-[#172B28] block mb-1">
                  Doctor's Primary Directives:
                </span>
                <p className="text-[#5F736F] leading-relaxed">
                  {lastVisit?.diagnosis_summary ||
                    lastVisit?.instructions ||
                    lastVisit?.summary?.summary_text ||
                    "No doctor-approved summary instructions released for this visit yet."}
                </p>
              </div>

              <div className="flex items-center justify-between pt-2">
                <Link
                  href="/patient/visits"
                  className="text-xs font-semibold text-[#0D9488] hover:underline flex items-center gap-1"
                >
                  <span>View All Approved Visits</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Link>

                <Link
                  href="/patient/assistant"
                  className="rounded-xl border border-[#0D9488] bg-white px-3 py-1.5 text-xs font-semibold text-[#0D9488] hover:bg-[#E7F5F1] transition"
                >
                  Ask AI About This Visit
                </Link>
              </div>
            </div>
          </div>

          {/* Action Checklist */}
          <RecoveryChecklist consultationId={overview?.last_consultation_id} />
        </div>

        {/* Right Column: Attending Doctor & Prescriptions */}
        <div className="lg:col-span-5 space-y-6">
          {/* Attending Doctor Specialist Card */}
          <div className="rounded-3xl border border-[#E3ECE9] bg-white p-5 shadow-xs">
            <h3 className="text-xs font-bold text-[#5F736F] uppercase tracking-wider mb-3">
              Attending Physician
            </h3>
            <div className="flex items-center gap-3.5 p-3 rounded-2xl bg-[#F7F9F8] border border-[#E3ECE9]">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#123B35] text-white">
                <Stethoscope className="h-6 w-6 text-[#0D9488]" />
              </div>
              <div className="flex-1">
                <span className="text-xs font-bold text-[#172B28] block">
                  {lastVisit?.doctor_name || "Dr. A. Ramanathan, MD"}
                </span>
                <span className="text-[11px] text-[#5F736F] block">
                  Cardiology & Internal Medicine
                </span>
                <span className="text-[10px] text-[#0D9488] font-medium block mt-0.5">
                  Verified PostVisit Clinical Staff
                </span>
              </div>
            </div>
          </div>

          {/* Treatment / Prescriptions Cards */}
          <div className="rounded-3xl border border-[#E3ECE9] bg-white p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#F1F5F9]">
              <h3 className="text-xs font-bold text-[#172B28]">Active Doctor-Approved Medications</h3>
              <Link href="/patient/visits" className="text-[11px] text-[#0D9488] font-semibold hover:underline">
                See all
              </Link>
            </div>

            <div className="space-y-2.5">
              {activeMeds.length === 0 ? (
                <p className="text-xs text-[#5F736F] italic py-3 text-center">
                  No active prescribed medications on file.
                </p>
              ) : (
                activeMeds.map((med, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-3 p-3 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0]"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-[#0D9488]">
                      <Pill className="h-5 w-5" />
                    </div>
                    <div className="flex-1">
                      <span className="text-xs font-bold text-[#172B28] block">
                        {med.medicine_name || med.name} {med.strength || med.dose}
                      </span>
                      <span className="text-[11px] text-[#5F736F]">
                        {med.frequency || "As directed"} • {med.timing || med.instructions || "After food"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

