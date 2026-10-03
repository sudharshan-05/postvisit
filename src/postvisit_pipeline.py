"""
PostVisit AI - End-to-End Clinical Consultation Pipeline
Target Architecture:
    MP3 / MP4 / WAV
           ↓
    Audio extraction + normalization (PyAV / soundfile)
           ↓
    Speaker diarization (Acoustic VAD + MFCC Gaussian KL clustering)
           ↓
    Doctor / Patient turns (Global conversational role attribution)
           ↓
    Multilingual ASR (IndicConformer)
           ↓
    Speaker-labelled transcript
           ↓
    LLM medical extraction (Preserving schedule & source evidence)
           ↓
    Structured JSON & Validation
           ↓
    Doctor verification layer
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio_processor import load_and_normalize_audio
from src.diarization import diarize_and_transcribe
from src.medical_extractor import extract_medical_record, validate_schema
from src.doctor_verification import DoctorVerification


def run_pipeline(
    media_path: str,
    language: str = "ta",
    strategy: str = "ctc",
    verify_doctor: Optional[str] = None,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Executes the full clinical consultation processing pipeline with performance tracking
    and debug artifacts generation.
    """
    total_start_time = time.time()

    media_file = Path(media_path)
    if not media_file.exists():
        raise FileNotFoundError(f"Input media file not found: {media_file}")

    file_ext = media_file.suffix.upper().replace(".", "")
    print("=" * 80)
    print("PostVisit AI - End-to-End Clinical Consultation Pipeline")
    print(f"Input Media File:    {media_file} ({file_ext})")
    print(f"Target Language:     Tamil ({language})")
    print(f"ASR Strategy:        {strategy.upper()}")
    print(f"Debug Mode:          {'ENABLED' if debug else 'DISABLED'}")
    print("=" * 80)

    # -------------------------------------------------------------
    # Step 1: Audio Extraction & Normalization
    # -------------------------------------------------------------
    step1_start = time.time()
    print(f"\n[Step 1] Extracting & normalizing audio from {file_ext} container...")
    wav, sr = load_and_normalize_audio(str(media_file))
    duration_sec = round(wav.shape[-1] / sr, 2)
    step1_time = round(time.time() - step1_start, 2)
    print(f"         Audio extracted: 16 kHz mono float32 | Duration: {duration_sec}s (in {step1_time}s)")

    # -------------------------------------------------------------
    # Step 2 & 3: Speaker Diarization & Multilingual ASR
    # -------------------------------------------------------------
    diar_start = time.time()
    print("\n[Step 2 & 3] Performing acoustic turn segmentation, diarization & IndicConformer ASR...")
    diarization_result = diarize_and_transcribe(
        wav,
        sample_rate=sr,
        language=language,
        strategy=strategy
    )
    diar_asr_time = round(time.time() - diar_start, 2)

    turns = diarization_result["turns"]
    speaker_transcript = diarization_result["speaker_labelled_transcript"]
    combined_transcript = diarization_result["combined_transcript"]
    role_mapping = diarization_result["role_mapping"]
    raw_segments = diarization_result.get("raw_segments", [])

    print(f"         Diarization & ASR completed in {diar_asr_time}s")
    print(f"         Raw segments detected: {diarization_result['raw_segments_count']}")
    print(f"         Merged turns:          {diarization_result['merged_turns_count']}")
    print(f"         Role Mapping:          {role_mapping}")

    print("\n" + "-" * 80)
    print("SPEAKER-LABELLED CLINICAL DIALOGUE TRANSCRIPT:")
    print("-" * 80)
    print(speaker_transcript)
    print("-" * 80)

    if not combined_transcript.strip():
        raise ValueError("Transcription produced empty output.")

    # -------------------------------------------------------------
    # Step 4: Semantic Clinical Extraction via LLM
    # -------------------------------------------------------------
    llm_start = time.time()
    print("\n[Step 4] Extracting structured clinical entities via LLM...")
    extraction_input = speaker_transcript if speaker_transcript.strip() else combined_transcript
    record = extract_medical_record(extraction_input)
    llm_time = round(time.time() - llm_start, 2)

    medical_data = record["medical_information"]
    validation = record["validation"]
    print(f"         LLM semantic extraction completed in {llm_time}s")

    print("\n" + "-" * 80)
    print("STRUCTURED MEDICAL JSON:")
    print("-" * 80)
    print(json.dumps(medical_data, ensure_ascii=False, indent=2))
    print("-" * 80)

    # -------------------------------------------------------------
    # Step 5: Schema & Safety Validation
    # -------------------------------------------------------------
    print("\n[Step 5] Checking schema constraints and clinical rules...")
    if validation["valid"]:
        validation_status = "VALID (Passed 100% schema conformance & field type checks)"
    else:
        validation_status = f"INVALID ({', '.join(validation.get('errors', []))})"
    print(f"         Validation Status: {validation_status}")

    # -------------------------------------------------------------
    # Step 6: Doctor Verification Layer
    # -------------------------------------------------------------
    print("\n[Step 6] Evaluating doctor review and physician verification status...")
    verification = DoctorVerification.create_pending_verification(medical_data, validation)

    if verify_doctor:
        verification = DoctorVerification.approve_and_sign(
            verification,
            doctor_name=verify_doctor,
            notes="Reviewed and approved consultation transcript and clinical extraction."
        )

    print("\n" + DoctorVerification.format_summary(verification))

    # -------------------------------------------------------------
    # Performance & RTF Calculation
    # -------------------------------------------------------------
    total_processing_time = round(time.time() - total_start_time, 2)
    rtf = round(total_processing_time / duration_sec, 2) if duration_sec > 0 else 0.0

    print("\n" + "=" * 80)
    print("PIPELINE PERFORMANCE MEASUREMENT:")
    print("=" * 80)
    print(f"Audio duration:        {duration_sec:.2f} sec")
    print(f"Audio extraction time: {step1_time:.2f} sec")
    print(f"Diarization + ASR:     {diar_asr_time:.2f} sec")
    print(f"LLM extraction time:   {llm_time:.2f} sec")
    print(f"Total processing time: {total_processing_time:.2f} sec")
    print(f"Real-Time Factor (RTF):{rtf:.2f}")
    print("=" * 80)

    # -------------------------------------------------------------
    # Debug Artifacts Export
    # -------------------------------------------------------------
    if debug:
        debug_dir = PROJECT_ROOT / "debug"
        debug_dir.mkdir(exist_ok=True)
        print(f"\n[DEBUG] Saving debug artifacts to: {debug_dir}")

        # 1. diarization.json
        with open(debug_dir / "diarization.json", "w", encoding="utf-8") as f:
            json.dump({
                "audio_file": str(media_file),
                "duration_sec": duration_sec,
                "raw_segments_count": len(raw_segments),
                "raw_segments": raw_segments
            }, f, ensure_ascii=False, indent=2)

        # 2. merged_segments.json
        with open(debug_dir / "merged_segments.json", "w", encoding="utf-8") as f:
            json.dump({
                "merged_turns_count": len(turns),
                "turns": turns
            }, f, ensure_ascii=False, indent=2)

        # 3. transcript.json
        with open(debug_dir / "transcript.json", "w", encoding="utf-8") as f:
            json.dump({
                "speaker_labelled_transcript": speaker_transcript,
                "combined_transcript": combined_transcript
            }, f, ensure_ascii=False, indent=2)

        # 4. role_mapping.json
        with open(debug_dir / "role_mapping.json", "w", encoding="utf-8") as f:
            formatted_role_mapping = {
                spk: {"role": role.lower()} for spk, role in role_mapping.items()
            }
            json.dump(formatted_role_mapping, f, ensure_ascii=False, indent=2)

        # 5. medical_extraction.json
        with open(debug_dir / "medical_extraction.json", "w", encoding="utf-8") as f:
            json.dump({
                "medical_information": medical_data,
                "validation": validation,
                "doctor_verification": verification
            }, f, ensure_ascii=False, indent=2)

        print("         Debug files written:")
        print("         - debug/diarization.json")
        print("         - debug/merged_segments.json")
        print("         - debug/transcript.json")
        print("         - debug/role_mapping.json")
        print("         - debug/medical_extraction.json")

    # -------------------------------------------------------------
    # Final Output Object
    # -------------------------------------------------------------
    final_output = {
        "media_file": str(media_file),
        "audio_format": file_ext,
        "audio_duration_sec": duration_sec,
        "processing_time_sec": total_processing_time,
        "rtf": rtf,
        "speaker_turns": turns,
        "role_mapping": role_mapping,
        "speaker_labelled_transcript": speaker_transcript,
        "combined_transcript": combined_transcript,
        "medical_information": medical_data,
        "validation": validation,
        "doctor_verification": verification
    }

    return final_output


def main():
    parser = argparse.ArgumentParser(description="PostVisit AI End-to-End Pipeline")
    parser.add_argument(
        "media_path",
        nargs="?",
        default="test.wav",
        help="Path to media file: MP3, MP4, or WAV (default: test.wav)"
    )
    parser.add_argument(
        "--lang",
        default="ta",
        help="Language code (default: ta for Tamil)"
    )
    parser.add_argument(
        "--strategy",
        default="ctc",
        choices=["rnnt", "ctc"],
        help="ASR Decoding strategy: ctc or rnnt (default: ctc)"
    )
    parser.add_argument(
        "--verify",
        default=None,
        help="Doctor name to simulate physician verification sign-off (e.g., --verify 'Dr. Ramanathan')"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode and export detailed stage JSONs to debug/"
    )

    args = parser.parse_args()
    try:
        run_pipeline(
            args.media_path,
            language=args.lang,
            strategy=args.strategy,
            verify_doctor=args.verify,
            debug=args.debug
        )
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
