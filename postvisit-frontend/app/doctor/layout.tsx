"use client";

import React, { useState } from "react";
import { DoctorSidebar } from "@/components/layout/DoctorSidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { AskAIDrawer } from "@/components/assistant/AskAIDrawer";

export default function DoctorLayout({ children }: { children: React.ReactNode }) {
  const [assistantOpen, setAssistantOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#F7F9F8]">
      {/* Left Navigation Sidebar */}
      <DoctorSidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader
          title="Physician Clinical Workspace"
          subtitle="Grounded AI & Diarized Multilingual Encounters"
          onOpenAssistant={() => setAssistantOpen(true)}
        />
        <main className="flex-1 p-6 overflow-y-auto">{children}</main>
      </div>

      {/* Slide-over Ask AI Assistant */}
      <AskAIDrawer isOpen={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </div>
  );
}
