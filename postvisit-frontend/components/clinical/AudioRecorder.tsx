"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Mic,
  Square,
  Play,
  Pause,
  Trash2,
  RefreshCw,
  Send,
  Check,
  CheckCircle2,
  AlertCircle,
  Volume2,
  X,
  Edit2,
  Sparkles,
  Upload,
} from "lucide-react";
import { formatDuration } from "@/lib/utils";
import { toast } from "sonner";
import { doctorApi } from "@/lib/api/doctor";
import { patientApi } from "@/lib/api/patient";
import { consultationsApi } from "@/lib/api/consultations";

export interface AudioRecorderProps {
  mode: "patient_question" | "doctor_note" | "consultation_encounter";
  consultationId?: string;
  patientId?: string;
  onTranscriptionSuccess?: (transcript: string) => void;
  onConsultationCreated?: (consultationId: string) => void;
  onClose?: () => void;
}

type RecordingStep =
  | "idle"
  | "recording"
  | "recorded"
  | "uploading"
  | "transcribing"
  | "complete"
  | "error";

export function AudioRecorder({
  mode,
  consultationId = "default-consultation",
  patientId,
  onTranscriptionSuccess,
  onConsultationCreated,
  onClose,
}: AudioRecorderProps) {
  const [step, setStep] = useState<RecordingStep>("idle");
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [activeInputMode, setActiveInputMode] = useState<"mic" | "upload">("mic");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [draftId, setDraftId] = useState("");
  const [isEditingTranscript, setIsEditingTranscript] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isConfirmed, setIsConfirmed] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Timer effect for recording duration (honors pause state)
  useEffect(() => {
    if (step === "recording" && !isPaused) {
      timerRef.current = setInterval(() => {
        setRecordSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [step, isPaused]);

  // Clean up object URL
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // 1. Request microphone & Start Recording
  const startRecording = async () => {
    setErrorMessage(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/ogg")
        ? "audio/ogg"
        : "";

      const options = mimeType ? { mimeType } : undefined;
      mediaRecorderRef.current = new MediaRecorder(stream, options);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const type = mimeType || "audio/webm";
        const blob = new Blob(audioChunksRef.current, { type });
        setAudioBlob(blob);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setStep("recorded");
        setIsPaused(false);
      };

      mediaRecorderRef.current.start(250);
      setStep("recording");
      setIsPaused(false);
      setRecordSeconds(0);
      setAudioBlob(null);
      setAudioUrl(null);
      setTranscript("");
      setIsConfirmed(false);
    } catch (err: any) {
      setErrorMessage(
        "Microphone permission was denied or your browser does not support audio recording."
      );
      toast.error("Microphone access denied.");
    }
  };

  // 2. Pause Recording
  const pauseRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      toast.info("Recording paused.");
    }
  };

  // 3. Resume Recording
  const resumeRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "paused") {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      toast.info("Recording resumed.");
    }
  };

  // 4. Stop Recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }
  };

  // 5. Cancel Recording
  const cancelRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }
    deleteRecording();
  };

  // 6. Delete / Reset
  const deleteRecording = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setAudioBlob(null);
    setRecordSeconds(0);
    setIsPaused(false);
    setTranscript("");
    setDraftId("");
    setErrorMessage(null);
    setIsConfirmed(false);
    setIsEditingTranscript(false);
    setStep("idle");
  };

  // 7. Handle Existing Audio File Upload Fallback
  const handleExistingAudioFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(file);
    const url = URL.createObjectURL(file);
    setAudioUrl(url);

    // Estimate duration using temporary audio element
    const tempAudio = new Audio(url);
    tempAudio.onloadedmetadata = () => {
      setRecordSeconds(Math.round(tempAudio.duration) || 0);
    };

    setStep("recorded");
    setIsPaused(false);
    setTranscript("");
    setIsConfirmed(false);
    toast.success(`Loaded "${file.name}" for clinical processing`);
  };

  // 5. Toggle Audio Playback
  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  // 6. Submit & Process Recording
  const handleProcessRecording = async () => {
    if (!audioBlob) return;
    setErrorMessage(null);
    setStep("uploading");

    try {
      if (mode === "consultation_encounter") {
        setStep("uploading");
        const ext = audioBlob.type.includes("webm") ? "webm" : audioBlob.type.includes("ogg") ? "ogg" : "wav";
        const file = new File([audioBlob], `encounter_record_${Date.now()}.${ext}`, { type: audioBlob.type });
        const res = await consultationsApi.upload(file, false);
        setStep("complete");
        toast.success(`Consultation queued for processing! ID: ${res.consultation_id.substring(0, 8)}...`);
        if (onConsultationCreated) onConsultationCreated(res.consultation_id);
      } else if (mode === "doctor_note") {
        setStep("transcribing");
        const res = await doctorApi.transcribeVoiceNote(consultationId, audioBlob);
        setTranscript(res.draft_transcript || "");
        setDraftId(res.draft_id || "");
        setStep("complete");
        toast.success("Doctor voice note transcribed. Please review before confirming.");
      } else {
        // Patient Voice Question
        setStep("transcribing");
        const res = await patientApi.transcribeVoice(audioBlob);
        setTranscript(res.transcript || "");
        setStep("complete");
        toast.success("Your voice question has been transcribed!");
      }
    } catch (err: any) {
      setStep("error");
      const safeError =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail?.message ||
        err?.message ||
        "Backend processing failed. Please check your connection and retry.";
      setErrorMessage(safeError);
      toast.error(safeError);
    }
  };

  // 7. Doctor Confirm Note
  const handleDoctorConfirmNote = async () => {
    if (!transcript.trim()) return;
    try {
      await doctorApi.confirmVoiceNote(consultationId, {
        draft_id: draftId || "voice-draft",
        final_note_text: transcript,
        category: "clinical_observation",
      });
      setIsConfirmed(true);
      toast.success("Voice note confirmed and added to official EHR!");
      if (onTranscriptionSuccess) onTranscriptionSuccess(transcript);
    } catch (err: any) {
      toast.error(err?.message || "Failed to confirm voice note in clinical record.");
    }
  };

  // 8. Patient Submit Question to AI
  const handlePatientAskAI = () => {
    if (!transcript.trim()) return;
    if (onTranscriptionSuccess) onTranscriptionSuccess(transcript);
    if (onClose) onClose();
  };

  return (
    <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[#E3ECE9]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#123B35] text-white">
            <Mic className="h-4 w-4 text-[#0D9488]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#172B28]">
              {mode === "doctor_note"
                ? "Doctor Clinical Voice Dictation"
                : mode === "patient_question"
                ? "Ask by Voice (Tamil or English)"
                : "Record Clinical Consultation Encounter"}
            </h3>
            <p className="text-[11px] text-[#5F736F]">
              {mode === "doctor_note"
                ? "Draft transcription requires clinician review before persisting to record"
                : mode === "patient_question"
                ? "Speak your question in clear Tamil or English"
                : "Captures outpatient encounter dialogue for AI transcription"}
            </p>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded-lg text-[#5F736F] hover:bg-[#F7F9F8]">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* State 1: IDLE */}
      {step === "idle" && (
        <div className="space-y-4">
          <div className="flex items-center justify-center gap-2 pb-2">
            <button
              onClick={() => setActiveInputMode("mic")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                activeInputMode === "mic"
                  ? "bg-[#0D9488] text-white shadow-2xs"
                  : "bg-[#F7F9F8] text-[#5F736F] hover:bg-[#E7F5F1]"
              }`}
            >
              <Mic className="h-3.5 w-3.5" />
              <span>Record with Microphone</span>
            </button>
            <button
              onClick={() => setActiveInputMode("upload")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                activeInputMode === "upload"
                  ? "bg-[#0D9488] text-white shadow-2xs"
                  : "bg-[#F7F9F8] text-[#5F736F] hover:bg-[#E7F5F1]"
              }`}
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Upload Existing Audio</span>
            </button>
          </div>

          {activeInputMode === "mic" ? (
            <div className="flex flex-col items-center justify-center p-8 rounded-2xl bg-[#F7F9F8] border border-dashed border-[#CBD5E1] text-center space-y-3">
              <button
                onClick={startRecording}
                className="flex h-16 w-16 items-center justify-center rounded-full bg-[#E7F5F1] text-[#0D9488] hover:bg-[#0D9488] hover:text-white transition shadow-sm group"
                aria-label="Start recording"
              >
                <Mic className="h-8 w-8 group-hover:scale-110 transition" />
              </button>
              <div>
                <span className="text-xs font-bold text-[#172B28] block">Start Audio Recording</span>
                <span className="text-[11px] text-[#5F736F]">
                  Click to grant microphone access and start speaking
                </span>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-8 rounded-2xl bg-[#F7F9F8] border border-dashed border-[#CBD5E1] text-center space-y-3">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleExistingAudioFile}
                accept=".webm,.wav,.mp3,.mp4,.m4a,.aac,.ogg,.flac"
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex h-16 w-16 items-center justify-center rounded-full bg-[#E7F5F1] text-[#0D9488] hover:bg-[#0D9488] hover:text-white transition shadow-sm group"
                aria-label="Browse audio file"
              >
                <Upload className="h-8 w-8 group-hover:scale-110 transition" />
              </button>
              <div>
                <span className="text-xs font-bold text-[#172B28] block">Choose Audio File</span>
                <span className="text-[11px] text-[#5F736F]">
                  Supports .webm, .wav, .mp3, .m4a, .aac, .ogg, .flac
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* State 2: RECORDING */}
      {step === "recording" && (
        <div className="flex flex-col items-center justify-center p-8 rounded-2xl bg-[#FEF2F2] border border-[#FECACA] text-center space-y-4">
          <div className={`flex h-16 w-16 items-center justify-center rounded-full ${
            isPaused ? "bg-amber-100 text-amber-600" : "bg-red-100 text-red-600 animate-pulse"
          }`}>
            <Mic className="h-8 w-8" />
          </div>
          <div>
            <span className={`text-xs font-bold flex items-center justify-center gap-1.5 ${
              isPaused ? "text-amber-700" : "text-red-600"
            }`}>
              <span className={`h-2 w-2 rounded-full ${isPaused ? "bg-amber-500" : "bg-red-600 animate-ping"}`} />
              {isPaused ? "Recording Paused" : "Recording Active"}
            </span>
            <span className="text-2xl font-mono font-bold text-[#172B28] block mt-1">
              {formatDuration(recordSeconds)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={cancelRecording}
              className="rounded-xl border border-[#E3ECE9] bg-white px-3 py-2 text-xs font-semibold text-[#5F736F] hover:bg-slate-50 transition"
            >
              Cancel
            </button>
            {isPaused ? (
              <button
                onClick={resumeRecording}
                className="flex items-center gap-1.5 rounded-xl border border-amber-300 bg-amber-50 px-3.5 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100 transition"
              >
                <Play className="h-3.5 w-3.5" />
                <span>Resume</span>
              </button>
            ) : (
              <button
                onClick={pauseRecording}
                className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-white px-3.5 py-2 text-xs font-semibold text-[#172B28] hover:bg-[#F7F9F8] transition"
              >
                <Pause className="h-3.5 w-3.5" />
                <span>Pause</span>
              </button>
            )}
            <button
              onClick={stopRecording}
              className="flex items-center gap-1.5 rounded-xl bg-red-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-red-700 transition"
            >
              <Square className="h-3.5 w-3.5" />
              <span>Stop Recording</span>
            </button>
          </div>
        </div>
      )}

      {/* State 3: RECORDED & READY FOR PREVIEW */}
      {step === "recorded" && audioUrl && (
        <div className="p-5 rounded-2xl bg-[#F7F9F8] border border-[#E3ECE9] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#172B28]">Recording Complete</span>
            <span className="text-xs font-mono text-[#5F736F] font-semibold">
              Duration: {formatDuration(recordSeconds)}
            </span>
          </div>

          {/* HTML5 Audio Player for preview */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-white border border-[#E3ECE9] gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={togglePlay}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-[#0D9488] text-white hover:bg-[#0F766E] transition"
                aria-label={isPlaying ? "Pause playback" : "Play playback"}
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
              </button>
              <span className="text-xs font-medium text-[#172B28]">
                {isPlaying ? "Playing preview..." : "Listen to recording"}
              </span>
            </div>

            <audio
              ref={audioRef}
              src={audioUrl}
              onEnded={() => setIsPlaying(false)}
              className="hidden"
            />
          </div>

          {/* Controls: Delete, Re-record, Process */}
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <button
                onClick={deleteRecording}
                className="flex items-center gap-1 rounded-xl border border-[#FECACA] bg-white px-3 py-1.5 text-xs font-semibold text-[#991B1B] hover:bg-[#FEF2F2] transition"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Delete</span>
              </button>
              <button
                onClick={startRecording}
                className="flex items-center gap-1 rounded-xl border border-[#E3ECE9] bg-white px-3 py-1.5 text-xs font-semibold text-[#5F736F] hover:bg-[#F7F9F8] transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Re-record</span>
              </button>
            </div>

            <button
              onClick={handleProcessRecording}
              className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#0F766E] transition"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Process Recording</span>
            </button>
          </div>
        </div>
      )}

      {/* State 4: PROCESSING / UPLOADING / TRANSCRIBING */}
      {(step === "uploading" || step === "transcribing") && (
        <div className="flex flex-col items-center justify-center p-8 rounded-2xl bg-[#E7F5F1] border border-[#CCFBF1] text-center space-y-3">
          <RefreshCw className="h-8 w-8 text-[#0D9488] animate-spin" />
          <div>
            <span className="text-xs font-bold text-[#123B35] block">
              {step === "uploading" ? "Uploading audio to backend..." : "Transcribing with medical ASR..."}
            </span>
            <span className="text-[11px] text-[#5F736F]">
              Performing audio normalization and server-side speech recognition.
            </span>
          </div>
        </div>
      )}

      {/* State 5: COMPLETE & TRANSCRIPT REVIEW */}
      {step === "complete" && transcript && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-[#16A34A]" />
              <span className="text-xs font-bold text-[#172B28]">Transcription Complete</span>
            </div>
            <button
              onClick={() => setIsEditingTranscript(!isEditingTranscript)}
              className="flex items-center gap-1 text-[11px] font-semibold text-[#0D9488] hover:underline"
            >
              <Edit2 className="h-3 w-3" />
              <span>{isEditingTranscript ? "Finish Editing" : "Edit Transcript"}</span>
            </button>
          </div>

          {isEditingTranscript ? (
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              rows={3}
              className="w-full rounded-2xl border border-[#E3ECE9] bg-[#F7F9F8] p-3 text-xs text-[#172B28] focus:border-[#0D9488] focus:bg-white focus:outline-none"
            />
          ) : (
            <div className="p-4 rounded-2xl bg-[#F7F9F8] border border-[#E3ECE9] text-xs text-[#172B28] leading-relaxed">
              "{transcript}"
            </div>
          )}

          {/* Action based on mode */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={deleteRecording}
              className="text-xs font-semibold text-[#5F736F] hover:text-[#172B28]"
            >
              Record Again
            </button>

            {mode === "doctor_note" ? (
              <button
                onClick={handleDoctorConfirmNote}
                disabled={isConfirmed}
                className={`flex items-center gap-1.5 rounded-xl px-5 py-2 text-xs font-semibold transition ${
                  isConfirmed
                    ? "bg-[#DCFCE7] text-[#166534] border border-[#BBF7D0]"
                    : "bg-[#0D9488] text-white hover:bg-[#0F766E] shadow-sm"
                }`}
              >
                <Check className="h-4 w-4" />
                <span>{isConfirmed ? "Confirmed & Saved to Record" : "Confirm Note"}</span>
              </button>
            ) : mode === "patient_question" ? (
              <button
                onClick={handlePatientAskAI}
                className="flex items-center gap-1.5 rounded-xl bg-[#0D9488] px-5 py-2 text-xs font-semibold text-white hover:bg-[#0F766E] shadow-sm transition"
              >
                <Sparkles className="h-4 w-4" />
                <span>Ask PostVisit AI</span>
              </button>
            ) : (
              <button
                onClick={() => {
                  deleteRecording();
                  if (onClose) onClose();
                }}
                className="rounded-xl bg-[#123B35] px-4 py-2 text-xs font-semibold text-white hover:bg-[#1A4D45]"
              >
                Done
              </button>
            )}
          </div>
        </div>
      )}

      {/* State 6: ERROR WITH REAL RETRY */}
      {step === "error" && (
        <div className="p-5 rounded-2xl bg-[#FEF2F2] border border-[#FECACA] space-y-3">
          <div className="flex items-start gap-2 text-xs text-[#991B1B]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold block mb-0.5">We couldn't process this recording.</strong>
              <p>{errorMessage || "Backend processing error occurred."}</p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={deleteRecording}
              className="rounded-xl border border-[#E3ECE9] bg-white px-3 py-1.5 text-xs font-semibold text-[#5F736F]"
            >
              Record Again
            </button>
            <button
              onClick={handleProcessRecording}
              className="rounded-xl bg-[#991B1B] px-4 py-1.5 text-xs font-semibold text-white hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
