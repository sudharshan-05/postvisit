"use client";

import React, { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { HealthTrendPoint } from "@/types";

interface HealthTrendsChartProps {
  data?: HealthTrendPoint[];
}

export function HealthTrendsChart({ data = [] }: HealthTrendsChartProps) {
  const [activeTab, setActiveTab] = useState<"appointments" | "weight" | "bp">("bp");
  const [timeRange, setTimeRange] = useState("This year");

  if (!data || data.length === 0) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-8 text-center shadow-xs">
        <h3 className="text-sm font-bold text-[#172B28] mb-1">Health Trends & Vitals</h3>
        <p className="text-xs text-[#5F736F]">
          No longitudinal vitals recorded yet. Trend charts will populate automatically as consultations and vital measurements are documented.
        </p>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    name: d.date,
    systolic: d.systolic_bp || 120,
    diastolic: d.diastolic_bp || 80,
    weight: d.weight_kg || 70,
    glucose: d.fasting_glucose || 100,
    appointments: 1,
    prevAppointments: 1,
  }));


  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-6 shadow-xs">
      {/* Chart Top Controls (Image 2 style) */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-6">
            <button
              onClick={() => setActiveTab("bp")}
              className={`text-sm font-semibold transition pb-1 border-b-2 ${
                activeTab === "bp"
                  ? "border-[#0D9488] text-[#123B35]"
                  : "border-transparent text-[#5F736F] hover:text-[#172B28]"
              }`}
            >
              Blood Pressure
            </button>
            <button
              onClick={() => setActiveTab("weight")}
              className={`text-sm font-semibold transition pb-1 border-b-2 ${
                activeTab === "weight"
                  ? "border-[#2563EB] text-[#1D4ED8]"
                  : "border-transparent text-[#5F736F] hover:text-[#172B28]"
              }`}
            >
              Weight (kg)
            </button>
            <button
              onClick={() => setActiveTab("appointments")}
              className={`text-sm font-semibold transition pb-1 border-b-2 ${
                activeTab === "appointments"
                  ? "border-[#0D9488] text-[#123B35]"
                  : "border-transparent text-[#5F736F] hover:text-[#172B28]"
              }`}
            >
              Consultations
            </button>
          </div>
          <p className="text-xs text-[#5F736F] mt-1.5">
            {activeTab === "bp"
              ? "Target: < 130/80 mmHg (AHA & Indian Hypertension Guidelines)"
              : activeTab === "weight"
              ? "Longitudinal weight tracking (Baseline: 74 kg)"
              : "63 clinical encounters this year"}
          </p>
        </div>

        {/* Legend & Filter */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-[#5F736F]">
            <span className="h-2 w-2 rounded-full bg-[#0D9488]" />
            <span>Current year</span>
          </div>
          <div className="flex items-center gap-1.5 text-[#5F736F]">
            <span className="h-2 w-2 rounded-full bg-[#93C5FD]" />
            <span>Previous year</span>
          </div>
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="rounded-lg border border-[#E3ECE9] bg-[#F7F9F8] px-2.5 py-1 text-xs text-[#172B28] focus:outline-none"
          >
            <option>This year</option>
            <option>Last 6 months</option>
            <option>Last 30 days</option>
          </select>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="tealGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0D9488" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#0D9488" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="blueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#2563EB" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#5F736F" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#5F736F" }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#FFFFFF",
                borderRadius: "12px",
                border: "1px solid #E3ECE9",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                fontSize: "12px",
              }}
            />
            {activeTab === "bp" && (
              <>
                <Area
                  type="monotone"
                  dataKey="systolic"
                  name="Systolic BP (mmHg)"
                  stroke="#0D9488"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#tealGradient)"
                />
                <Area
                  type="monotone"
                  dataKey="diastolic"
                  name="Diastolic BP (mmHg)"
                  stroke="#93C5FD"
                  strokeWidth={2}
                  fillOpacity={0.5}
                  fill="url(#blueGradient)"
                />
              </>
            )}
            {activeTab === "weight" && (
              <Area
                type="monotone"
                dataKey="weight"
                name="Weight (kg)"
                stroke="#2563EB"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#blueGradient)"
              />
            )}
            {activeTab === "appointments" && (
              <Area
                type="monotone"
                dataKey="appointments"
                name="Visits"
                stroke="#0D9488"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#tealGradient)"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
