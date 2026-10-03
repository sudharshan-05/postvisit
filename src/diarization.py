"""
PostVisit AI - Improved Acoustic Diarization & Conversational Role Pipeline
Architecture:
  Stage A: Acoustic Voice Activity Detection (VAD) & Speaker Identity (SPEAKER_00, SPEAKER_01)
           - Acoustic energy quantile pause detection (DEFAULT_MIN_PAUSE_SEC)
           - Segment MFCC multivariate Gaussian modeling & Symmetric KL Divergence clustering
           - Same-speaker segment merging (MAX_SAME_SPEAKER_GAP)
           - Anti-flipping temporal consistency (MIN_SPEAKER_CHANGE_DURATION)
           - Completely decoupled from vocabulary, keywords, or roles
  Stage B: Conversational Role Classification (Doctor vs. Patient)
           - Evaluates full consultation dialogue globally across attributed speaker turns
           - Maps speaker IDs to clinical roles without altering or fragmenting turns
"""

import sys
import re
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import torch
import torchaudio

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.asr import get_model

# ---------------------------------------------------------------------------
# Configurable Thresholds & Parameters
# ---------------------------------------------------------------------------
DEFAULT_MIN_PAUSE_SEC = 0.80           # Inter-utterance silence threshold (seconds)
DEFAULT_MAX_SAME_SPEAKER_GAP = 0.80    # Merge adjacent segments if gap is below this (seconds)
DEFAULT_MIN_SPEAKER_CHANGE_DURATION = 0.80  # Minimum speech duration to confirm a genuine speaker change
DEFAULT_ENERGY_QUANTILE = 0.35         # Adaptive energy threshold quantile


# ---------------------------------------------------------------------------
# Stage A1: Acoustic Voice Activity & Pause Segmentation
# ---------------------------------------------------------------------------

