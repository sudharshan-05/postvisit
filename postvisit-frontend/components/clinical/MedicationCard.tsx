"use client";

import React from "react";
import { Pill, CheckCircle2 } from "lucide-react";
import { MedicationItem } from "@/types";

interface MedicationCardProps {
  medications?: MedicationItem[];
  editable?: boolean;
  onSave?: (meds: MedicationItem[]) => void;
}

export function MedicationCard({
  medications = [],
}: MedicationCardProps) {
  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-5 shadow-xs">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#E3ECE9]">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#E7F5F1] text-[#0D9488]">
            <Pill className="h-4 w-4" />
          </div>
          <h3 className="text-sm font-bold text-[#172B28]">Prescribed Medications</h3>
        </div>
        <span className="text-xs text-[#5F736F] font-semibold">
          {medications.length} {medications.length === 1 ? "item" : "items"}
        </span>
      </div>

      {medications.length === 0 ? (
        <div className="p-6 text-center text-xs text-[#5F736F]">
          No prescribed medications recorded in this consultation.
        </div>
      ) : (
        <div className="space-y-3">
          {medications.map((med, index) => {
            const medName = med.name || med.medicine_name || "Medication";
            const doseStr = med.strength || med.dose || "";
            return (
              <div
                key={index}
                className="rounded-xl border border-[#F0FDF4] bg-[#F7F9F8] p-3.5 hover:border-[#CCFBF1] transition space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#172B28]">
                    {medName} {doseStr}
                  </span>
                  <span className="rounded-md bg-[#E7F5F1] px-2 py-0.5 text-[10px] font-semibold text-[#123B35]">
                    {med.route || "Oral"} • {med.frequency || "As directed"}
                  </span>
                </div>
                <p className="text-xs text-[#5F736F] leading-relaxed">
                  Timing: {med.timing || "After meals"} {med.duration ? `• Duration: ${med.duration}` : ""}
                </p>
                {med.instructions && (
                  <p className="text-[11px] text-[#0D9488] bg-white p-2 rounded-lg border border-[#E3ECE9]">
                    Instruction: {med.instructions}
                  </p>
                )}
                {med.notes && (
                  <p className="text-[11px] text-[#5F736F] italic">
                    Note: "{med.notes}"
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
