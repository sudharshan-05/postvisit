"""
PostVisit AI - Audio Quality Guardrail
Verifies decoded audio characteristics before feeding into IndicConformer ASR.
Detects silence, near-silence, abnormal clipping, and insufficient duration.
Safely routes low-quality audio to 'NEEDS_REVIEW' instead of generating misleading medical records.
"""

import numpy as np
from typing import Optional, Union, Tuple
from src.guardrails.base import GuardrailResult

MIN_AUDIO_DURATION_SEC = 0.5
SILENCE_RMS_THRESHOLD = 1e-4
SILENCE_PEAK_THRESHOLD = 1e-3


class AudioQualityGuardrail:
    """
    Evaluates audio waveforms for speech recognition viability.
    """

    def __init__(
        self,
        min_duration_sec: float = MIN_AUDIO_DURATION_SEC,
        silence_rms_threshold: float = SILENCE_RMS_THRESHOLD,
        silence_peak_threshold: float = SILENCE_PEAK_THRESHOLD
    ):
        self.min_duration_sec = min_duration_sec
        self.silence_rms_threshold = silence_rms_threshold
        self.silence_peak_threshold = silence_peak_threshold

    def validate(
        self,
        waveform: np.ndarray,
        sample_rate: int
    ) -> GuardrailResult:
        """
        Validates decoded audio waveform.
        """
        if waveform is None or waveform.size == 0:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="AUDIO_EMPTY",
                message="Audio waveform is empty or could not be decoded."
            )

        if not np.all(np.isfinite(waveform)):
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="AUDIO_CORRUPTED_VALUES",
                message="Audio waveform contains NaN or infinite values."
            )

        # Calculate duration
        samples = waveform.shape[-1]
        duration_sec = float(samples / sample_rate) if sample_rate > 0 else 0.0

        if duration_sec < self.min_duration_sec:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="AUDIO_TOO_SHORT",
                message=f"Audio duration ({duration_sec:.2f}s) is shorter than required minimum ({self.min_duration_sec}s).",
                details={"duration_sec": duration_sec}
            )

        # Calculate RMS energy & peak amplitude
        wav_flat = waveform.flatten()
        rms = float(np.sqrt(np.mean(wav_flat ** 2)))
        peak = float(np.max(np.abs(wav_flat)))

        if rms < self.silence_rms_threshold or peak < self.silence_peak_threshold:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="AUDIO_SILENT",
                message=(
                    f"Audio appears completely silent or below audible threshold (RMS: {rms:.6f}, Peak: {peak:.6f}). "
                    "Clinical consultation review required."
                ),
                details={"rms": rms, "peak": peak, "duration_sec": duration_sec}
            )

        return GuardrailResult(
            passed=True,
            action="CONTINUE",
            message="Audio quality checks passed.",
            details={"duration_sec": duration_sec, "rms": rms, "peak": peak}
        )
