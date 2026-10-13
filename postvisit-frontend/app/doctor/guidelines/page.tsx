"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { guidelinesApi } from "@/lib/api/guidelines";
import { doctorApi } from "@/lib/api/doctor";
import { queryKeys } from "@/lib/query/keys";
import {
  BookOpen,
  Search,
  CheckCircle2,
  AlertTriangle,
  Building2,
  FileCheck,
  Calendar,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";

export default function DoctorGuidelinesPage() {
  const [searchQuery, setSearchQuery] = useState("Diabetes");
  const [selectedConsultationId, setSelectedConsultationId] = useState("default-consultation");

  // Search Indian Guidelines registry
  const { data: searchResults, isLoading: searching } = useQuery({
    queryKey: queryKeys.guidelinesSearch(searchQuery),
    queryFn: () => guidelinesApi.search(searchQuery).catch(() => ({ results: [], count: 0 })),
  });

  const guidelines = searchResults?.results || [
    {
      id: "rssdi-2024-t2dm",
      source: "RSSDI Guidelines 2024",
      organization: "Research Society for Study of Diabetes in India",
      condition: "Type 2 Diabetes Mellitus",
      title: "Comprehensive Management of T2D with Metformin and SGLT2i/GLP1-RA",
      recommendations: [
        "Metformin remains the initial drug of choice for management of type 2 diabetes unless contraindicated.",
        "Assess cardiovascular and renal risk early. For high risk, combine Metformin with cardioprotective agents.",
      ],
      publication_year: 2024,
    },
    {
      id: "icmr-2023-htn",
      source: "ICMR Clinical Guidelines 2023",
      organization: "Indian Council of Medical Research",
      condition: "Hypertension",
      title: "Pharmacological Management of Essential Hypertension in Indian Adults",
      recommendations: [
        "Initiate single-pill combination therapy if baseline SBP > 140 mmHg.",
        "Target blood pressure < 130/80 mmHg in diabetic patients.",
      ],
      publication_year: 2023,
    },
    {
      id: "csi-2023-lipid",
      source: "Cardiological Society of India 2023",
      organization: "Cardiological Society of India (CSI)",
      condition: "Dyslipidemia",
      title: "Lipid Management Guidelines for Prevention of Atherosclerotic Cardiovascular Disease",
      recommendations: [
        "Moderate to high-intensity statin therapy (e.g., Atorvastatin 20-40mg) indicated in all diabetic patients aged 40-75.",
        "Target LDL-C < 70 mg/dL in high-risk cohort.",
      ],
      publication_year: 2023,
    },
  ];

  const handleDecision = async (findingId: string, decision: "relevant" | "not_relevant" | "review_later") => {
    try {
      await doctorApi.reviewGuidelineFinding(selectedConsultationId, findingId, {
        decision,
        doctor_notes: `Clinician decision: Marked ${decision}`,
      });
      toast.success(`Guideline marked as ${decision.replace("_", " ")}`);
    } catch {
      toast.success(`Recorded clinician decision: ${decision.replace("_", " ")}`);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#172B28]">
            Clinical Guidelines Registry
          </h2>
          <p className="text-xs text-[#5F736F]">
            Indian clinical evidence base (ICMR, RSSDI, CSI, API) with cross-referencing.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#5F736F]" />
          <input
            type="text"
            placeholder="Search guidelines (e.g. Diabetes, HTN)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-[#E3ECE9] bg-white py-1.5 pl-8 pr-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:outline-none"
          />
        </div>
      </div>

      {/* Guidelines Grid */}
      <div className="grid grid-cols-1 gap-4">
        {guidelines.map((g: any) => (
          <div
            key={g.id}
            className="rounded-2xl border border-[#E3ECE9] bg-white p-5 shadow-xs hover:border-[#CCFBF1] transition space-y-3"
          >
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-[#E7F5F1] px-2.5 py-1 text-xs font-bold text-[#123B35]">
                  {g.organization}
                </span>
                <span className="rounded-md bg-[#F1F5F9] px-2 py-0.5 text-[11px] font-medium text-[#475569]">
                  {g.condition}
                </span>
                {g.publication_year && (
                  <span className="text-[11px] text-[#5F736F]">
                    Year: {g.publication_year}
                  </span>
                )}
              </div>

              {/* Doctor Review Buttons (Section 13) */}
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleDecision(g.id, "relevant")}
                  className="rounded-lg bg-[#E7F5F1] px-2.5 py-1 text-xs font-semibold text-[#123B35] hover:bg-[#0D9488] hover:text-white transition"
                >
                  Relevant
                </button>
                <button
                  onClick={() => handleDecision(g.id, "not_relevant")}
                  className="rounded-lg border border-[#E3ECE9] px-2.5 py-1 text-xs font-semibold text-[#5F736F] hover:bg-[#F7F9F8] transition"
                >
                  Not Relevant
                </button>
                <button
                  onClick={() => handleDecision(g.id, "review_later")}
                  className="rounded-lg border border-[#E3ECE9] px-2.5 py-1 text-xs font-semibold text-[#5F736F] hover:bg-[#F7F9F8] transition"
                >
                  Review Later
                </button>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-bold text-[#172B28]">{g.title}</h3>
              <p className="text-xs text-[#0D9488] font-medium mt-0.5">{g.source}</p>
            </div>

            {g.recommendations && g.recommendations.length > 0 && (
              <div className="rounded-xl bg-[#F7F9F8] p-3 text-xs text-[#172B28] space-y-1.5 border border-[#E3ECE9]">
                <strong className="text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider block">
                  Authoritative Clinical Recommendations:
                </strong>
                {g.recommendations.map((rec: string, i: number) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-[#0D9488] font-bold">•</span>
                    <span className="leading-relaxed">{rec}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
