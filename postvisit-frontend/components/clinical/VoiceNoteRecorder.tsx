"use client";

import React from "react";
import { useAuth } from "@/lib/auth/context";
import { AudioRecorder } from "@/components/clinical/AudioRecorder";

interface VoiceNoteRecorderProps {
  consultationId?: string;
  onConfirmed?: (transcript: string) => void;
}

export function VoiceNoteRecorder({
  consultationId = "default-consultation",
  onConfirmed,
}: VoiceNoteRecorderProps) {
  const { role } = useAuth();

  return (
    <AudioRecorder
      mode={role === "doctor" ? "doctor_note" : "patient_question"}
      consultationId={consultationId}
      onTranscriptionSuccess={onConfirmed}
    />
  );
}

