"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import { Activity, Stethoscope, HeartHandshake, ShieldCheck, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [role, setRole] = useState<"doctor" | "patient">("doctor");
  const [email, setEmail] = useState("dr.ramanathan@postvisit.ai");
  const [password, setPassword] = useState("••••••••");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (role === "doctor") {
        await login("doctor", undefined, "dr_ramanathan", "Dr. A. Ramanathan");
        toast.success("Welcome back, Dr. Ramanathan");
        router.push("/doctor/dashboard");
      } else {
        await login("patient", undefined, "pt_89241", "Ananya Patel");
        toast.success("Welcome back, Ananya");
        router.push("/patient/dashboard");
      }
    } catch {
      toast.error("Failed to authenticate session.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 bg-[#F7F9F8]">
      <div className="w-full max-w-md rounded-3xl border border-[#E3ECE9] bg-white p-8 shadow-sm">
        {/* Brand Banner */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#123B35] text-white shadow-sm mb-3">
            <Activity className="h-6 w-6 text-[#0D9488]" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#172B28]">
            PostVisit<span className="text-[#0D9488]">.AI</span>
          </h1>
          <p className="text-xs text-[#5F736F] mt-1">
            Clinical clarity. Better continuity of care.
          </p>
        </div>

        {/* Role Segment Tabs */}
        <div className="grid grid-cols-2 gap-1 rounded-2xl bg-[#F7F9F8] p-1.5 border border-[#E3ECE9] mb-6">
          <button
            type="button"
            onClick={() => {
              setRole("doctor");
              setEmail("dr.ramanathan@postvisit.ai");
            }}
            className={`flex items-center justify-center gap-2 rounded-xl py-2 text-xs font-semibold transition ${
              role === "doctor"
                ? "bg-white text-[#123B35] shadow-xs border border-[#E3ECE9]"
                : "text-[#5F736F] hover:text-[#172B28]"
            }`}
          >
            <Stethoscope className="h-4 w-4 text-[#0D9488]" />
            Doctor Portal
          </button>
          <button
            type="button"
            onClick={() => {
              setRole("patient");
              setEmail("ananya.patel@patient.postvisit.ai");
            }}
            className={`flex items-center justify-center gap-2 rounded-xl py-2 text-xs font-semibold transition ${
              role === "patient"
                ? "bg-white text-[#123B35] shadow-xs border border-[#E3ECE9]"
                : "text-[#5F736F] hover:text-[#172B28]"
            }`}
          >
            <HeartHandshake className="h-4 w-4 text-[#2563EB]" />
            Patient Portal
          </button>
        </div>

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-[#172B28] block mb-1">
              Registered Medical Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-xl border border-[#E3ECE9] bg-[#F7F9F8] p-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none transition"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#172B28] block mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-xl border border-[#E3ECE9] bg-[#F7F9F8] p-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none transition"
            />
          </div>

          <div className="flex items-center justify-between text-xs text-[#5F736F]">
            <label className="flex items-center gap-2">
              <input type="checkbox" defaultChecked className="rounded text-[#0D9488]" />
              <span>Remember secure session</span>
            </label>
            <a href="#" className="hover:text-[#0D9488]">Forgot password?</a>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="flex items-center justify-center gap-2 w-full rounded-xl bg-[#123B35] py-3 text-xs font-semibold text-white shadow-sm hover:bg-[#1A4D45] transition disabled:opacity-50"
          >
            <span>{isLoading ? "Signing in..." : `Sign in to ${role === "doctor" ? "Doctor Workspace" : "Patient Portal"}`}</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        {/* Sandbox Badge */}
        <div className="mt-6 flex items-center justify-center gap-1.5 text-[11px] text-[#5F736F] border-t border-[#E3ECE9] pt-4">
          <ShieldCheck className="h-4 w-4 text-[#16A34A]" />
          <span>Connected to Verified Sandbox Backend (Stage 1–5B)</span>
        </div>
      </div>
    </div>
  );
}
