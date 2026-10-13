"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Calendar,
  Activity,
  FlaskConical,
  MessageSquare,
  User,
  Heart,
  ChevronLeft,
  ChevronRight,
  PhoneCall,
} from "lucide-react";

export function PatientSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  const navItems = [
    {
      label: "Dashboard",
      href: "/patient/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "My Visits",
      href: "/patient/visits",
      icon: Calendar,
    },
    {
      label: "Lab Reports",
      href: "/patient/reports",
      icon: FlaskConical,
    },
    {
      label: "AI Health Assistant",
      href: "/patient/assistant",
      icon: MessageSquare,
    },
    {
      label: "Profile",
      href: "/patient/profile",
      icon: User,
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
        <Link href="/patient/dashboard" className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#0D9488] text-white shadow-sm">
            <Heart className="h-5 w-5 text-white" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-sm tracking-tight text-[#172B28]">
                PostVisit<span className="text-[#0D9488]"> Patient</span>
              </span>
              <span className="text-[10px] text-[#5F736F] leading-tight font-medium">
                Your Health Journey
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
          {!collapsed ? "Health Care" : "•••"}
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/patient/dashboard" && pathname?.startsWith(item.href));
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

      {/* Clinic Contact Card (Image 2 style) */}
      {!collapsed && (
        <div className="m-3 rounded-2xl bg-gradient-to-br from-[#E7F5F1] to-[#F0FDF4] p-3.5 border border-[#CCFBF1]">
          <div className="flex items-center gap-2 mb-1.5">
            <PhoneCall className="h-4 w-4 text-[#0D9488]" />
            <span className="text-xs font-semibold text-[#123B35]">Clinic Support</span>
          </div>
          <p className="text-[11px] text-[#5F736F] mb-2 leading-relaxed">
            Need emergency assistance or follow-up clarification?
          </p>
          <div className="rounded-lg bg-white px-2.5 py-1.5 text-[11px] font-semibold text-[#123B35] border border-[#E3ECE9] text-center">
            Helpline: 1800-419-CARE
          </div>
        </div>
      )}
    </aside>
  );
}
