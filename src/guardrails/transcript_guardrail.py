"""
PostVisit AI - Transcript Guardrail
Validates transcribed consultation output before passing to clinical LLM agents.
Ensures non-empty speech, valid speaker turns, and positive chronological timestamps.
Safely routes defective transcripts to 'NEEDS_REVIEW'.
"""

import re
from typing import List, Dict, Any, Optional
from src.guardrails.base import GuardrailResult

MIN_WORDS_COUNT = 2


class TranscriptGuardrail:
    """
    Validates ASR output and speaker turn segments.
    """

    def __init__(self, min_words: int = MIN_WORDS_COUNT):
        self.min_words = min_words

    def validate(
        self,
        transcript_text: str,
        speaker_turns: Optional[List[Dict[str, Any]]] = None
    ) -> GuardrailResult:
        """
        Validates the transcript text and speaker turns.
        """
        clean_text = (transcript_text or "").strip()

        # 1. Non-empty check
        if not clean_text:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="TRANSCRIPT_EMPTY",
                message="ASR produced an empty transcript. Speech content could not be detected."
            )

        # 2. Reasonable speech content
        words = clean_text.split()
        if len(words) < self.min_words:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="TRANSCRIPT_TOO_SHORT",
                message=f"Transcript contains fewer than {self.min_words} words.",
                details={"word_count": len(words), "text": clean_text}
            )

        # 3. Speaker segment validity check
        if speaker_turns:
            invalid_segments = []
            for i, turn in enumerate(speaker_turns):
                start = float(turn.get("start", turn.get("start_sec", 0.0)))
                end = float(turn.get("end", turn.get("end_sec", 0.0)))
                if start < 0 or end < start:
                    invalid_segments.append({"index": i, "start": start, "end": end})

            if invalid_segments:
                return GuardrailResult(
                    passed=False,
                    action="NEEDS_REVIEW",
                    error_code="INVALID_SPEAKER_TIMESTAMPS",
                    message="Speaker segments contain invalid or non-chronological timestamps.",
                    details={"invalid_segments": invalid_segments}
                )

        return GuardrailResult(
            passed=True,
            action="CONTINUE",
            message="Transcript guardrail passed.",
            details={"word_count": len(words), "character_count": len(clean_text)}
        )
