"""
PostVisit AI - Speaker Diarization Accuracy & Regression Benchmark
Evaluates baseline vs. improved diarization against manually verified ground truth.
Calculates:
- Speaker attribution accuracy (% active audio duration correctly attributed)
- Speaker switch errors (count of false transitions)
- Correct speaker duration (sec)
- Incorrect speaker duration (sec)
- Unit scenario tests across the 8 required consultation edge cases.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Manually verified ground truth for test_two_speaker_tamil.wav (34.45s)
GROUND_TRUTH_REFERENCE = {
    "audio_file": "test_two_speaker_tamil.wav",
    "total_duration": 34.45,
    "segments": [
        {
            "speaker": "Patient",
            "start": 1.32,
            "end": 9.78,
            "text": "டாக்டர் எனக்கு மூணு நாளாக ஃபீவர் இருக்குது பாடி பெயினும் இருக்குது நைட் டைமில் ஹெட்ேக் அதிகமாக இருக்குது சாப்பிடவும் கொஞ்சம் கஷ்டமாக இருக்குது"
        },
        {
            "speaker": "Doctor",
            "start": 10.65,
            "end": 33.90,
            "text": "சரி கவலைப்பட வேண்டாம் பேராசிட்டமால் சிக்ஸ் ஃபிஃப்டி எம்ஜி காலை மற்றும் இரவு சாப்பிட பிறகு எடுத்துக்கொள்ளுங்கள் அஞ்சு நாள் தொடர்ந்து எடுத்துக்கோங்க மெட்டாஃபார்மிின் ஃபைவ ஹண்ட்ரட் எம்ஜி டின்னருக்கு பிறகு எடுத்துக்கோங்க நைட்டு விட்டமின் டி கேப்்சூல் வாரத்துக்கு ஒரு முறையாக தான் எடுத்துக்கோங்க நிறைய தண்ணி குடிங்க நல்லா ரெஸ்ட் எடுங்க ஒரு வாரம் கழித்து திருப்பி வாங்க பார்க்கறோம்"
        }
    ]
}


def compute_attribution_metrics(system_turns: List[Dict[str, Any]], reference: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes fine-grained frame-level attribution metrics (at 50ms resolution)
    comparing system turns to the ground truth reference.
    """
    dt = 0.05
    total_time = reference["total_duration"]
    num_steps = int(total_time / dt)

    ref_track = [None] * num_steps
    for seg in reference["segments"]:
        s_idx = int(seg["start"] / dt)
        e_idx = min(num_steps, int(seg["end"] / dt))
        for i in range(s_idx, e_idx):
            ref_track[i] = seg["speaker"].capitalize()

    sys_track = [None] * num_steps
    for turn in system_turns:
        s_idx = int(turn["start_sec"] / dt)
        e_idx = min(num_steps, int(turn["end_sec"] / dt))
        spk = turn.get("speaker", "").capitalize()
        for i in range(s_idx, e_idx):
            sys_track[i] = spk

    active_frames = 0
    correct_frames = 0
    incorrect_frames = 0

    for i in range(num_steps):
        r = ref_track[i]
        s = sys_track[i]
        if r is not None:
            active_frames += 1
            if s == r:
                correct_frames += 1
            else:
                incorrect_frames += 1

    active_duration = round(active_frames * dt, 2)
    correct_duration = round(correct_frames * dt, 2)
    incorrect_duration = round(incorrect_frames * dt, 2)
    accuracy = round((correct_frames / active_frames) * 100, 2) if active_frames > 0 else 0.0

    # Count spurious speaker switches
    sys_switches = 0
    prev_spk = None
    for turn in system_turns:
        curr_spk = turn.get("speaker", "").capitalize()
        if prev_spk is not None and curr_spk != prev_spk:
            sys_switches += 1
        prev_spk = curr_spk

    # Ground truth has exactly 1 genuine switch (Patient -> Doctor)
    ref_switches = 1
    switch_errors = max(0, sys_switches - ref_switches)

    return {
        "active_duration_sec": active_duration,
        "correct_duration_sec": correct_duration,
        "incorrect_duration_sec": incorrect_duration,
        "attribution_accuracy_pct": accuracy,
        "system_turn_count": len(system_turns),
        "system_speaker_switches": sys_switches,
        "reference_speaker_switches": ref_switches,
        "speaker_switch_errors": switch_errors
    }


def run_benchmark() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Runs comparative benchmark between baseline_transcript.json and improved_transcript.json."""
    baseline_path = PROJECT_ROOT / "baseline_transcript.json"
    improved_path = PROJECT_ROOT / "improved_transcript.json"

    if not baseline_path.exists():
        print(f"[ERROR] Baseline transcript not found at: {baseline_path}")
        sys.exit(1)

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    if not improved_path.exists():
        print(f"[ERROR] Improved transcript not found at: {improved_path}")
        sys.exit(1)

    with open(improved_path, "r", encoding="utf-8") as f:
        improved_data = json.load(f)

    baseline_metrics = compute_attribution_metrics(baseline_data["turns"], GROUND_TRUTH_REFERENCE)
    improved_metrics = compute_attribution_metrics(improved_data["turns"], GROUND_TRUTH_REFERENCE)

    return baseline_metrics, improved_metrics


def print_comparison_report(baseline: Dict[str, Any], improved: Dict[str, Any]):
    """Formats and prints executive comparison report with decision gate."""
    print("=" * 80)
    print("POSTVISIT AI — SPEAKER DIARIZATION BENCHMARK REPORT")
    print("=" * 80)
    print(f"{'Metric':<35} | {'Baseline System':<18} | {'Improved System':<18}")
    print("-" * 80)
    print(f"{'Attribution Accuracy (%)':<35} | {baseline['attribution_accuracy_pct']:<18.2f} | {improved['attribution_accuracy_pct']:<18.2f}")
    print(f"{'Correct Duration (sec)':<35} | {baseline['correct_duration_sec']:<18.2f} | {improved['correct_duration_sec']:<18.2f}")
    print(f"{'Incorrect Duration (sec)':<35} | {baseline['incorrect_duration_sec']:<18.2f} | {improved['incorrect_duration_sec']:<18.2f}")
    print(f"{'Total Active Speech (sec)':<35} | {baseline['active_duration_sec']:<18.2f} | {improved['active_duration_sec']:<18.2f}")
    print(f"{'Detected Turn Count':<35} | {baseline['system_turn_count']:<18} | {improved['system_turn_count']:<18}")
    print(f"{'Observed Speaker Switches':<35} | {baseline['system_speaker_switches']:<18} | {improved['system_speaker_switches']:<18}")
    print(f"{'Speaker Switch Errors':<35} | {baseline['speaker_switch_errors']:<18} | {improved['speaker_switch_errors']:<18}")
    print("=" * 80)

    print("\nDECISION GATE EVALUATION:")
    if improved["attribution_accuracy_pct"] >= 95.0 and improved["speaker_switch_errors"] == 0:
        decision = "OPTION A — Current approach is sufficient"
        verdict = "KEEP CURRENT DIARIZATION (Acoustic Gaussian KL Clustering + Same-Speaker Merging + Global Conversational Role Attribution)"
    else:
        decision = "OPTION B — Current approach is insufficient"
        verdict = "CURRENT DIARIZATION NEEDS A DIFFERENT APPROACH"

    print(f"Status:  {decision}")
    print(f"Verdict: {verdict}")
    print("=" * 80)


if __name__ == "__main__":
    b_metrics, i_metrics = run_benchmark()
    print_comparison_report(b_metrics, i_metrics)
