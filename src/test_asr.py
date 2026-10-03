"""
PostVisit AI - Command-Line ASR Test Runner
Usage:
    python src/test_asr.py [path_to_audio] [--lang ta] [--strategy ctc]
"""

import sys
import os
import argparse
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

LANGUAGE_NAMES = {
    "ta": "Tamil",
    "hi": "Hindi",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "bn": "Bengali",
    "en": "English"
}


def main():
    parser = argparse.ArgumentParser(description="Test PostVisit AI Tamil Speech-to-Text")
    parser.add_argument(
        "audio_path",
        nargs="?",
        default="audio/test.wav",
        help="Path to WAV audio file (default: audio/test.wav)"
    )
    parser.add_argument(
        "--lang",
        default="ta",
        help="Language code (default: ta for Tamil)"
    )
    parser.add_argument(
        "--strategy",
        default="ctc",
        choices=["ctc", "rnnt"],
        help="Decoding strategy: ctc or rnnt (default: ctc)"
    )

    args = parser.parse_args()

    audio_file = Path(args.audio_path)
    if not audio_file.exists():
        print(f"Error: Audio file not found at '{audio_file}'")
        sys.exit(1)

    lang_display = LANGUAGE_NAMES.get(args.lang, args.lang)
    print("=" * 60)
    print(f"PostVisit AI - Speech Recognition Test")
    print(f"File:       {audio_file}")
    print(f"Language:   {lang_display} ({args.lang})")
    print(f"Strategy:   {args.strategy}")
    print("=" * 60)

    try:
        result = transcribe_audio(
            audio_path=str(audio_file),
            language=args.lang,
            strategy=args.strategy
        )

        print("\n" + "-" * 60)
        print(f"Language: {lang_display}")
        print(f"Transcript: {result['text']}")
        print("-" * 60)

    except Exception as e:
        print(f"\n[ERROR] Transcription failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
