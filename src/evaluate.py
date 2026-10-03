"""
PostVisit AI - ASR Evaluation & Medical Accuracy Checker
Calculates Word Error Rate (WER) and verifies clinical entities.
"""

import re
import sys
from typing import Dict, List, Tuple, Any

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Computes Word Error Rate (WER) using Levenshtein distance on words.
    """
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1].lower() == hyp_words[j - 1].lower():
                d[i][j] = d[i - 1][j - 1]
            else:
                substitution = d[i - 1][j - 1] + 1
                insertion = d[i][j - 1] + 1
                deletion = d[i - 1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)

    return round(d[len(ref_words)][len(hyp_words)] / len(ref_words), 4)


# Critical medical tokens and patterns that must never be corrupted
MEDICAL_KEYWORDS = [
    "metformin", "amlodipine", "paracetamol", "atorvastatin",
    "thyroxine", "insulin", "antibiotics", "mg", "milligram",
    "mcg", "ml", "mmhg", "hba1c", "bp", "ecg", "sugar",
    "check-up", "follow-up", "sos", "500", "650", "5", "10", "50"
]


def extract_medical_entities(text: str) -> List[str]:
    """
    Extracts alphanumeric medical keywords, dosages, and test names from text.
    """
    found = []
    # Alphanumeric words (English medical terms and numbers)
    ascii_words = re.findall(r"[A-Za-z0-9\-]+", text.lower())
    for word in ascii_words:
        if word in MEDICAL_KEYWORDS or any(char.isdigit() for char in word):
            found.append(word)
    return found


def evaluate_medical_accuracy(
    expected_text: str,
    actual_text: str,
    key_entities_hint: str = ""
) -> Dict[str, Any]:
    """
    Evaluates both linguistic accuracy (WER) and clinical integrity.
    Returns PASS or MEDICAL ENTITY ERROR.
    """
    wer = calculate_wer(expected_text, actual_text)

    # Extract critical entities from expected text
    expected_entities = extract_medical_entities(expected_text)

    # If hints exist, also include them
    if key_entities_hint:
        for part in key_entities_hint.split(","):
            if ":" in part:
                val = part.split(":", 1)[1].strip()
                for w in extract_medical_entities(val):
                    if w not in expected_entities:
                        expected_entities.append(w)

    actual_lower = actual_text.lower()
    missing_entities = []

    for entity in expected_entities:
        if entity not in actual_lower:
            missing_entities.append(entity)

    if missing_entities:
        status = "MEDICAL ENTITY ERROR"
        reason = f"Missing or corrupted critical entities: {', '.join(missing_entities)}"
    elif wer > 0.35:
        status = "REVIEW_REQUIRED"
        reason = f"High transcription error rate (WER: {wer * 100:.1f}%)"
    else:
        status = "PASS"
        reason = "All critical medical entities preserved"

    return {
        "expected": expected_text,
        "actual": actual_text,
        "wer": wer,
        "status": status,
        "missing_entities": missing_entities,
        "reason": reason
    }
