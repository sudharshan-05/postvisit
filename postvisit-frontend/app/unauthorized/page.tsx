"use client";

import Link from "next/link";
import { ShieldAlert, ArrowLeft } from "lucide-react";

export default function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 bg-[#F7F9F8]">
      <div className="w-full max-w-md rounded-3xl border border-[#E3ECE9] bg-white p-8 text-center shadow-xs">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-100 text-red-600 mx-auto mb-4">
          <ShieldAlert className="h-7 w-7" />
        </div>
        <h2 className="text-lg font-bold text-[#172B28] mb-1">
          Access Restricted (403)
        </h2>
        <p className="text-xs text-[#5F736F] leading-relaxed mb-6">
          You do not have the required clinical authorization or role permissions to view this resource. Patient data isolation is cryptographically enforced.
        </p>
        <Link
          href="/login"
          className="inline-flex items-center gap-2 rounded-xl bg-[#123B35] px-5 py-2.5 text-xs font-semibold text-white hover:bg-[#1A4D45] transition"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Return to Sign In</span>
        </Link>
      </div>
    </div>
  );
}
