"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import { Activity } from "lucide-react";

export default function RootPage() {
  const router = useRouter();
  const { role, isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading) {
      if (role === "patient") {
        router.replace("/patient/dashboard");
      } else {
        router.replace("/doctor/dashboard");
      }
    }
  }, [role, isLoading, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F9F8]">
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#123B35] text-white animate-pulse">
          <Activity className="h-6 w-6 text-[#0D9488]" />
        </div>
        <span className="text-xs font-semibold text-[#172B28]">
          Loading PostVisit AI Workspace...
        </span>
      </div>
    </div>
  );
}
