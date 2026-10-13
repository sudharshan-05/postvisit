"use client";

import React, { useState } from "react";
import { PatientSidebar } from "@/components/layout/PatientSidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { AskAIDrawer } from "@/components/assistant/AskAIDrawer";

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const [assistantOpen, setAssistantOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#F7F9F8]">
      {/* Left Patient Navigation Sidebar */}
      <PatientSidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader
          title="Patient Health Portal"
          subtitle="Your consultation, explained clearly. Your health journey, connected."
          onOpenAssistant={() => setAssistantOpen(true)}
        />
        <main className="flex-1 p-6 overflow-y-auto">{children}</main>
      </div>

      {/* Slide-over Patient Ask AI Assistant */}
      <AskAIDrawer isOpen={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </div>
  );
}
