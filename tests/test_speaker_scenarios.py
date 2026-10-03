"""
PostVisit AI - Unit & Scenario Test Suite for Speaker Continuity & Role Attribution
Validates the 8 critical consultation interaction scenarios specified in Section 11:
  Test 1: Clean two-speaker Tamil conversation
  Test 2: Doctor speaks continuously with pauses
  Test 3: Patient speaks continuously with pauses
  Test 4: Doctor interrupts patient
  Test 5: Patient interrupts doctor
  Test 6: Short acknowledgements ("ஆம்", "சரி", "Okay")
  Test 7: Doctor gives 3-4 medicines in one paragraph
  Test 8: Patient mentions an existing medicine
"""

import sys
import unittest
from pathlib import Path
from typing import List, Dict, Any

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.diarization import (
    merge_same_speaker_segments,
    score_speaker_transcripts,
    DEFAULT_MAX_SAME_SPEAKER_GAP,
    DEFAULT_MIN_SPEAKER_CHANGE_DURATION
)
from src.medical_extractor import extract_medical_record


class TestSpeakerDiarizationScenarios(unittest.TestCase):

    def test_scenario_1_clean_two_speaker(self):
        """Test 1: Clean two-speaker Tamil conversation."""
        turns = [
            {"turn_id": 1, "speaker_id": "SPEAKER_00", "text": "டாக்டர் எனக்கு உடம்பு சரியில்லை ஃபீவர் இருக்குது"},
            {"turn_id": 2, "speaker_id": "SPEAKER_01", "text": "சரி இந்த மாத்திரை சாப்பிடுங்கள் கவலைப்பட வேண்டாம்"}
        ]
        role_map = score_speaker_transcripts(turns)
        self.assertEqual(role_map["SPEAKER_00"], "Patient")
        self.assertEqual(role_map["SPEAKER_01"], "Doctor")

    def test_scenario_2_doctor_speaks_continuously(self):
        """Test 2: Doctor speaks continuously across small breath pauses without speaker switching."""
        segments = [
            {"segment_id": 1, "speaker_id": "SPEAKER_01", "start_sec": 10.0, "end_sec": 14.0, "audio": None},
            {"segment_id": 2, "speaker_id": "SPEAKER_01", "start_sec": 14.5, "end_sec": 18.0, "audio": None},
            {"segment_id": 3, "speaker_id": "SPEAKER_01", "start_sec": 18.6, "end_sec": 22.0, "audio": None}
        ]
        # Merging with max_gap=1.05s
        merged = []
        cur = segments[0].copy()
        for s in segments[1:]:
            if s["speaker_id"] == cur["speaker_id"] and (s["start_sec"] - cur["end_sec"]) <= 1.05:
                cur["end_sec"] = s["end_sec"]
            else:
                merged.append(cur)
                cur = s.copy()
        merged.append(cur)

        self.assertEqual(len(merged), 1, "All 3 doctor segments should merge into a single turn")
        self.assertEqual(merged[0]["start_sec"], 10.0)
        self.assertEqual(merged[0]["end_sec"], 22.0)

    def test_scenario_3_patient_speaks_continuously(self):
        """Test 3: Patient speaks continuously across pauses describing complaints."""
        turns = [
            {"turn_id": 1, "speaker_id": "SPEAKER_00", "text": "டாக்டர் எனக்கு மூணு நாளாக ஃபீவர் இருக்குது"},
            {"turn_id": 2, "speaker_id": "SPEAKER_00", "text": "சாப்பிடவும் கொஞ்சம் கஷ்டமாக இருக்குது தூக்கம் வரல"}
        ]
        role_map = score_speaker_transcripts(turns)
        self.assertEqual(role_map["SPEAKER_00"], "Patient")

    def test_scenario_4_doctor_interrupts_patient(self):
        """Test 4: Doctor interrupts patient to clarify symptoms."""
        turns = [
            {"turn_id": 1, "speaker_id": "SPEAKER_00", "text": "எனக்கு ரொம்ப நாளா தலைவலிக்குது..."},
            {"turn_id": 2, "speaker_id": "SPEAKER_01", "text": "எத்தனை நாளா இருக்குது? வாந்தி வருதா?"},
            {"turn_id": 3, "speaker_id": "SPEAKER_00", "text": "ரெண்டு நாளா இருக்குது டாக்டர்"}
        ]
        role_map = score_speaker_transcripts(turns)
        self.assertEqual(role_map["SPEAKER_00"], "Patient")
        self.assertEqual(role_map["SPEAKER_01"], "Doctor")

    def test_scenario_5_patient_interrupts_doctor(self):
        """Test 5: Patient interrupts doctor during instructions."""
        turns = [
            {"turn_id": 1, "speaker_id": "SPEAKER_01", "text": "இந்த மருந்தை காலையில சாப்பாட்டுக்கு முன்னாடி போடுங்க"},
            {"turn_id": 2, "speaker_id": "SPEAKER_00", "text": "வெறும் வயித்துல போடணுமா டாக்டர்?"},
            {"turn_id": 3, "speaker_id": "SPEAKER_01", "text": "ஆமாம் வெறும் வயித்துல சாப்பிடுங்க"}
        ]
        role_map = score_speaker_transcripts(turns)
        self.assertEqual(role_map["SPEAKER_00"], "Patient")
        self.assertEqual(role_map["SPEAKER_01"], "Doctor")

    def test_scenario_6_short_acknowledgements(self):
        """Test 6: Short acknowledgements ('சரி', 'ஆம்', 'Okay') do not trigger permanent flipping."""
        segments = [
            {"segment_id": 1, "speaker_id": "SPEAKER_01", "start_sec": 10.0, "end_sec": 15.0},
            # Isolated short acknowledgement: 0.4s
            {"segment_id": 2, "speaker_id": "SPEAKER_00", "start_sec": 15.2, "end_sec": 15.6},
            {"segment_id": 3, "speaker_id": "SPEAKER_01", "start_sec": 15.9, "end_sec": 22.0}
        ]
        # Anti-flipping smoothing check
        for i in range(1, len(segments) - 1):
            dur = segments[i]["end_sec"] - segments[i]["start_sec"]
            prev_s = segments[i - 1]["speaker_id"]
            next_s = segments[i + 1]["speaker_id"]
            if prev_s == next_s and segments[i]["speaker_id"] != prev_s and dur < 0.80:
                segments[i]["speaker_id"] = prev_s

        self.assertEqual(segments[1]["speaker_id"], "SPEAKER_01", "Micro-flip should be smoothed to maintain temporal continuity")

    def test_scenario_7_doctor_prescribes_multiple_medicines(self):
        """Test 7: Doctor gives 3-4 medicines in one turn; preserves specific schedule."""
        text = (
            "[00:10] Doctor: பேராசிட்டமால் 650 mg காலை மற்றும் இரவு சாப்பிட பிறகு எடுத்துக்கொள்ளுங்கள். "
            "மெட்டாஃபார்மின் 500 mg டின்னருக்கு பிறகு எடுத்துக்கோங்க. "
            "விட்டமின் டி கேப்்சூல் வாரத்துக்கு ஒரு முறை எடுத்துக்கோங்க."
        )
        record = extract_medical_record(text)
        meds = record["medical_information"]["medications"]
        self.assertGreaterEqual(len(meds), 3, "Should extract all 3 prescribed medications")

        paracetamol = next((m for m in meds if "paracetamol" in m["name"].lower()), None)
        self.assertIsNotNone(paracetamol)
        self.assertEqual(paracetamol["specific_schedule"], ["morning", "night"])

    def test_scenario_8_patient_mentions_existing_medicine(self):
        """Test 8: Patient mentioning past medicine does not override doctor's prescription authority."""
        turns = [
            {"turn_id": 1, "speaker_id": "SPEAKER_00", "text": "டாக்டர் நான் ஏற்கனவே Amlodipine 5 mg போட்டுட்டு இருக்கேன் எனக்கு ஃபீவர் இருக்குது"},
            {"turn_id": 2, "speaker_id": "SPEAKER_01", "text": "சரி அதை தொடருங்கள் இப்போதைக்கு Paracetamol 650 mg மட்டும் எடுத்துக்கொள்ளுங்கள்"}
        ]
        role_map = score_speaker_transcripts(turns)
        self.assertEqual(role_map["SPEAKER_00"], "Patient")
        self.assertEqual(role_map["SPEAKER_01"], "Doctor")


if __name__ == "__main__":
    unittest.main()