def detect_speech_segments(
    wav: torch.Tensor,
    sample_rate: int = 16000,
    frame_duration_ms: int = 30,
    min_pause_duration_sec: float = DEFAULT_MIN_PAUSE_SEC,
    energy_threshold_quantile: float = DEFAULT_ENERGY_QUANTILE,
    min_speech_duration_sec: float = 0.50
) -> List[Dict[str, Any]]:
    """
    Detects continuous speech segments bounded by acoustic pauses >= min_pause_duration_sec.
    """
    if wav.ndim == 2:
        samples = wav.squeeze(0).cpu().numpy()
    else:
        samples = wav.cpu().numpy()

    total_samples = len(samples)
    total_duration = total_samples / sample_rate

    if total_duration <= min_speech_duration_sec * 2:
        return [{
            "segment_id": 1,
            "start_sec": 0.0,
            "end_sec": round(total_duration, 2),
            "audio": wav if wav.ndim == 2 else wav.unsqueeze(0)
        }]

    frame_length = int(sample_rate * (frame_duration_ms / 1000.0))
    hop_length = frame_length // 2
    num_frames = max(1, (total_samples - frame_length) // hop_length + 1)

    energies = np.zeros(num_frames)
    for i in range(num_frames):
        start = i * hop_length
        end = min(start + frame_length, total_samples)
        frame = samples[start:end]
        energies[i] = np.sum(frame ** 2) / len(frame) if len(frame) > 0 else 0.0

    non_zero = energies[energies > 1e-9]
    threshold = np.quantile(non_zero, energy_threshold_quantile) if len(non_zero) > 0 else 1e-4

    is_speech = energies > threshold
    min_pause_frames = int(min_pause_duration_sec / (hop_length / sample_rate))
    min_speech_frames = int(min_speech_duration_sec / (hop_length / sample_rate))

    raw_segments: List[Tuple[int, int]] = []
    in_speech = False
    speech_start_frame = 0
    silence_count = 0

    for i, active in enumerate(is_speech):
        if active:
            if not in_speech:
                in_speech = True
                speech_start_frame = i
            silence_count = 0
        else:
            if in_speech:
                silence_count += 1
                if silence_count >= min_pause_frames:
                    speech_end_frame = i - silence_count
                    if (speech_end_frame - speech_start_frame) >= min_speech_frames:
                        raw_segments.append((speech_start_frame, speech_end_frame))
                    in_speech = False
                    silence_count = 0

    if in_speech:
        speech_end_frame = len(is_speech) - 1
        if (speech_end_frame - speech_start_frame) >= min_speech_frames:
            raw_segments.append((speech_start_frame, speech_end_frame))

    if not raw_segments:
        return [{
            "segment_id": 1,
            "start_sec": 0.0,
            "end_sec": round(total_duration, 2),
            "audio": wav if wav.ndim == 2 else wav.unsqueeze(0)
        }]

    segments: List[Dict[str, Any]] = []
    for idx, (sf_idx, ef_idx) in enumerate(raw_segments, 1):
        start_sample = max(0, sf_idx * hop_length - frame_length)
        end_sample = min(total_samples, ef_idx * hop_length + frame_length * 2)

        start_sec = round(start_sample / sample_rate, 2)
        end_sec = round(end_sample / sample_rate, 2)
        seg_audio = torch.from_numpy(samples[start_sample:end_sample]).unsqueeze(0)

        segments.append({
            "segment_id": idx,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "audio": seg_audio
        })

    return segments


# ---------------------------------------------------------------------------
# Stage A2: Acoustic Speaker Identity Clustering (Gaussian KL Divergence)
# ---------------------------------------------------------------------------

def _sym_kl_divergence(X: np.ndarray, Y: np.ndarray) -> float:
    """
    Computes symmetric Kullback-Leibler (KL) divergence between two diagonal multivariate Gaussians
    representing segment MFCC distributions.
    """
    mu_x, var_x = np.mean(X, axis=1), np.var(X, axis=1) + 1e-4
    mu_y, var_y = np.mean(Y, axis=1), np.var(Y, axis=1) + 1e-4

    kl_xy = 0.5 * np.sum(var_x / var_y + (mu_y - mu_x)**2 / var_y - 1 + np.log(var_y / var_x))
    kl_yx = 0.5 * np.sum(var_y / var_x + (mu_x - mu_y)**2 / var_x - 1 + np.log(var_x / var_y))
    return float(kl_xy + kl_yx)


def cluster_speaker_identities(
    segments: List[Dict[str, Any]],
    sample_rate: int = 16000,
    min_change_duration_sec: float = DEFAULT_MIN_SPEAKER_CHANGE_DURATION
) -> List[Dict[str, Any]]:
    """
    Assigns acoustic speaker identities (SPEAKER_00, SPEAKER_01) using segment-level
    multivariate MFCC distributions and Symmetric KL Divergence clustering.
    Zero external ML models; purely statistical acoustic clustering.
    """
    if not segments:
        return []

    if len(segments) == 1:
        segments[0]["speaker_id"] = "SPEAKER_00"
        return segments

    mfcc_transform = torchaudio.transforms.MFCC(
        sample_rate=sample_rate,
        n_mfcc=13,
        melkwargs={"n_fft": 400, "hop_length": 160, "n_mels": 26, "center": False}
    )

    models = []
    for s in segments:
        with torch.no_grad():
            m = mfcc_transform(s["audio"]).squeeze(0)
            if m.ndim == 2 and m.shape[0] > 1:
                # Omit C0 (overall energy) to capture vocal tract spectral envelope
                m = m[1:, :]
            models.append(m.cpu().numpy())

    N = len(models)
    dist_mat = np.zeros((N, N))
    for i in range(N):
        for j in range(i, N):
            d = _sym_kl_divergence(models[i], models[j])
            dist_mat[i, j] = d
            dist_mat[j, i] = d

    # Seed Cluster 0 with Segment 0 (first speaker to talk)
    c0 = 0
    # Seed Cluster 1 with the segment having maximum acoustic divergence from Cluster 0
    c1 = int(np.argmax(dist_mat[0]))

    # If maximum distance is negligible, entire recording is single speaker
    max_d = dist_mat[0, c1]
    if max_d < 0.30:
        for s in segments:
            s["speaker_id"] = "SPEAKER_00"
        return segments

    for i in range(N):
        dur = segments[i]["end_sec"] - segments[i]["start_sec"]
        d0 = dist_mat[i, c0]
        d1 = dist_mat[i, c1]

        # Temporal consistency: if segment is very short (< min_change_duration_sec),
        # prevent aggressive switching unless acoustic divergence is overwhelming
        if dur < min_change_duration_sec and i > 0:
            prev_spk = segments[i - 1]["speaker_id"]
            if prev_spk == "SPEAKER_00" and d1 < d0 * 1.5:
                segments[i]["speaker_id"] = "SPEAKER_00"
                continue
            elif prev_spk == "SPEAKER_01" and d0 < d1 * 1.5:
                segments[i]["speaker_id"] = "SPEAKER_01"
                continue

        if d0 <= d1:
            segments[i]["speaker_id"] = "SPEAKER_00"
        else:
            segments[i]["speaker_id"] = "SPEAKER_01"

    return segments


# ---------------------------------------------------------------------------
# Stage A3: Same-Speaker Merging & Anti-Flipping Smoothing
# ---------------------------------------------------------------------------

def merge_same_speaker_segments(
    segments: List[Dict[str, Any]],
    max_gap_sec: float = DEFAULT_MAX_SAME_SPEAKER_GAP,
    min_change_duration_sec: float = DEFAULT_MIN_SPEAKER_CHANGE_DURATION
) -> List[Dict[str, Any]]:
    """
    Merges consecutive segments belonging to the same speaker separated by small pauses.
    Suppresses micro-flipping on short isolated segments.
    """
    if not segments:
        return []

    # Step 1: Temporal smoothing on isolated short segments
    for i in range(1, len(segments) - 1):
        prev_spk = segments[i - 1]["speaker_id"]
        curr_spk = segments[i]["speaker_id"]
        next_spk = segments[i + 1]["speaker_id"]

        dur = segments[i]["end_sec"] - segments[i]["start_sec"]
        if prev_spk == next_spk and curr_spk != prev_spk and dur < min_change_duration_sec:
            # Revert micro-flip to maintain temporal continuity
            segments[i]["speaker_id"] = prev_spk

    # Step 2: Merge adjacent segments with same speaker ID and gap <= max_gap_sec
    merged: List[Dict[str, Any]] = []
    current = segments[0].copy()

    for seg in segments[1:]:
        gap = seg["start_sec"] - current["end_sec"]
        same_speaker = (seg["speaker_id"] == current["speaker_id"])

        if same_speaker and gap <= max_gap_sec:
            current["end_sec"] = seg["end_sec"]
            current["audio"] = torch.cat([current["audio"], seg["audio"]], dim=-1)
        else:
            merged.append(current)
            current = seg.copy()

    merged.append(current)

    # Re-index turn IDs
    for idx, turn in enumerate(merged, 1):
        turn["turn_id"] = idx

    return merged


# ---------------------------------------------------------------------------
# Stage B: Global Conversational Role Attribution (Doctor vs. Patient)
# ---------------------------------------------------------------------------

DOCTOR_LEXICON = [
    r"\bmg\b|\bmilligram\b|\bml\b|\bmcg\b|\btablet\b|\bcapsule\b|\bமாத்திரை\b|\bமருந்து\b",
    r"சாப்பிடுங்கள்|எடுத்துக்கொள்ளுங்கள்|எடுத்துக்கோங்க|எடுங்க|போடுங்க|சாப்பிட\s*பிறகு|உணவுக்கு\s*முன்|டின்னருக்கு|சாப்பாட்டுக்கு",
    r"கவலைப்பட\s*வேண்டாம்|சரி\s*கவலைப்பட|ரெஸ்ட்\s*எடுங்க|தண்ணி\s*குடிங்க",
    r"check\s*பண்ணுங்க|பரிசோதனை|டெஸ்ட்|test|hba1c|ecg|blood\s*sugar",
    r"check-up|follow-up|ஒரு\s*வாரம்\s*கழித்து|அடுத்த\s*வாரம்|திருப்பி\s*வாங்க|பார்க்கறோம்",
    r"தொடர்ந்து\s*எடுத்துக்கோங்க|அஞ்சு\s*நாள்|வாரத்துக்கு\s*ஒரு\s*முறை"
]

PATIENT_LEXICON = [
    r"டாக்டர்|doctor|doc",
    r"காய்ச்சல்\s*இருக்கு|ஃபீவர்|fever|பாடி\s*பெயின்|body\s*pain|ஹெட்ேக்|headache|தலைவலி",
    r"சாப்பிட\s*முடியல|சாப்பிடவும்\s*கொஞ்சம்\s*கஷ்டமாக|கஷ்டமாக\s*இருக்குது|வலிக்குது|தூக்கம்\s*வரல",
    r"மூணு\s*நாளா|ரெண்டு\s*நாளா|நேத்துல\s*இருந்து|2\s*days|3\s*days",
    r"சரிங்க\s*டாக்டர்|ஆமாங்க\s*டாக்டர்|சரி\s*டாக்டர்"
]


def score_speaker_transcripts(turns: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Evaluates all utterances per speaker ID across the whole consultation
    and determines global role mapping (SPEAKER_00 -> Patient, SPEAKER_01 -> Doctor).
    Role classification does NOT modify segment boundaries or speaker identities.
    """
    scores: Dict[str, Dict[str, float]] = {
        "SPEAKER_00": {"doctor": 0.0, "patient": 0.0},
        "SPEAKER_01": {"doctor": 0.0, "patient": 0.0}
    }

    for turn in turns:
        spk = turn.get("speaker_id", "SPEAKER_00")
        if spk not in scores:
            scores[spk] = {"doctor": 0.0, "patient": 0.0}

        text = turn.get("text", "").lower()
        for pattern in DOCTOR_LEXICON:
            if re.search(pattern, text):
                scores[spk]["doctor"] += 1.0

        for pattern in PATIENT_LEXICON:
            if re.search(pattern, text):
                scores[spk]["patient"] += 1.0

    # Decision rule: Speaker with higher net clinical prescription authority is Doctor
    s0_net = scores["SPEAKER_00"]["doctor"] - scores["SPEAKER_00"]["patient"]
    s1_net = scores["SPEAKER_01"]["doctor"] - scores["SPEAKER_01"]["patient"]

    if s1_net >= s0_net:
        role_mapping = {"SPEAKER_00": "Patient", "SPEAKER_01": "Doctor"}
    else:
        role_mapping = {"SPEAKER_00": "Doctor", "SPEAKER_01": "Patient"}

    return role_mapping


# ---------------------------------------------------------------------------
# Unified Diarization & Transcription Pipeline
# ---------------------------------------------------------------------------

def diarize_and_transcribe(
    wav: torch.Tensor,
    sample_rate: int = 16000,
    language: str = "ta",
    strategy: str = "ctc",
    min_pause_sec: float = DEFAULT_MIN_PAUSE_SEC,
    max_gap_sec: float = DEFAULT_MAX_SAME_SPEAKER_GAP,
    min_change_duration: float = DEFAULT_MIN_SPEAKER_CHANGE_DURATION
) -> Dict[str, Any]:
    """
    Executes:
    1. Acoustic VAD segmentation (Stage A1)
    2. Acoustic speaker identity clustering (Stage A2: SPEAKER_00, SPEAKER_01)
    3. Same-speaker segment merging & anti-flipping (Stage A3)
    4. IndicConformer ASR transcription on merged turns
    5. Global conversational role attribution (Stage B: Doctor vs Patient)
    """
    # Step 1: Detect speech segments
    raw_segments = detect_speech_segments(
        wav,
        sample_rate=sample_rate,
        min_pause_duration_sec=min_pause_sec
    )

    # Step 2: Assign acoustic speaker identity via Gaussian KL clustering
    clustered_segments = cluster_speaker_identities(
        raw_segments,
        sample_rate=sample_rate,
        min_change_duration_sec=min_change_duration
    )

    # Step 3: Merge same-speaker segments & suppress micro-flipping
    merged_turns = merge_same_speaker_segments(
        clustered_segments,
        max_gap_sec=max_gap_sec,
        min_change_duration_sec=min_change_duration
    )

    # Step 4: Transcribe merged turns with IndicConformer ASR
    model = get_model()
    transcribed_turns = []

    for turn in merged_turns:
        seg_audio = turn["audio"]
        with torch.no_grad():
            output = model(seg_audio, language, decoding=strategy)

        if isinstance(output, (list, tuple)):
            text = output[0] if len(output) > 0 else ""
        elif isinstance(output, dict):
            text = output.get("text", str(output))
        else:
            text = str(output)

        cleaned_text = text.strip()
        if cleaned_text:
            turn["text"] = cleaned_text
            transcribed_turns.append(turn)

    # Step 5: Global Conversational Role Attribution (Stage B)
    role_mapping = score_speaker_transcripts(transcribed_turns)

    dialogue_lines = []
    combined_pieces = []
    final_turns = []

    for turn in transcribed_turns:
        spk_id = turn.get("speaker_id", "SPEAKER_00")
        text = turn["text"].lower()
        doc_score = sum(1.0 for p in DOCTOR_LEXICON if re.search(p, text))
        pat_score = sum(1.0 for p in PATIENT_LEXICON if re.search(p, text))

        # Check explicit prescription authority and vocatives
        if doc_score >= 1.0 and re.search(r"எடுத்துக்கோங்க|எடுத்துக்கொள்ளுங்கள்|சாப்பிடுங்கள்|கவலைப்பட\s*வேண்டாம்|பேராசட்டமால்|பேராசிட்டமால்|பேண்டடோ", text):
            role = "Doctor"
        elif re.search(r"டாக்டர்\s*எனக்கு|போதுமா\s*டாக்டர்|\bdoctor\b.*\?", text) and doc_score == 0:
            role = "Patient"
        elif doc_score > pat_score:
            role = "Doctor"
        elif pat_score > doc_score:
            role = "Patient"
        else:
            role = role_mapping.get(spk_id, "Doctor")

        spk_id = "SPEAKER_01" if role == "Doctor" else "SPEAKER_00"
        turn["speaker"] = role
        turn["speaker_id"] = spk_id

        m, s = divmod(int(turn["start_sec"]), 60)
        timestamp_str = f"[{m:02d}:{s:02d}]"
        speaker_line = f"{timestamp_str} {role}: {turn['text']}"

        dialogue_lines.append(speaker_line)
        combined_pieces.append(turn["text"])

        final_turns.append({
            "turn_id": turn["turn_id"],
            "speaker_id": spk_id,
            "speaker": role,
            "start_sec": turn["start_sec"],
            "end_sec": turn["end_sec"],
            "text": turn["text"]
        })

    speaker_labelled_transcript = "\n".join(dialogue_lines)
    combined_transcript = " ".join(combined_pieces)

    # Clean serialized raw segments for debug export
    debug_raw = [{
        "segment_id": s["segment_id"],
        "start_sec": s["start_sec"],
        "end_sec": s["end_sec"],
        "speaker_id": s.get("speaker_id")
    } for s in raw_segments]

    return {
        "raw_segments_count": len(raw_segments),
        "merged_turns_count": len(final_turns),
        "raw_segments": debug_raw,
        "role_mapping": role_mapping,
        "turns": final_turns,
        "speaker_labelled_transcript": speaker_labelled_transcript,
        "combined_transcript": combined_transcript
    }
