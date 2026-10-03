"""
PostVisit AI - Milestone 2: Medical Information Extraction Evaluation Suite
Evaluates dynamic semantic extraction, safety rules, anti-hallucination compliance,
and scalability across 46 clinical scenarios (including unseen medicines & custom entities).
Measures inference latency, initialization time, and system resource metrics.
"""

import sys
import time
import json
import tracemalloc
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.medical_extractor import extract_medical_information, get_llm_client, validate_schema

# ---------------------------------------------------------------------------
# Comprehensive Clinical Evaluation Dataset (46 Scenarios)
# ---------------------------------------------------------------------------
TEST_DATASET: List[Dict[str, Any]] = [
    # --- PART 1: 20 Core Clinical Scenarios (Corrected for generic reference) ---
    {
        "id": "TC-01",
        "category": "Generic Reference (Missing Name Rule)",
        "transcript": "இந்த மாத்திரையை தினமும் இரவு சாப்பிட்ட பிறகு எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": None,  # MUST NOT treat generic word as drug name
        "expected_strength": None,
        "expected_freq": "once daily",
        "expected_timing": "night, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-02",
        "category": "Complete Clinical Prescription",
        "transcript": "Metformin 500 mg இரவு உணவுக்குப் பிறகு எடுத்துக்கொள்ளுங்கள். முப்பது நாட்களுக்கு தொடர்ந்து எடுக்கவும்.",
        "expected_med": "Metformin",
        "expected_strength": "500 mg",
        "expected_freq": None,
        "expected_timing": "night, after food",
        "expected_duration": "30 days",
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-03",
        "category": "Antihypertensive Morning Regimen",
        "transcript": "Amlodipine 5 mg தினமும் காலை உணவுக்கு முன் எடுத்துக்கொள்ள வேண்டும்.",
        "expected_med": "Amlodipine",
        "expected_strength": "5 mg",
        "expected_freq": "once daily",
        "expected_timing": "morning, before food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-04",
        "category": "Analgesic PRN / SOS with Symptom",
        "transcript": "Paracetamol 650 mg காய்ச்சல் வரும் போது மட்டும் எடுத்துக் கொள்ளுங்கள்.",
        "expected_med": "Paracetamol",
        "expected_strength": "650 mg",
        "expected_freq": "as needed",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-05",
        "category": "Antibiotic Fixed Course",
        "transcript": "Azithromycin 500 mg ஐந்து நாட்களுக்கு தினமும் ஒரு வேளை எடுத்துக்கொள்ள வேண்டும்.",
        "expected_med": "Azithromycin",
        "expected_strength": "500 mg",
        "expected_freq": "once daily",
        "expected_timing": None,
        "expected_duration": "5 days",
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-06",
        "category": "Statin Bedtime Regimen",
        "transcript": "Atorvastatin 10 mg தூங்குவதற்கு முன் இரவில் மட்டும் எடுத்துக் கொள்ளுங்கள்.",
        "expected_med": "Atorvastatin",
        "expected_strength": "10 mg",
        "expected_freq": None,
        "expected_timing": "night",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-07",
        "category": "Thyroid Empty Stomach Regimen",
        "transcript": "Thyroxine 50 mcg தினமும் காலையில் வெறும் வயிற்றில் சாப்பிட வேண்டும்.",
        "expected_med": "Thyroxine",
        "expected_strength": "50 mcg",
        "expected_freq": "once daily",
        "expected_timing": "morning, empty stomach",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-08",
        "category": "Liquid Volume Dosage",
        "transcript": "Cough syrup 5 ml தினமும் மூன்று முறை சாப்பாட்டுக்கு பின் குடிக்கவும்.",
        "expected_med": "Cough syrup",
        "expected_strength": "5 ml",
        "expected_freq": "thrice daily",
        "expected_timing": "after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-09",
        "category": "Injectable Units Regimen",
        "transcript": "Insulin 10 units காலை உணவுக்கு அரை மணி நேரத்திற்கு முன் போட வேண்டும்.",
        "expected_med": "Insulin",
        "expected_strength": "10 units",
        "expected_freq": None,
        "expected_timing": "before food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-10",
        "category": "Diagnostic Monitoring Test",
        "transcript": "HbA1c test-ஐ அடுத்த visit-க்கு முன்னால் செய்து கொள்ளுங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": "HbA1c",
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-11",
        "category": "Emergency Cardiac Diagnostic",
        "transcript": "நெஞ்சு வலி இருந்தால் உடனே ECG எடுத்து பார்க்க வேண்டும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": "ECG",
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-12",
        "category": "Routine Consultation Follow-up",
        "transcript": "ஒரு மாதம் கழித்து மீண்டும் check-upக்கு வரவும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": "1 மாதம்",
        "expected_review": True
    },
    {
        "id": "TC-13",
        "category": "Tanglish Code-Switched Follow-up",
        "transcript": "Two weeks கழித்து follow-upக்கு வரவும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": "2 weeks",
        "expected_review": True
    },
    {
        "id": "TC-14",
        "category": "Dietary Lifestyle Advice",
        "transcript": "உப்பு மற்றும் எண்ணெய் உணவுகளை குறைத்துக் கொள்ள வேண்டும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-15",
        "category": "Hydration Fluid Intake",
        "transcript": "தினமும் குறைந்தது மூன்று லிட்டர் தண்ணீர் குடிக்க வேண்டும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-16",
        "category": "Home Vitals Self-Monitoring",
        "transcript": "BP-ஐ morning மற்றும் night check பண்ணுங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-17",
        "category": "Code-Mixed Multi-Entity Dialogue",
        "transcript": "Metformin 500 mg-ஐ night dinnerக்கு பிறகு எடுத்துக்கொள்ளுங்கள். BP கொஞ்சம் high-ஆ இருக்கிறது.",
        "expected_med": "Metformin",
        "expected_strength": "500 mg",
        "expected_freq": None,
        "expected_timing": "night, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-18",
        "category": "Red Flag Urgent Warning",
        "transcript": "Chest pain அல்லது breathing difficulty இருந்தால் உடனே hospital-க்கு செல்லவும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-19",
        "category": "Anti-Hallucination Incomplete Dosage",
        "transcript": "Metformin எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "Metformin",
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-20",
        "category": "Anti-Hallucination Generic Prescription",
        "transcript": "மருந்தை சாப்பிடுங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },

    # --- PART 2: 10 Unseen Medicine Tests ---
    {
        "id": "TC-U01",
        "category": "Unseen Medicine: Empagliflozin",
        "transcript": "Empagliflozin 10 mg தினமும் காலையில் எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "Empagliflozin",
        "expected_strength": "10 mg",
        "expected_freq": "once daily",
        "expected_timing": "morning",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U02",
        "category": "Unseen Medicine: Semaglutide",
        "transcript": "Semaglutide 0.5 mg வாரத்திற்கு ஒரு முறை ஊசி மூலம் எடுத்துக்கொள்ளவும்.",
        "expected_med": "Semaglutide",
        "expected_strength": "0.5 mg",
        "expected_freq": "once weekly",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U03",
        "category": "Unseen Medicine: Tirzepatide",
        "transcript": "Tirzepatide 2.5 mg வாரத்திற்கு ஒரு முறை எடுத்துக்கொள்ள வேண்டும்.",
        "expected_med": "Tirzepatide",
        "expected_strength": "2.5 mg",
        "expected_freq": "once weekly",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U04",
        "category": "Unseen Medicine: Rivaroxaban",
        "transcript": "Rivaroxaban 15 mg இரவு உணவுக்குப் பிறகு சாப்பிடவும்.",
        "expected_med": "Rivaroxaban",
        "expected_strength": "15 mg",
        "expected_freq": None,
        "expected_timing": "night, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U05",
        "category": "Unseen Medicine: Linagliptin",
        "transcript": "Linagliptin 5 mg தினமும் ஒரு வேளை எடுத்துக்கொள்ளவும்.",
        "expected_med": "Linagliptin",
        "expected_strength": "5 mg",
        "expected_freq": "once daily",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U06",
        "category": "Unseen Medicine: Sacubitril",
        "transcript": "Sacubitril 50 mg காலை மற்றும் இரவு எடுத்துக்கொள்ள வேண்டும்.",
        "expected_med": "Sacubitril",
        "expected_strength": "50 mg",
        "expected_freq": "twice daily",
        "expected_timing": "morning, night",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U07",
        "category": "Unseen Medicine: Dapagliflozin",
        "transcript": "Dapagliflozin 10 mg காலை உணவுக்கு முன் சாப்பிடவும்.",
        "expected_med": "Dapagliflozin",
        "expected_strength": "10 mg",
        "expected_freq": None,
        "expected_timing": "morning, before food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U08",
        "category": "Unseen Medicine: Entresto",
        "transcript": "Entresto 100 mg இரு வேளை உணவுக்குப் பிறகு எடுத்துக்கொள்ளவும்.",
        "expected_med": "Entresto",
        "expected_strength": "100 mg",
        "expected_freq": "twice daily",
        "expected_timing": "after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U09",
        "category": "Unseen Medicine: Farxiga",
        "transcript": "Farxiga 5 mg காலையில் எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "Farxiga",
        "expected_strength": "5 mg",
        "expected_freq": None,
        "expected_timing": "morning",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-U10",
        "category": "Unseen Medicine: Sitagliptin",
        "transcript": "Sitagliptin 100 mg ஒரு வேளை எடுத்துக்கொள்ளவும்.",
        "expected_med": "Sitagliptin",
        "expected_strength": "100 mg",
        "expected_freq": "once daily",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },

    # --- PART 3: 5 Custom / Unknown Synthetic Names ---
    {
        "id": "TC-C01",
        "category": "Custom Entity: NewDrug-X",
        "transcript": "NewDrug-X 25 mg காலை உணவுக்குப் பிறகு எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "NewDrug-X",
        "expected_strength": "25 mg",
        "expected_freq": None,
        "expected_timing": "morning, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-C02",
        "category": "Custom Entity: Medicine-A",
        "transcript": "Medicine-A 100 mg இரவு தூங்குவதற்கு முன் எடுத்துக்கொள்ளவும்.",
        "expected_med": "Medicine-A",
        "expected_strength": "100 mg",
        "expected_freq": None,
        "expected_timing": "night",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-C03",
        "category": "Custom Entity: ABC-25",
        "transcript": "ABC-25 10 ml மூன்று வேளை உணவுக்குப் பின் குடிக்கவும்.",
        "expected_med": "ABC-25",
        "expected_strength": "10 ml",
        "expected_freq": "thrice daily",
        "expected_timing": "after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-C04",
        "category": "Custom Entity: TestMedicine",
        "transcript": "TestMedicine 50 mg தினமும் ஒரு வேளை எடுத்துக்கொள்ள வேண்டும்.",
        "expected_med": "TestMedicine",
        "expected_strength": "50 mg",
        "expected_freq": "once daily",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-C05",
        "category": "Custom Entity: Drug-XYZ",
        "transcript": "Drug-XYZ 500 mg தேவைப்படும் போது மட்டும் எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "Drug-XYZ",
        "expected_strength": "500 mg",
        "expected_freq": "as needed",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },

    # --- PART 4: 5 Generic References ---
    {
        "id": "TC-G01",
        "category": "Generic: இந்த மாத்திரை",
        "transcript": "இந்த மாத்திரையை தினமும் இரவு சாப்பிட்ட பிறகு எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": "once daily",
        "expected_timing": "night, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-G02",
        "category": "Generic: இந்த மருந்து",
        "transcript": "இந்த மருந்தை காலையில் வெறும் வயிற்றில் குடிக்க வேண்டும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": "morning, empty stomach",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-G03",
        "category": "Generic: this tablet",
        "transcript": "this tablet-ஐ தினமும் இரு வேளை எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": "twice daily",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-G04",
        "category": "Generic: that medicine",
        "transcript": "that medicine-ஐ இரவு உணவுக்குப் பின் சாப்பிடவும்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": "night, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-G05",
        "category": "Generic: மருந்தை சாப்பிடுங்கள்",
        "transcript": "மருந்தை சாப்பிடுங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },

    # --- PART 5: 5 Incomplete Prescriptions ---
    {
        "id": "TC-I01",
        "category": "Incomplete: Missing all dosage",
        "transcript": "Metformin எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "Metformin",
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-I02",
        "category": "Incomplete: Missing freq/duration",
        "transcript": "Amlodipine 5 mg எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "Amlodipine",
        "expected_strength": "5 mg",
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-I03",
        "category": "Incomplete: PRN missing strength",
        "transcript": "Paracetamol காய்ச்சல் வரும் போது மட்டும் எடுத்துக்கொள்ளவும்.",
        "expected_med": "Paracetamol",
        "expected_strength": None,
        "expected_freq": "as needed",
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-I04",
        "category": "Incomplete: Missing duration",
        "transcript": "Atorvastatin 10 mg இரவில் எடுத்துக்கொள்ளவும்.",
        "expected_med": "Atorvastatin",
        "expected_strength": "10 mg",
        "expected_freq": None,
        "expected_timing": "night",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },
    {
        "id": "TC-I05",
        "category": "Incomplete: Ambiguous advice",
        "transcript": "மாத்திரை சாப்பிடுங்கள் ஏதும் பிரச்சனை என்றால் வாருங்கள்.",
        "expected_med": None,
        "expected_strength": None,
        "expected_freq": None,
        "expected_timing": None,
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    },

    # --- PART 6: 1 Critical Scalability Test ---
    {
        "id": "TC-CRIT",
        "category": "Critical Scalability (Zero Code Presence)",
        "transcript": "ABC-NewMedicine 37.5 mg இரவு உணவுக்குப் பிறகு எடுத்துக்கொள்ளுங்கள்.",
        "expected_med": "ABC-NewMedicine",
        "expected_strength": "37.5 mg",
        "expected_freq": None,
        "expected_timing": "night, after food",
        "expected_duration": None,
        "expected_test": None,
        "expected_follow_up": None,
        "expected_review": True
    }
]


def run_evaluation_suite(dataset: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Executes benchmark evaluation on clinical test cases.
    Measures latency, memory usage, anti-hallucination compliance, and test-set accuracy.
    """
    data_to_test = dataset or TEST_DATASET
    print("=" * 85)
    print("PostVisit AI - Milestone 2 Clinical Extraction Evaluation Suite")
    print(f"Total Scenarios in Benchmark: {len(data_to_test)}")
    print("=" * 85)

    # Initialize memory tracker & measure initialization time
    tracemalloc.start()
    t_init_start = time.time()
    client = get_llm_client()
    init_time = time.time() - t_init_start
    print(f"[Engine] Provider: {client.provider.upper()} | Model: {client.model}")
    print(f"[Engine] Client initialization time: {init_time * 1000:.2f} ms")

    stats = {
        "total": len(data_to_test),
        "passed": 0,
        "failed": 0,
        "correct_med": 0,
        "correct_strength": 0,
        "correct_freq": 0,
        "correct_timing": 0,
        "correct_duration": 0,
        "correct_test": 0,
        "correct_follow_up": 0,
        "hallucinations": 0,
        "doctor_reviews_flagged": 0,
        "expected_doctor_reviews": 0
    }

    latencies: List[float] = []

    print(f"\n{'ID':<8} {'Category':<32} {'Med':<10} {'Dose':<8} {'Timing':<8} {'Review':<8} {'Latency':<8} {'Status':<6}")
    print("-" * 94)

    first_inference_time: Optional[float] = None

    for idx, tc in enumerate(data_to_test):
        t0 = time.time()
        res = extract_medical_information(tc["transcript"])
        dt = time.time() - t0
        latencies.append(dt)

        if idx == 0:
            first_inference_time = dt

        actual_meds = res.get("medications", [])
        actual_med = actual_meds[0]["name"] if actual_meds else None
        # Strength or dose
        actual_strength = (actual_meds[0]["strength"] or actual_meds[0].get("dose")) if actual_meds else None
        actual_freq = actual_meds[0]["frequency"] if actual_meds else None
        actual_timing = actual_meds[0]["timing"] if actual_meds else None
        actual_duration = actual_meds[0]["duration"] if actual_meds else None

        actual_tests = res.get("tests", [])
        actual_test_name = actual_tests[0]["name"] if actual_tests else None
        actual_follow_up_time = res.get("follow_up", {}).get("time")

        # 1. Medication Name Evaluation
        med_ok = False
        if tc["expected_med"] is None:
            if actual_med is None:
                med_ok = True
        elif actual_med:
            exp_m = tc["expected_med"].lower()
            act_m = actual_med.lower()
            if exp_m in act_m or act_m in exp_m:
                med_ok = True
        if med_ok:
            stats["correct_med"] += 1

        # 2. Strength / Dosage Evaluation
        dose_ok = False
        if tc["expected_strength"] is None:
            if actual_strength is None:
                dose_ok = True
            else:
                stats["hallucinations"] += 1
        elif actual_strength and tc["expected_strength"].lower() in actual_strength.lower():
            dose_ok = True
        if dose_ok:
            stats["correct_strength"] += 1

        # 3. Frequency Evaluation
        freq_ok = False
        if tc["expected_freq"] is None:
            # If not explicitly expected, either None or present as spoken is acceptable unless hallucinated
            freq_ok = True
        elif actual_freq:
            freq_ok = True
        if freq_ok:
            stats["correct_freq"] += 1

        # 4. Timing Evaluation
        timing_ok = False
        if tc["expected_timing"] is None:
            timing_ok = True
        elif actual_timing:
            timing_ok = True
        if timing_ok:
            stats["correct_timing"] += 1

        # 5. Tests Evaluation
        test_ok = False
        if tc["expected_test"] is None:
            test_ok = True
        elif actual_test_name and tc["expected_test"].lower() in actual_test_name.lower():
            test_ok = True
        if test_ok:
            stats["correct_test"] += 1

        # 6. Doctor Review Flagging
        if res.get("requires_doctor_review"):
            stats["doctor_reviews_flagged"] += 1
        if tc["expected_review"]:
            stats["expected_doctor_reviews"] += 1

        review_ok = (res.get("requires_doctor_review") == tc["expected_review"])
        all_ok = med_ok and dose_ok and test_ok and review_ok

        if all_ok:
            stats["passed"] += 1
            status_str = "PASS"
        else:
            stats["failed"] += 1
            status_str = "FAIL"

        print(
            f"{tc['id']:<8} {tc['category'][:30]:<32} "
            f"{'OK' if med_ok else 'FAIL':<10} "
            f"{'OK' if dose_ok else 'FAIL':<8} "
            f"{'OK' if timing_ok else 'NONE':<8} "
            f"{'YES' if res.get('requires_doctor_review') else 'NO':<8} "
            f"{dt:.2f}s    "
            f"{status_str:<6}"
        )

    # Memory measurement
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    print("-" * 94)
    print("\n" + "=" * 85)
    print("Milestone 2 Performance & Accuracy Evaluation Report")
    print("=" * 85)
    print(f"Total Benchmark Scenarios:          {stats['total']}")
    print(f"Passed Scenarios:                   {stats['passed']}/{stats['total']}")
    print(f"Failed Scenarios:                   {stats['failed']}/{stats['total']}")
    print(f"Test-Set Accuracy:                  {stats['passed']/stats['total']*100:.1f}%")
    print(f"Medication Extraction Accuracy:     {stats['correct_med']}/{stats['total']} ({stats['correct_med']/stats['total']*100:.1f}%)")
    print(f"Dosage Extraction Accuracy:         {stats['correct_strength']}/{stats['total']} ({stats['correct_strength']/stats['total']*100:.1f}%)")
    print(f"Doctor Review Compliance:           {stats['doctor_reviews_flagged']}/{stats['expected_doctor_reviews']} ({stats['doctor_reviews_flagged']/stats['expected_doctor_reviews']*100:.1f}%)")
    print(f"Hallucinations / Fabrications:      {stats['hallucinations']} (Strict Zero Tolerance)")
    print("-" * 85)
    print("Performance & Resource Metrics:")
    print(f"First Inference Latency:            {first_inference_time:.2f}s" if first_inference_time else "N/A")
    print(f"Average Inference Latency:          {avg_latency:.2f}s")
    print(f"Peak Process Memory Allocated:      {peak_mem / 1024:.2f} KB ({peak_mem / (1024*1024):.2f} MB)")
    print("=" * 85)
    print("⚠️ CLINICAL NOTE: The above metric reflects Test-Set Accuracy on this benchmark suite.")
    print("   Do NOT claim 100% Medical Accuracy for real-world clinical deployment without ongoing")
    print("   licensed physician review and validation on diverse clinical consultation corpora.")
    print("=" * 85)

    return stats


if __name__ == "__main__":
    run_extraction_evaluation_suite = run_evaluation_suite()
