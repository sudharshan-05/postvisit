"""
PostVisit AI - Dataset Evaluation Runner
Evaluates all test audios against tests/expected_transcripts.csv
"""

import sys
import os
import csv
from pathlib import Path

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.asr import transcribe_audio
from src.evaluate import evaluate_medical_accuracy


def run_full_evaluation(csv_path: str = "tests/expected_transcripts.csv"):
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: CSV file not found at {csv_file}")
        sys.exit(1)

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 80)
    print("PostVisit AI - Medical ASR Evaluation Suite")
    print(f"Total test cases configured: {len(rows)}")
    print("=" * 80)

    total_tested = 0
    passed = 0
    medical_entity_errors = 0
    reviews_required = 0
    wers = []

    for row in rows:
        audio_name = row["audio"]
        expected_text = row["expected_text"]
        hint = row.get("key_entities", "")

        # Look in tests/ or audio/
        audio_path = Path("tests") / audio_name
        if not audio_path.exists():
            audio_path = Path("audio") / audio_name

        if not audio_path.exists():
            print(f"[-] [SKIPPED] {audio_name}: Audio file not present yet")
            continue

        total_tested += 1
        print(f"\n[+] Testing {audio_name} ({row.get('category', 'General')})")
        print(f"    Expected: {expected_text}")

        try:
            result = transcribe_audio(str(audio_path), language="ta")
            actual_text = result["text"]
            print(f"    Actual:   {actual_text}")

            eval_res = evaluate_medical_accuracy(expected_text, actual_text, hint)
            print(f"    Status:   {eval_res['status']} (WER: {eval_res['wer'] * 100:.1f}%)")
            if eval_res["status"] == "MEDICAL ENTITY ERROR":
                print(f"    Alert:    {eval_res['reason']}")
                medical_entity_errors += 1
            elif eval_res["status"] == "PASS":
                passed += 1
            else:
                reviews_required += 1

            wers.append(eval_res["wer"])

        except Exception as e:
            print(f"    [ERROR] Failed to transcribe: {e}")
            medical_entity_errors += 1

    print("\n" + "=" * 80)
    print("Evaluation Summary")
    print(f"Total Tested:           {total_tested}")
    print(f"Passed:                 {passed}")
    print(f"Medical Entity Errors:  {medical_entity_errors}")
    print(f"Review Required:        {reviews_required}")
    if wers:
        avg_wer = sum(wers) / len(wers)
        print(f"Average WER:            {avg_wer * 100:.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    run_full_evaluation()
