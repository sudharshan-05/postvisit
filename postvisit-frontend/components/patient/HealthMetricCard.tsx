"use client";

import React from "react";
import { Scale, ArrowUpDown, User, Heart, Activity } from "lucide-react";

interface HealthMetricGridProps {
  weight?: number | string;
  height?: number | string;
  age?: number | string;
  pulse?: number | string;
  bloodPressure?: string;
}

export function HealthMetricGrid({
  weight = "72 kg",
  height = "181 cm",
  age = "28 y.o.",
  pulse = "96 BPM",
  bloodPressure = "120/80",
}: HealthMetricGridProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {/* 1. Weight - Vibrant Blue Card (Image 2 style) */}
      <div className="rounded-3xl bg-[#2563EB] p-5 text-white shadow-sm flex items-center justify-between transition hover:shadow-md">
        <div>
          <span className="text-xs font-medium text-blue-100 block mb-1">Weight</span>
          <span className="text-2xl font-bold tracking-tight">{weight}</span>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/20 backdrop-blur-xs">
          <Scale className="h-6 w-6 text-white" />
        </div>
      </div>

      {/* 2. Height - Crisp White Card */}
      <div className="rounded-3xl bg-white border border-[#E3ECE9] p-5 text-[#172B28] shadow-xs flex items-center justify-between transition hover:shadow-sm">
        <div>
          <span className="text-xs font-medium text-[#5F736F] block mb-1">Height</span>
          <span className="text-2xl font-bold tracking-tight text-[#172B28]">{height}</span>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#EFF6FF] text-[#2563EB]">
          <ArrowUpDown className="h-6 w-6" />
        </div>
      </div>

      {/* 3. Age - Soft Green Card */}
      <div className="rounded-3xl bg-[#ECFDF5] border border-[#D1FAE5] p-5 text-[#065F46] shadow-xs flex items-center justify-between transition hover:shadow-sm">
        <div>
          <span className="text-xs font-medium text-[#047857] block mb-1">Age</span>
          <span className="text-2xl font-bold tracking-tight text-[#065F46]">{age}</span>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#D1FAE5] text-[#059669]">
          <User className="h-6 w-6" />
        </div>
      </div>

      {/* 4. Pulse / BP - Soft Blue Card */}
      <div className="rounded-3xl bg-[#F0F9FF] border border-[#E0F2FE] p-5 text-[#075985] shadow-xs flex items-center justify-between transition hover:shadow-sm">
        <div>
          <span className="text-xs font-medium text-[#0284C7] block mb-1">Pulse / BP</span>
          <span className="text-2xl font-bold tracking-tight text-[#0C4A6E]">{pulse}</span>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#E0F2FE] text-[#0284C7]">
          <Heart className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}
