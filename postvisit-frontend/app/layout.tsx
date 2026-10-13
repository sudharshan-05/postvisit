import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/lib/query/provider";
import { AuthProvider } from "@/lib/auth/context";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "PostVisit AI — Clinical Clarity. Better Continuity of Care.",
  description:
    "Multilingual clinical consultation and patient-care platform. Your consultation, explained clearly. Your health journey, connected.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-[#F7F9F8] text-[#172B28] min-h-screen">
        <QueryProvider>
          <AuthProvider>
            {children}
            <Toaster position="top-right" richColors />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
