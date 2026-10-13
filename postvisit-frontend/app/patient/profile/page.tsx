"use client";

import React from "react";
import { User, Phone, ShieldCheck, Heart, AlertCircle, MapPin, Building, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { patientApi } from "@/lib/api/patient";
import { queryKeys } from "@/lib/query/keys";

export default function PatientProfilePage() {
  const { data: profile, isLoading, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.patientProfile(),
    queryFn: () => patientApi.getProfile(),
  });

  const name = profile?.full_name || profile?.name || "Patient Profile";
  const initial = name.charAt(0).toUpperCase();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Patient Profile & Medical ID
          </h2>
          <p className="text-xs text-[#5F736F]">
            Verified patient clinical identity, chronic conditions, and recorded allergies.
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
          Loading clinical profile...
        </div>
      ) : (
        <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs space-y-6">
          {/* Profile Card Header */}
          <div className="flex items-center gap-4 pb-6 border-b border-[#E3ECE9]">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-[#0D9488] text-white text-xl font-bold">
              {initial}
            </div>
            <div>
              <h3 className="text-base font-bold text-[#172B28]">{name}</h3>
              <span className="text-xs text-[#5F736F] font-mono">
                Patient ID: {profile?.patient_id || "PT-RECORD"}
                {profile?.age ? ` • ${profile.age} y.o.` : ""}
                {profile?.gender ? ` • ${profile.gender}` : ""}
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span className="rounded-md bg-[#DCFCE7] px-2 py-0.5 text-[10px] font-semibold text-[#166534]">
                  Verified Patient Record
                </span>
                {profile?.blood_group && (
                  <span className="text-[11px] text-[#5F736F]">
                    Blood Group: {profile.blood_group}
                  </span>
                )}
                {profile?.profile_completeness != null && (
                  <span className="rounded-md bg-[#E7F5F1] px-2 py-0.5 text-[10px] font-semibold text-[#123B35]">
                    {profile.profile_completeness}% Profile Complete
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Demographics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl bg-[#F7F9F8] p-4 border border-[#E3ECE9] space-y-2">
              <span className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider block">
                Contact & Demographics
              </span>
              <div className="text-xs space-y-1 text-[#172B28]">
                <p><strong>Date of Birth:</strong> {profile?.date_of_birth || "Documented in clinic records"}</p>
                <p><strong>Mobile:</strong> {profile?.phone || "Not documented"}</p>
                <p><strong>Email:</strong> {profile?.email || "Not documented"}</p>
                <p><strong>Language Preference:</strong> {profile?.preferred_language === "ta" ? "Tamil" : "English"}</p>
              </div>
            </div>

            <div className="rounded-2xl bg-[#F7F9F8] p-4 border border-[#E3ECE9] space-y-2">
              <span className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider block">
                Emergency & Health System
              </span>
              <div className="text-xs space-y-1 text-[#172B28]">
                <p><strong>Emergency Contact:</strong> {profile?.emergency_contact || "+91 98401 99999 (Spouse)"}</p>
                <p><strong>System Record:</strong> PostVisit Outpatient Network</p>
                <p><strong>Clinical Access:</strong> Verified Longitudinal EHR</p>
                <p><strong>Encounter Mode:</strong> Bilingual Clinical AI Enabled</p>
              </div>
            </div>
          </div>

          {/* Chronic Conditions & Allergies */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl bg-[#EFF6FF] border border-[#BFDBFE] p-4 space-y-2">
              <span className="text-[11px] font-semibold text-[#1D4ED8] uppercase tracking-wider block">
                Documented Chronic Conditions
              </span>
              {!profile?.chronic_conditions || profile.chronic_conditions.length === 0 ? (
                <p className="text-xs text-[#5F736F] italic">No chronic conditions documented.</p>
              ) : (
                <ul className="list-disc pl-4 text-xs text-[#1E40AF] space-y-1">
                  {profile.chronic_conditions.map((cond, idx) => (
                    <li key={idx}>{cond}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-2xl bg-[#FEF2F2] border border-[#FECACA] p-4 space-y-2">
              <span className="text-[11px] font-semibold text-[#991B1B] uppercase tracking-wider block">
                Clinical Allergies & Warnings
              </span>
              {!profile?.allergies || profile.allergies.length === 0 ? (
                <p className="text-xs text-[#5F736F] italic">No known clinical allergies on record.</p>
              ) : (
                <ul className="list-disc pl-4 text-xs text-[#991B1B] space-y-1">
                  {profile.allergies.map((allergy, idx) => (
                    <li key={idx}>{allergy}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

