"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  FileText,
  FlaskConical,
  BookOpen,
  CheckCircle2,
  Bot,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
  Mic,
} from "lucide-react";

export function DoctorSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  const navItems = [
    {
      label: "Overview",
      href: "/doctor/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "Consultations",
      href: "/doctor/consultations",
      icon: Activity,
    },
    {
      label: "Patients",
      href: "/doctor/patients",
      icon: Users,
    },
    {
      label: "Lab Reports",
      href: "/doctor/lab-reports",
      icon: FlaskConical,
    },
    {
      label: "Guidelines",
      href: "/doctor/guidelines",
      icon: BookOpen,
    },
    {
      label: "Summary Reviews",
      href: "/doctor/reviews",
      icon: CheckCircle2,
    },
  ];

  return (
    <aside
      className={`relative flex flex-col border-r border-[#E3ECE9] bg-white transition-all duration-300 ${
        collapsed ? "w-18" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-[#E3ECE9] px-4">
        <Link href="/doctor/dashboard" className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#123B35] text-white shadow-sm">
            <Activity className="h-5 w-5 text-[#0D9488]" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-sm tracking-tight text-[#123B35]">
                PostVisit<span className="text-[#0D9488]">.AI</span>
              </span>
              <span className="text-[10px] text-[#5F736F] leading-tight font-medium">
                Clinical Workspace
              </span>
            </div>
          )}
        </Link>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded-lg p-1.5 text-[#5F736F] hover:bg-[#F7F9F8] transition"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <div className={`px-3 py-1.5 text-[11px] font-semibold text-[#5F736F] uppercase tracking-wider ${collapsed ? "text-center" : ""}`}>
          {!collapsed ? "Clinical Workspace" : "•••"}
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/doctor/dashboard" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-xs font-medium transition ${
                isActive
                  ? "bg-[#E7F5F1] text-[#123B35] font-semibold"
                  : "text-[#5F736F] hover:bg-[#F7F9F8] hover:text-[#172B28]"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-[#0D9488]" : "text-[#5F736F]"}`} />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </div>

      {/* Quick Dictation / AI Helper Footer Card */}
      {!collapsed && (
        <div className="m-3 rounded-2xl bg-[#F7F9F8] p-3.5 border border-[#E3ECE9]">
          <div className="flex items-center gap-2 mb-1.5">
            <Mic className="h-4 w-4 text-[#0D9488]" />
            <span className="text-xs font-semibold text-[#172B28]">Voice Dictation</span>
          </div>
          <p className="text-[11px] text-[#5F736F] mb-2.5 leading-relaxed">
            Record notes in Tamil or English with automated clinical structuring.
          </p>
          <Link
            href="/doctor/consultations"
            className="block text-center rounded-lg bg-white px-2.5 py-1.5 text-[11px] font-semibold text-[#123B35] border border-[#E3ECE9] hover:bg-[#E7F5F1] transition shadow-xs"
          >
            Start Encounter
          </Link>
        </div>
      )}

      {/* Footer Settings */}
      <div className="border-t border-[#E3ECE9] p-3">
        <Link
          href="/doctor/dashboard"
          className="flex items-center gap-3 rounded-xl px-3 py-2 text-xs font-medium text-[#5F736F] hover:bg-[#F7F9F8] hover:text-[#172B28] transition"
        >
          <Settings className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Settings & Compliance</span>}
        </Link>
      </div>
    </aside>
  );
}
