"use client";

import React, { useState, useEffect, useRef } from "react";
import { Play, Pause, RotateCcw, RotateCw, Volume2, VolumeX, AlertCircle } from "lucide-react";
import { formatDuration } from "@/lib/utils";

interface AudioPlayerProps {
  audioUrl?: string;
  duration?: number;
  title?: string;
  subtitle?: string;
}

export function AudioPlayer({
  audioUrl,
  duration,
  title = "Consultation Audio",
  subtitle = "Recorded clinical encounter",
}: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [realDuration, setRealDuration] = useState(duration || 0);
  const [isMuted, setIsMuted] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.muted = isMuted;
    }
  }, [isMuted]);

  if (!audioUrl) {
    return (
      <div className="rounded-2xl border border-[#E3ECE9] bg-white p-4 shadow-xs">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-xs font-semibold text-[#172B28]">{title}</h4>
            <p className="text-[11px] text-[#5F736F]">{subtitle}</p>
          </div>
          <span className="text-[11px] text-[#5F736F] italic bg-[#F7F9F8] px-2.5 py-1 rounded-md border border-[#E3ECE9]">
            Audio not available
          </span>
        </div>
      </div>
    );
  }

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false));
    }
  };

  const handleSeek = (newTime: number) => {
    if (!audioRef.current) return;
    const clamped = Math.min(Math.max(newTime, 0), realDuration);
    audioRef.current.currentTime = clamped;
    setCurrentTime(clamped);
  };

  const progressPercent = realDuration > 0 ? (currentTime / realDuration) * 100 : 0;

  return (
    <div className="rounded-2xl border border-[#E3ECE9] bg-white p-4 shadow-xs">
      <audio
        ref={audioRef}
        src={audioUrl}
        onTimeUpdate={() => {
          if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
        }}
        onLoadedMetadata={() => {
          if (audioRef.current && isFinite(audioRef.current.duration)) {
            setRealDuration(audioRef.current.duration);
          }
        }}
        onEnded={() => {
          setIsPlaying(false);
          setCurrentTime(0);
        }}
        className="hidden"
      />

      <div className="flex items-center justify-between mb-3">
        <div>
          <h4 className="text-xs font-semibold text-[#172B28]">{title}</h4>
          <p className="text-[11px] text-[#5F736F]">{subtitle}</p>
        </div>
        <div className="text-[11px] font-mono text-[#5F736F] bg-[#F7F9F8] px-2.5 py-1 rounded-md border border-[#E3ECE9]">
          {formatDuration(currentTime)} / {formatDuration(realDuration)}
        </div>
      </div>

      {/* Waveform / Scrubber Bar */}
      <div className="relative mb-3">
        <div
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const pct = clickX / rect.width;
            handleSeek(pct * realDuration);
          }}
          className="h-2 w-full rounded-full bg-[#E7F5F1] cursor-pointer overflow-hidden relative"
        >
          <div
            className="h-full bg-[#0D9488] rounded-full transition-all duration-150"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* -10s Rewind */}
          <button
            onClick={() => handleSeek(currentTime - 10)}
            className="flex h-8 w-8 items-center justify-center rounded-full text-[#5F736F] hover:bg-[#F7F9F8] hover:text-[#172B28] transition"
            title="Rewind 10 seconds"
          >
            <RotateCcw className="h-4 w-4" />
          </button>

          {/* Play/Pause Button */}
          <button
            onClick={togglePlay}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-[#0D9488] text-white shadow-sm hover:bg-[#0F766E] transition"
            aria-label={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
          </button>

          {/* +10s Forward */}
          <button
            onClick={() => handleSeek(currentTime + 10)}
            className="flex h-8 w-8 items-center justify-center rounded-full text-[#5F736F] hover:bg-[#F7F9F8] hover:text-[#172B28] transition"
            title="Forward 10 seconds"
          >
            <RotateCw className="h-4 w-4" />
          </button>
        </div>

        {/* Volume toggle */}
        <button
          onClick={() => setIsMuted(!isMuted)}
          className="rounded-full p-2 text-[#5F736F] hover:bg-[#F7F9F8] hover:text-[#172B28] transition"
          aria-label={isMuted ? "Unmute" : "Mute"}
        >
          {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

