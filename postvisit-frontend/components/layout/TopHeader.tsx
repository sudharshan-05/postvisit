"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import {
  Bell,
  Search,
  User,
  Shield,
  Stethoscope,
  HeartHandshake,
  LogOut,
  ChevronDown,
} from "lucide-react";

interface TopHeaderProps {
  title?: string;
  subtitle?: string;
  onOpenAssistant?: () => void;
}

export function TopHeader({ title, subtitle, onOpenAssistant }: TopHeaderProps) {
  const router = useRouter();
  const { user, role, login, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const handleRoleSwitch = (newRole: "doctor" | "patient") => {
    login(newRole);
    setDropdownOpen(false);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    if (role === "doctor") {
      router.push(`/doctor/patients?query=${encodeURIComponent(searchQuery.trim())}`);
    } else {
      router.push(`/patient/visits`);
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-[#E3ECE9] bg-white/90 px-6 backdrop-blur-md">
      {/* Page Title & Breadcrumb */}
      <div>
        {title && <h1 className="text-lg font-semibold text-[#172B28]">{title}</h1>}
        {subtitle && <p className="text-xs text-[#5F736F]">{subtitle}</p>}
      </div>

      {/* Global Search Bar */}
      <form onSubmit={handleSearch} className="hidden md:flex items-center relative w-72">
        <Search className="absolute left-3 h-4 w-4 text-[#5F736F]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={role === "doctor" ? "Search patient records, MRN..." : "Search your visits..."}
          className="w-full rounded-full border border-[#E3ECE9] bg-[#F7F9F8] py-1.5 pl-9 pr-4 text-xs text-[#172B28] placeholder-[#5F736F] focus:border-[#0D9488] focus:bg-white focus:outline-none transition"
        />
      </form>

      {/* Actions & Profile */}
      <div className="flex items-center gap-3">
        {/* Role Quick Switch (Sandbox / Dev convenience) */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 rounded-full border border-[#E3ECE9] bg-[#F7F9F8] px-3 py-1.5 text-xs font-medium text-[#172B28] hover:bg-[#E7F5F1] transition"
          >
            {role === "doctor" ? (
              <>
                <Stethoscope className="h-3.5 w-3.5 text-[#0D9488]" />
                <span>Doctor Portal</span>
              </>
            ) : (
              <>
                <HeartHandshake className="h-3.5 w-3.5 text-[#2563EB]" />
                <span>Patient Portal</span>
              </>
            )}
            <ChevronDown className="h-3 w-3 text-[#5F736F]" />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-xl border border-[#E3ECE9] bg-white p-1.5 shadow-lg z-50">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider">
                Switch Perspective
              </div>
              <button
                onClick={() => handleRoleSwitch("doctor")}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition ${
                  role === "doctor" ? "bg-[#E7F5F1] text-[#123B35]" : "text-[#172B28] hover:bg-[#F7F9F8]"
                }`}
              >
                <Stethoscope className="h-4 w-4 text-[#0D9488]" />
                Doctor Workspace
              </button>
              <button
                onClick={() => handleRoleSwitch("patient")}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition ${
                  role === "patient" ? "bg-[#E7F5F1] text-[#123B35]" : "text-[#172B28] hover:bg-[#F7F9F8]"
                }`}
              >
                <HeartHandshake className="h-4 w-4 text-[#2563EB]" />
                Patient Portal
              </button>
            </div>
          )}
        </div>

        {/* AI Copilot trigger pill */}
        {onOpenAssistant && (
          <button
            onClick={onOpenAssistant}
            className="flex items-center gap-1.5 rounded-full border border-[#0D9488] bg-[#E7F5F1] px-3 py-1.5 text-xs font-medium text-[#123B35] hover:bg-[#0D9488] hover:text-white transition shadow-sm"
          >
            <span className="h-2 w-2 rounded-full bg-[#0D9488] animate-pulse" />
            AI Copilot
          </button>
        )}

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotificationOpen(!notificationOpen)}
            aria-label="Notifications"
            className="relative rounded-full p-2 text-[#5F736F] hover:bg-[#F7F9F8] transition"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-[#0D9488]" />
          </button>

          {notificationOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-2xl border border-[#E3ECE9] bg-white p-3 shadow-xl z-50 space-y-2">
              <div className="flex items-center justify-between pb-1.5 border-b border-[#E3ECE9]">
                <span className="text-xs font-bold text-[#172B28]">Clinical Notifications</span>
                <span className="text-[10px] text-[#0D9488] font-semibold">All Read</span>
              </div>
              <p className="text-xs text-[#5F736F] py-2 text-center">
                No unread clinical alerts or critical lab notifications.
              </p>
            </div>
          )}
        </div>

        {/* Profile Avatar / User Info */}
        <div className="flex items-center gap-2 pl-2 border-l border-[#E3ECE9]">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#123B35] text-white text-xs font-semibold">
            {user?.name ? user.name.charAt(0).toUpperCase() : "U"}
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-xs font-medium text-[#172B28] truncate max-w-[130px]">
              {user?.name || (role === "doctor" ? "Dr. A. Ramanathan" : "Patient Ananya")}
            </div>
            <div className="text-[10px] text-[#5F736F] capitalize">
              {role === "doctor" ? "Attending Physician" : "Patient"}
            </div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#FEE2E2] hover:text-[#DC2626] transition ml-1"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
}

