"""
PostVisit AI - Milestone 2: Comprehensive Clinical Extraction Test Suite
Includes:
- Original 20 Clinical Scenarios (with corrected generic reference behavior)
- 10 Unseen Medicine Tests (evaluating dynamic extraction without hardcoded drug lists)
- 5 Unknown / Custom Synthetic Names (NewDrug-X, Medicine-A, ABC-25, TestMedicine, Drug-XYZ)
- 5 Generic References (verifying name defaults to null)
- 5 Incomplete Prescriptions (verifying missing attributes and doctor review flags)
- 1 Critical Scalability Test (medication name never in code/prompts/training)
"""

import sys
import unittest
from pathlib import Path

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.medical_extractor import extract_medical_information, validate_schema


class TestMedicalInformationExtraction(unittest.TestCase):

    # =========================================================================
    # PART 1: ORIGINAL 20 CLINICAL SCENARIOS (Updated to Milestone 2 Schema)
    # =========================================================================

    def test_01_generic_tamil_prescription(self):
        """Test Case 1: Generic prescription without drug name. Name must be null."""
        transcript = "இந்த மாத்திரையை தினமும் இரவு சாப்பிட்ட பிறகு எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertGreaterEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        # CRITICAL FIX: Generic phrase must NOT be accepted as drug name
        self.assertIsNone(med["name"])
        self.assertIsNone(med["strength"])
        self.assertIsNotNone(med["frequency"])
        self.assertIsNotNone(med["timing"])
        self.assertTrue(data["requires_doctor_review"])
        self.assertGreaterEqual(len(data["uncertain_items"]), 1)

    def test_02_metformin_complete_prescription(self):
        """Test Case 2: Complete prescription with drug name, strength, timing, and duration."""
        transcript = "Metformin 500 mg இரவு உணவுக்குப் பிறகு எடுத்துக்கொள்ளுங்கள். முப்பது நாட்களுக்கு தொடர்ந்து எடுக்கவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Metformin")
        self.assertEqual(med["strength"], "500 mg")
        self.assertIsNotNone(med["timing"])
        self.assertIn("30", str(med["duration"]))

    def test_03_amlodipine_morning_prescription(self):
        """Test Case 3: Antihypertensive with morning timing and food relation."""
        transcript = "Amlodipine 5 mg தினமும் காலை உணவுக்கு முன் எடுத்துக்கொள்ள வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Amlodipine")
        self.assertEqual(med["strength"], "5 mg")
        self.assertIsNotNone(med["timing"])

    def test_04_paracetamol_sos_dosage(self):
        """Test Case 4: PRN/SOS medication with symptom correlation."""
        transcript = "Paracetamol 650 mg காய்ச்சல் வரும் போது மட்டும் எடுத்துக் கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Paracetamol")
        self.assertEqual(med["strength"], "650 mg")
        self.assertTrue(any("காய்ச்சல்" in s or "fever" in s.lower() for s in data["symptoms_mentioned"]) or med["frequency"] is not None)

    def test_05_antibiotics_fixed_duration(self):
        """Test Case 5: Antibiotic course with strict day duration."""
        transcript = "Azithromycin 500 mg ஐந்து நாட்களுக்கு தினமும் ஒரு வேளை எடுத்துக்கொள்ள வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Azithromycin")
        self.assertEqual(med["strength"], "500 mg")
        self.assertTrue("5" in str(med["duration"]) or "ஐந்து" in str(med["duration"]) or "five" in str(med["duration"]).lower())

    def test_06_atorvastatin_bedtime(self):
        """Test Case 6: Lipid lowering drug taken at bedtime."""
        transcript = "Atorvastatin 10 mg தூங்குவதற்கு முன் இரவில் மட்டும் எடுத்துக் கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Atorvastatin")
        self.assertEqual(med["strength"], "10 mg")

    def test_07_thyroxine_empty_stomach(self):
        """Test Case 7: Thyroid medication with mcg units and empty stomach."""
        transcript = "Thyroxine 50 mcg தினமும் காலையில் வெறும் வயிற்றில் சாப்பிட வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Thyroxine")
        self.assertEqual(med["strength"], "50 mcg")

    def test_08_syrup_liquid_dosage(self):
        """Test Case 8: Liquid medication with ml volume units."""
        transcript = "Cough syrup 5 ml தினமும் மூன்று முறை சாப்பாட்டுக்கு பின் குடிக்கவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertGreaterEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        dosage_val = med.get("dose") or med.get("strength")
        self.assertEqual(dosage_val, "5 ml")

    def test_09_insulin_units(self):
        """Test Case 9: Injectable insulin with units measurement."""
        transcript = "Insulin 10 units காலை உணவுக்கு அரை மணி நேரத்திற்கு முன் போட வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Insulin")
        units_val = med.get("dose") or med.get("strength")
        self.assertEqual(units_val, "10 units")

    def test_10_lab_test_hba1c(self):
        """Test Case 10: Diabetic diagnostic monitoring before visit."""
        transcript = "HbA1c test-ஐ அடுத்த visit-க்கு முன்னால் செய்து கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 0)
        self.assertGreaterEqual(len(data["tests"]), 1)
        test = data["tests"][0]
        self.assertIn("hba1c", test["name"].lower())

    def test_11_cardiac_ecg_test(self):
        """Test Case 11: Emergency cardiac diagnostic test."""
        transcript = "நெஞ்சு வலி இருந்தால் உடனே ECG எடுத்து பார்க்க வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertGreaterEqual(len(data["tests"]), 1)
        self.assertIn("ecg", data["tests"][0]["name"].lower())

    def test_12_routine_follow_up(self):
        """Test Case 12: Tamil follow-up consultation timeline."""
        transcript = "ஒரு மாதம் கழித்து மீண்டும் check-upக்கு வரவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertIsNotNone(data["follow_up"]["time"])
        self.assertTrue("1" in data["follow_up"]["time"] or "மாதம்" in data["follow_up"]["time"] or "month" in data["follow_up"]["time"].lower())

    def test_13_code_switching_follow_up(self):
        """Test Case 13: Tanglish code-switched follow-up."""
        transcript = "Two weeks கழித்து follow-upக்கு வரவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertIsNotNone(data["follow_up"]["time"])
        self.assertTrue("2" in data["follow_up"]["time"] or "two" in data["follow_up"]["time"].lower() or "week" in data["follow_up"]["time"].lower())

    def test_14_dietary_instructions(self):
        """Test Case 14: Dietary lifestyle management."""
        transcript = "உப்பு மற்றும் எண்ணெய் உணவுகளை குறைத்துக் கொள்ள வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertGreaterEqual(len(data["instructions"]), 1)

    def test_15_lifestyle_water_intake(self):
        """Test Case 15: Fluid hydration guidance."""
        transcript = "தினமும் குறைந்தது மூன்று லிட்டர் தண்ணீர் குடிக்க வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertGreaterEqual(len(data["instructions"]), 1)

    def test_16_code_mixed_vitals_monitoring(self):
        """Test Case 16: Blood pressure home monitoring schedule."""
        transcript = "BP-ஐ morning மற்றும் night check பண்ணுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertTrue(len(data["instructions"]) > 0 or len(data["tests"]) > 0)

    def test_17_code_mixed_complex_prescription(self):
        """Test Case 17: Multi-lingual doctor dialogue with prescription and vitals."""
        transcript = "Metformin 500 mg-ஐ night dinnerக்கு பிறகு எடுத்துக்கொள்ளுங்கள். BP கொஞ்சம் high-ஆ இருக்கிறது."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Metformin")
        self.assertEqual(med["strength"], "500 mg")

    def test_18_warning_emergency_red_flag(self):
        """Test Case 18: Urgent warning and hospital visit criteria."""
        transcript = "Chest pain அல்லது breathing difficulty இருந்தால் உடனே hospital-க்கு செல்லவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertTrue(len(data["warnings"]) > 0 or len(data["instructions"]) > 0)

    def test_19_missing_dosage_critical_safety_rule(self):
        """Test Case 19: CRITICAL SAFETY RULE: Missing dosage MUST NOT be invented."""
        transcript = "Metformin எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Metformin")
        self.assertIsNone(med["strength"])
        self.assertIsNone(med["frequency"])
        self.assertIsNone(med["timing"])
        self.assertIsNone(med["duration"])
        self.assertTrue(data["requires_doctor_review"])
        self.assertGreaterEqual(len(data["uncertain_items"]), 1)

    def test_20_ambiguous_tablet_safety_rule(self):
        """Test Case 20: Generic ambiguous prescription without medication name."""
        transcript = "மருந்தை சாப்பிடுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertTrue(data["requires_doctor_review"])
        self.assertGreaterEqual(len(data["uncertain_items"]), 1)

    # =========================================================================
    # PART 2: 10 UNSEEN MEDICINE TESTS (Dynamic Extraction without Whitelist)
    # =========================================================================

    def test_u01_empagliflozin(self):
        """Unseen Medicine 1: Empagliflozin SGLT2 inhibitor."""
        transcript = "Empagliflozin 10 mg தினமும் காலையில் எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Empagliflozin")
        self.assertEqual(data["medications"][0]["strength"], "10 mg")

    def test_u02_semaglutide(self):
        """Unseen Medicine 2: Semaglutide GLP-1 agonist."""
        transcript = "Semaglutide 0.5 mg வாரத்திற்கு ஒரு முறை ஊசி மூலம் எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Semaglutide")
        self.assertEqual(data["medications"][0]["strength"], "0.5 mg")

    def test_u03_tirzepatide(self):
        """Unseen Medicine 3: Tirzepatide dual GIP/GLP-1."""
        transcript = "Tirzepatide 2.5 mg வாரத்திற்கு ஒரு முறை எடுத்துக்கொள்ள வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Tirzepatide")
        self.assertEqual(data["medications"][0]["strength"], "2.5 mg")

    def test_u04_rivaroxaban(self):
        """Unseen Medicine 4: Rivaroxaban anticoagulant."""
        transcript = "Rivaroxaban 15 mg இரவு உணவுக்குப் பிறகு சாப்பிடவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Rivaroxaban")
        self.assertEqual(data["medications"][0]["strength"], "15 mg")

    def test_u05_linagliptin(self):
        """Unseen Medicine 5: Linagliptin DPP-4 inhibitor."""
        transcript = "Linagliptin 5 mg தினமும் ஒரு வேளை எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Linagliptin")
        self.assertEqual(data["medications"][0]["strength"], "5 mg")

    def test_u06_sacubitril(self):
        """Unseen Medicine 6: Sacubitril heart failure therapy."""
        transcript = "Sacubitril 50 mg காலை மற்றும் இரவு எடுத்துக்கொள்ள வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Sacubitril")
        self.assertEqual(data["medications"][0]["strength"], "50 mg")

    def test_u07_dapagliflozin(self):
        """Unseen Medicine 7: Dapagliflozin SGLT2 inhibitor."""
        transcript = "Dapagliflozin 10 mg காலை உணவுக்கு முன் சாப்பிடவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Dapagliflozin")
        self.assertEqual(data["medications"][0]["strength"], "10 mg")

    def test_u08_entresto(self):
        """Unseen Medicine 8: Entresto brand medication."""
        transcript = "Entresto 100 mg இரு வேளை உணவுக்குப் பிறகு எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Entresto")
        self.assertEqual(data["medications"][0]["strength"], "100 mg")

    def test_u09_farxiga(self):
        """Unseen Medicine 9: Farxiga brand medication."""
        transcript = "Farxiga 5 mg காலையில் எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Farxiga")
        self.assertEqual(data["medications"][0]["strength"], "5 mg")

    def test_u10_sitagliptin(self):
        """Unseen Medicine 10: Sitagliptin antidiabetic."""
        transcript = "Sitagliptin 100 mg ஒரு வேளை எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Sitagliptin")
        self.assertEqual(data["medications"][0]["strength"], "100 mg")

    # =========================================================================
    # PART 3: 5 UNKNOWN / CUSTOM SYNTHETIC NAMES
    # =========================================================================

    def test_c01_newdrug_x(self):
        """Custom Name 1: NewDrug-X explicitly from user prompt."""
        transcript = "NewDrug-X 25 mg காலை உணவுக்குப் பிறகு எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "NewDrug-X")
        self.assertEqual(data["medications"][0]["strength"], "25 mg")

    def test_c02_medicine_a(self):
        """Custom Name 2: Medicine-A synthetic entity."""
        transcript = "Medicine-A 100 mg இரவு தூங்குவதற்கு முன் எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Medicine-A")
        self.assertEqual(data["medications"][0]["strength"], "100 mg")

    def test_c03_abc_25(self):
        """Custom Name 3: ABC-25 liquid entity."""
        transcript = "ABC-25 10 ml மூன்று வேளை உணவுக்குப் பின் குடிக்கவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "ABC-25")
        dosage_val = med.get("dose") or med.get("strength")
        self.assertEqual(dosage_val, "10 ml")

    def test_c04_testmedicine(self):
        """Custom Name 4: TestMedicine synthetic entity."""
        transcript = "TestMedicine 50 mg தினமும் ஒரு வேளை எடுத்துக்கொள்ள வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "TestMedicine")
        self.assertEqual(data["medications"][0]["strength"], "50 mg")

    def test_c05_drug_xyz(self):
        """Custom Name 5: Drug-XYZ SOS entity."""
        transcript = "Drug-XYZ 500 mg தேவைப்படும் போது மட்டும் எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertEqual(data["medications"][0]["name"], "Drug-XYZ")
        self.assertEqual(data["medications"][0]["strength"], "500 mg")

    # =========================================================================
    # PART 4: 5 GENERIC REFERENCES (Name must be null, Flag Doctor Review)
    # =========================================================================

    def test_g01_indha_maathirai(self):
        """Generic Reference 1: இந்த மாத்திரை must not become name."""
        transcript = "இந்த மாத்திரையை தினமும் இரவு சாப்பிட்ட பிறகு எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertGreaterEqual(len(data["medications"]), 1)
        self.assertIsNone(data["medications"][0]["name"])
        self.assertTrue(data["requires_doctor_review"])

    def test_g02_indha_marundhu(self):
        """Generic Reference 2: இந்த மருந்து must not become name."""
        transcript = "இந்த மருந்தை காலையில் வெறும் வயிற்றில் குடிக்க வேண்டும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        if data["medications"]:
            self.assertIsNone(data["medications"][0]["name"])
        self.assertTrue(data["requires_doctor_review"])

    def test_g03_this_tablet(self):
        """Generic Reference 3: this tablet must not become name."""
        transcript = "this tablet-ஐ தினமும் இரு வேளை எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        if data["medications"]:
            self.assertIsNone(data["medications"][0]["name"])
        self.assertTrue(data["requires_doctor_review"])

    def test_g04_that_medicine(self):
        """Generic Reference 4: that medicine must not become name."""
        transcript = "that medicine-ஐ இரவு உணவுக்குப் பின் சாப்பிடவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        if data["medications"]:
            self.assertIsNone(data["medications"][0]["name"])
        self.assertTrue(data["requires_doctor_review"])

    def test_g05_marundhai_saapidungal(self):
        """Generic Reference 5: மருந்தை சாப்பிடுங்கள் ambiguous."""
        transcript = "மருந்தை சாப்பிடுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertTrue(data["requires_doctor_review"])

    # =========================================================================
    # PART 5: 5 INCOMPLETE PRESCRIPTIONS
    # =========================================================================

    def test_i01_missing_all_dosage_fields(self):
        """Incomplete 1: Drug mentioned with zero dosage, timing, duration."""
        transcript = "Metformin எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Metformin")
        self.assertIsNone(med["strength"])
        self.assertIsNone(med["frequency"])
        self.assertIsNone(med["timing"])
        self.assertIsNone(med["duration"])
        self.assertTrue(data["requires_doctor_review"])

    def test_i02_missing_frequency_and_duration(self):
        """Incomplete 2: Drug + strength given, but missing frequency and duration."""
        transcript = "Amlodipine 5 mg எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "Amlodipine")
        self.assertEqual(med["strength"], "5 mg")
        self.assertIsNone(med["duration"])
        self.assertTrue(data["requires_doctor_review"])

    def test_i03_missing_strength_on_prn(self):
        """Incomplete 3: PRN drug without explicit mg strength."""
        transcript = "Paracetamol காய்ச்சல் வரும் போது மட்டும் எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertIsNone(data["medications"][0]["strength"])
        self.assertTrue(data["requires_doctor_review"])

    def test_i04_missing_duration(self):
        """Incomplete 4: Statin given at night without duration."""
        transcript = "Atorvastatin 10 mg இரவில் எடுத்துக்கொள்ளவும்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertEqual(len(data["medications"]), 1)
        self.assertIsNone(data["medications"][0]["duration"])
        self.assertTrue(data["requires_doctor_review"])

    def test_i05_ambiguous_instruction(self):
        """Incomplete 5: Ambiguous instruction triggering doctor review."""
        transcript = "மாத்திரை சாப்பிடுங்கள் ஏதும் பிரச்சனை என்றால் வாருங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)
        self.assertTrue(data["requires_doctor_review"])

    # =========================================================================
    # PART 6: CRITICAL SCALABILITY TEST
    # =========================================================================

    def test_crit_abc_newmedicine(self):
        """
        CRITICAL SCALABILITY TEST:
        Medication has NEVER appeared in source code, prompt examples, or training datasets.
        The extractor must extract ABC-NewMedicine purely via semantic comprehension.
        """
        transcript = "ABC-NewMedicine 37.5 mg இரவு உணவுக்குப் பிறகு எடுத்துக்கொள்ளுங்கள்."
        data = extract_medical_information(transcript)
        validate_schema(data)

        self.assertEqual(len(data["medications"]), 1)
        med = data["medications"][0]
        self.assertEqual(med["name"], "ABC-NewMedicine")
        self.assertEqual(med["strength"], "37.5 mg")
        self.assertIsNotNone(med["timing"])


if __name__ == "__main__":
    unittest.main()
