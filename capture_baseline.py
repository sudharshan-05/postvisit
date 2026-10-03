import json
import time
from src.audio_processor import load_and_normalize_audio
from src.diarization import diarize_and_transcribe

t0 = time.time()
wav, sr = load_and_normalize_audio("test_two_speaker_tamil.wav")
res = diarize_and_transcribe(wav, sample_rate=sr, strategy="ctc")
dt = time.time() - t0

baseline_output = {
    "audio_file": "test_two_speaker_tamil.wav",
    "processing_time_sec": round(dt, 2),
    "turns": res["turns"],
    "speaker_labelled_transcript": res["speaker_labelled_transcript"],
    "combined_transcript": res["combined_transcript"]
}

with open("baseline_transcript.json", "w", encoding="utf-8") as f:
    json.dump(baseline_output, f, ensure_ascii=False, indent=2)

print("baseline_transcript.json saved successfully in", round(dt, 2), "s")
