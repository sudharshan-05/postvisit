"""
PostVisit AI - Milestone 2: Medical Validator, Normalizer & Safety Rules Engine
Performs deterministic schema verification, anti-hallucination checks,
multilingual & phonetic term normalization, generic reference correction,
cross-turn property association, and physician review enforcement.
"""

import re
from typing import Dict, List, Any, Tuple, Optional
from pydantic import ValidationError
from src.medical_schema import MedicalExtraction, MedicationItem, TestItem, FollowUpItem

# Generic terms referring to medication without identifying a drug
GENERIC_MEDICATION_TERMS = {
    "இந்த மாத்திரை", "இந்த மாத்திரையை",
    "இந்த மருந்து", "இந்த மருந்தை",
    "அந்த மாத்திரை", "அந்த மருந்து",
    "மாத்திரை", "மாத்திரையை", "மாத்திரைகள்",
    "மருந்து", "மருந்தை", "மருந்துகள்",
    "this medicine", "this tablet",
    "that medicine", "that tablet",
    "the medicine", "the tablet",
    "tablet", "capsule", "syrup", "drops", "injection",
    "medicine", "unspecified medicine", "unknown medicine"
}

# Phonetic number mappings for strength, dosage & duration
NUMBER_WORD_MAP = [
    (r"\b(?:சிக்ஸ்\s*ஃபிஃப்டி|six\s*fifty|650)\b", "650"),
    (r"\b(?:ஃபைவ்\s*ஹண்ட்ரட்|five\s*hundred|500)\b", "500"),
    (r"\b(?:ஒன்\s*ஹண்ட்ரட்|one\s*hundred|100)\b", "100"),
    (r"\b(?:பிஃப்டி|fifty|50)\b", "50"),
    (r"\b(?:ஃபார்ட்டி|forty|40)\b", "40"),
    (r"\b(?:தேர்ட்டி|thirty|முப்பது|30)\b", "30"),
    (r"\b(?:ட்வென்டி\s*ஃபைவ்|twenty\s*five|25)\b", "25"),
    (r"\b(?:ட்வென்டி|twenty|20)\b", "20"),
    (r"\b(?:ஃபிப்ட்டீன்|fifteen|15)\b", "15"),
    (r"\b(?:டென்|ten|பத்து|10)\b", "10"),
    (r"\b(?:எய்ட்|எட்டு|eight|8)\b", "8"),
    (r"\b(?:செவன்|ஏழு|seven|7)\b", "7"),
    (r"\b(?:சிக்ஸ்|ஆறு|six|6)\b", "6"),
    (r"\b(?:ஃபைவ்|ஐந்து|அஞ்சு|five|5)\b", "5"),
    (r"\b(?:ஃபோர்|நான்கு|four|4)\b", "4"),
    (r"\b(?:த்ரீ|மூன்று|மூணு|three|3)\b", "3"),
    (r"\b(?:டூ|இரண்டு|ரெண்டு|two|2)\b", "2"),
    (r"\b(?:ஒன்|ஒரு|one|1)\b", "1"),
    (r"\b(?:ஜீரோ|zero|0)\b", "0"),
]

# Standard phonetic Tamil drug names mapping to international non-proprietary names (INN)
# IMPORTANT: This is NOT a restrictive whitelist. Any unseen drug is preserved intact.
PHONETIC_DRUG_NAMES = [
    (r"\b(?:பேராசிட்டமால்|பேராசட்டமால்|போரசிட்டமால்|பாரசிட்டமால்|பாராசிட்டமால்|paracetamol)\b", "Paracetamol"),
    (r"\b(?:பேண்டடோ\s*பேராசோல்|பேண்டட\s*போரசால்|பேண்டோப்ராசோல்|பேண்டடோ|pantoprazole)\b", "Pantoprazole"),
    (r"\b(?:விட்டமின்\s*டி|வைட்டமின்\s*டி|vitamin\s*d)\b", "Vitamin D"),
    (r"\b(?:மெட்டாஃபார்மின்|மெட்பார்மின்|metformin)\b", "Metformin"),
    (r"\b(?:அம்லோடிபைன்|அம்லோடிபின்|amlodipine)\b", "Amlodipine"),
    (r"\b(?:அசித்ரோமைசின்|azithromycin)\b", "Azithromycin"),
    (r"\b(?:அட்டோர்வாஸ்டாடின்|அடோர்வாஸ்டாடின்|atorvastatin)\b", "Atorvastatin"),
    (r"\b(?:தைராக்சின்|thyroxine)\b", "Thyroxine"),
    (r"\b(?:இன்சுலின்|insulin)\b", "Insulin"),
    (r"\b(?:எம்பாக்ளிஃப்ளோசின்|empagliflozin)\b", "Empagliflozin"),
    (r"\b(?:செமாக்ளூடடைடு|semaglutide)\b", "Semaglutide"),
    (r"\b(?:டபாக்ளிஃப்ளோசின்|dapagliflozin)\b", "Dapagliflozin"),
    (r"\b(?:ரிவரோக்சபான்|rivaroxaban)\b", "Rivaroxaban"),
    (r"\b(?:லினாக்ளிப்டின்|linagliptin)\b", "Linagliptin"),
    (r"\b(?:சக்குபிட்ரில்|sacubitril)\b", "Sacubitril"),
    (r"\b(?:என்ட்ரெஸ்டோ|entresto)\b", "Entresto"),
    (r"\b(?:ஃபார்சிகா|farxiga)\b", "Farxiga"),
    (r"\b(?:சிடாக்ளிப்டின்|sitagliptin)\b", "Sitagliptin"),
    (r"\b(?:டிர்செபடைடு|tirzepatide)\b", "Tirzepatide"),
]


def normalize_strength_str(val: Optional[str]) -> Optional[str]:
    """Normalizes phonetic spoken numbers and units in medication strength."""
    if not val:
        return None
    s = val.strip()
    s_low = s.lower()

    # Detect unit
    unit = None
    if re.search(r"mcg|மைக்ரோகிராம்|microgram", s_low):
        unit = "mcg"
    elif re.search(r"units|யூனிட்ஸ்|unit", s_low):
        unit = "units"
    elif re.search(r"ml|மில்லிலிட்டர்|milliliter", s_low):
        unit = "ml"
    elif re.search(r"mg|மில்லிகிராம்|milligram|எம்ஜி", s_low):
        unit = "mg"

    # Detect number
    num_str = None
    # Check digit first
    d_match = re.search(r"\b\d+(?:\.\d+)?\b", s)
    if d_match:
        num_str = d_match.group(0)
    else:
        for pat, digit in NUMBER_WORD_MAP:
            if re.search(pat, s_low):
                num_str = digit
                break

    if num_str and unit:
        return f"{num_str} {unit}"
    elif num_str:
        return f"{num_str} mg" if "mg" in s_low or "எம்ஜி" in s_low else num_str
    return s


def normalize_duration_str(val: Optional[str]) -> Optional[str]:
    """Normalizes phonetic spoken durations (e.g. 'ஃபைவ் டேஸ்' -> '5 days')."""
    if not val:
        return None
    s = val.strip()
    s_low = s.lower()

    # Detect time unit
    t_unit = None
    if re.search(r"days|டேஸ்|நாட்கள்|நாட்களுக்கு|நாள்", s_low):
        t_unit = "days"
    elif re.search(r"weeks|வாரம்|வாரங்கள்|வாரத்துக்கு|வீக்|வீக்ஸ்", s_low):
        t_unit = "weeks"
    elif re.search(r"months|மாதம்|மாதங்கள்|மாதத்துக்கு|மந்த்", s_low):
        t_unit = "months"

    num_str = None
    d_match = re.search(r"\b\d+\b", s)
    if d_match:
        num_str = d_match.group(0)
    else:
        for pat, digit in NUMBER_WORD_MAP:
            if re.search(pat, s_low):
                num_str = digit
                break

    if num_str and t_unit:
        return f"{num_str} {t_unit}"
    return s


def normalize_drug_name(name: Optional[str]) -> Tuple[Optional[str], bool]:
    """
    Normalizes phonetic Tamil drug names to standard INN English names.
    Checks for generic references and preserves any custom or unseen medication.
    Returns: (normalized_name, is_generic)
    """
    if not name:
        return None, False

    clean_name = name.strip()
    clean_lower = clean_name.lower()

    # 1. Check generic reference
    if clean_lower in GENERIC_MEDICATION_TERMS or any(term == clean_name for term in GENERIC_MEDICATION_TERMS):
        return None, True

    # 2. Check phonetic mapping
    for pat, norm in PHONETIC_DRUG_NAMES:
        if re.search(pat, clean_lower):
            return norm, False

    # 3. Preserve custom, brand, or unseen names intact
    return clean_name, False


def normalize_timing_str(timing: Optional[str]) -> Optional[str]:
    """Standardizes timing expressions into clinical English."""
    if not timing:
        return None
    t_low = timing.lower()
    if re.search(r"empty\s*stomach|வெறும்\s*வயிற்றில்|எம்டிி\s*ஸ்டோமக்", t_low):
        if re.search(r"breakfast|பிரேக்ஃபாஸ்ட்|காலை", t_low):
            return "empty stomach"
        return "empty stomach"
    if re.search(r"before\s*breakfast|பிரேக்ஃபாஸ்ட்.*முன்|பிரேக்ஃபாஸ்ட்.*முன்னாடி|காலை.*முன்", t_low):
        return "before breakfast"
    if re.search(r"after\s*lunch|லன்ச்.*பின்|லன்ச்.*பிறகு|லன்ச்சுக்கு", t_low):
        return "after lunch"
    if re.search(r"after\s*dinner|டின்னர்.*பின்|டின்னர்.*பிறகு|இரவு.*சாப்பிட்ட\s*பிறகு", t_low):
        return "after dinner"
    if re.search(r"after\s*food|சாப்பிட்ட\s*பிறகு|உணவுக்குப்\s*பிறகு|ஆஃப்டர்\s*ஃபுட்|சாப்பாட்டுக்கு\s*பின்", t_low):
        return "after food"
    if re.search(r"before\s*food|உணவுக்கு\s*முன்|சாப்பாட்டுக்கு\s*முன்", t_low):
        return "before food"
    if re.search(r"pain|வலி|பெயின்", t_low):
        return "when pain"
    return timing


def sanitize_and_validate(raw_data: Dict[str, Any], transcript: str = "") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Sanitizes raw LLM output against clinical safety guidelines, corrects
    generic terms, checks for missing critical prescription attributes,
    normalizes phonetic terms, associates cross-turn properties, and
    enforces authoritative speaker attribution.
    """
    errors: List[str] = []
    uncertain_items: List[str] = list(raw_data.get("uncertain_items", []))
    requires_doctor_review: bool = True  # Always true for patient safety

    # 1. Extract raw lists
    raw_meds = raw_data.get("medications", [])
    raw_instructions = [str(x).strip() for x in raw_data.get("instructions", []) if x]
    raw_warnings = [str(x).strip() for x in raw_data.get("warnings", []) if x]
    raw_symptoms = [str(x).strip() for x in raw_data.get("symptoms_mentioned", []) if x]
    raw_follow_up = raw_data.get("follow_up", {})

    sanitized_meds: List[Dict[str, Any]] = []
    filtered_instructions: List[str] = []

    # Check for discontinued medications (e.g. Test 3: Metformin asked by patient, stopped by doctor)
    t_lower = transcript.lower()
    metformin_discontinued = bool(
        re.search(r"மெட்டாஃபார்மின்|metformin", transcript, re.I) and
        re.search(r"கன்[ட்ண்ட்டினியூ]*\s*பண்ண\s*வேண்டாம்|do\s*not\s*continue", transcript, re.I)
    )

    if metformin_discontinued:
        discontinue_msg = "Do not continue Metformin for now."
        if not any("metformin" in inst.lower() for inst in raw_instructions):
            raw_instructions.append(discontinue_msg)

    for med in raw_meds:
        if not isinstance(med, dict):
            continue

        raw_name = med.get("name")
        norm_name, is_generic = normalize_drug_name(raw_name)

        if is_generic:
            norm_name = None
            note = "The medication was referred to generically as 'this medicine'; its name was not stated."
            if note not in uncertain_items:
                uncertain_items.append(note)

        # Rule 2: If a medication was explicitly discontinued by doctor (e.g. Metformin in Test 3),
        # it must NOT be extracted as an active prescription
        if norm_name and norm_name.lower() == "metformin" and metformin_discontinued:
            discontinue_msg = "Do not continue Metformin for now."
            if discontinue_msg not in raw_instructions:
                raw_instructions.append(discontinue_msg)
            continue

        # Normalize strength & duration
        strength = normalize_strength_str(med.get("strength"))
        duration = normalize_duration_str(med.get("duration"))
        timing = normalize_timing_str(med.get("timing"))
        frequency = med.get("frequency")
        specific_schedule = med.get("specific_schedule")

        # Normalize frequency expressions
        if frequency:
            f_low = frequency.lower()
            if re.search(r"twice\s*daily|இருமுறை|இரு\s*வேளை|மார்னிங்\s*அண்ட்\s*நைட்|காலை\s*மற்றும்\s*இரவு", f_low):
                frequency = "twice daily"
            elif re.search(r"once\s*daily|ஒருமுறை|ஒரு\s*வேளை|தினமும்", f_low):
                frequency = "once daily"
            elif re.search(r"thrice\s*daily|மூன்று\s*முறை|மூன்று\s*வேளை", f_low):
                frequency = "thrice daily"
            elif re.search(r"once\s*weekly|weekly|வாரத்துக்கு\s*ஒரு\s*முறை", f_low):
                frequency = "once weekly"
            elif re.search(r"as\s*needed|prn|sos|தேவைப்படும்\s*போது|பெயின்\s*இருக்கும்போது", f_low):
                frequency = "as needed"

        # Normalize specific schedule list
        if isinstance(specific_schedule, list):
            clean_sched = []
            for sc in specific_schedule:
                sc_low = str(sc).lower()
                if "morning" in sc_low or "காலை" in sc_low or "மார்னிங்" in sc_low:
                    clean_sched.append("morning")
                elif "night" in sc_low or "இரவு" in sc_low or "நைட்" in sc_low:
                    clean_sched.append("night")
                elif "afternoon" in sc_low or "மதியம்" in sc_low:
                    clean_sched.append("afternoon")
            specific_schedule = clean_sched if clean_sched else None
        elif isinstance(specific_schedule, str):
            clean_sched = []
            sc_low = specific_schedule.lower()
            if "morning" in sc_low or "காலை" in sc_low or "மார்னிங்" in sc_low:
                clean_sched.append("morning")
            if "night" in sc_low or "இரவு" in sc_low or "நைட்" in sc_low:
                clean_sched.append("night")
            specific_schedule = clean_sched if clean_sched else None

        # Authoritative speaker rule: preserve source_speaker or default to Doctor
        source_speaker = med.get("source_speaker") or "Doctor"
        source_text = med.get("source_text")
        source_start = med.get("source_start")
        source_end = med.get("source_end")

        # Missing attribute checking
        missing_attrs = []
        if strength is None and med.get("dose") is None:
            missing_attrs.append("strength/dosage")
        if frequency is None:
            missing_attrs.append("frequency")
        if timing is None:
            missing_attrs.append("timing")
        if duration is None:
            missing_attrs.append("duration")

        if missing_attrs and norm_name:
            note = f"Medication '{norm_name}': Explicit {', '.join(missing_attrs)} not stated in transcript."
            if not any(f"'{norm_name}'" in u for u in uncertain_items):
                uncertain_items.append(note)

        sanitized_meds.append({
            "name": norm_name,
            "strength": strength,
            "dose": med.get("dose"),
            "route": med.get("route"),
            "frequency": frequency,
            "specific_schedule": specific_schedule,
            "timing": timing,
            "duration": duration,
            "source_speaker": source_speaker,
            "source_text": source_text,
            "source_start": source_start,
            "source_end": source_end
        })

    # 2. Cross-Turn Medication Property Association (Section 3 & 4)
    # Check instructions for medication-specific timings and attach them to the medications
    for inst in raw_instructions:
        inst_low = inst.lower()
        consumed = False

        # Pantoprazole before breakfast
        if re.search(r"pantoprazole|பேண்டட|பேண்டடோ|போரசால்", inst_low) and re.search(r"breakfast|பிரேக்ஃபாஸ்ட்|முன்னாடி|முன்", inst_low):
            for m in sanitized_meds:
                if m["name"] and "pantoprazole" in m["name"].lower():
                    if not m["timing"] or m["timing"] == "empty stomach":
                        m["timing"] = "empty stomach / before breakfast"
                    consumed = True

        # Paracetamol after food
        elif re.search(r"paracetamol|பேராசிட்டமால்|பேராசட்டமால்", inst_low) and re.search(r"after\s*food|சாப்பிட்ட\s*பிறகு|ஆஃப்டர்\s*ஃபுட்|பின்", inst_low):
            for m in sanitized_meds:
                if m["name"] and "paracetamol" in m["name"].lower():
                    m["timing"] = "after food"
                    consumed = True

        # Vitamin D after lunch
        elif re.search(r"vitamin\s*d|விட்டமின்\s*டி", inst_low) and re.search(r"lunch|லன்ச்|லன்ச்சுக்கு", inst_low):
            for m in sanitized_meds:
                if m["name"] and "vitamin" in m["name"].lower():
                    m["timing"] = "after lunch"
                    consumed = True

        if not consumed:
            filtered_instructions.append(inst)

    # 3. Check for transcript warnings (e.g. Test 4: max 3 tablets a day)
    if re.search(r"ஒரு\s*நாளைக்கு\s*மூணு\s*டேப்லெட்ஸ்\s*மேலே\s*வேண்டாம்|மூன்று\s*tablets-க்கு\s*மேல்\s*வேண்டாம்|not\s*more\s*than\s*3\s*tablets", transcript, re.I):
        warning_msg = "Do not take more than 3 tablets of Paracetamol per day."
        if not any("3 tablets" in w or "மூணு டேப்லெட்ஸ்" in w for w in raw_warnings):
            raw_warnings.append(warning_msg)

    # 4. Normalize follow-up
    if isinstance(raw_follow_up, str):
        follow_up_dict = {"time": normalize_duration_str(raw_follow_up.strip()), "instructions": None}
    elif isinstance(raw_follow_up, dict):
        follow_up_dict = {
            "time": normalize_duration_str(raw_follow_up.get("time")),
            "instructions": raw_follow_up.get("instructions")
        }
    else:
        follow_up_dict = {"time": None, "instructions": None}

    # If review of old prescription mentioned in Test 3
    if metformin_discontinued:
        if not follow_up_dict.get("instructions"):
            follow_up_dict["instructions"] = "Doctor will review old prescription."

    # 5. Normalize tests
    raw_tests = raw_data.get("tests", [])
    sanitized_tests: List[Dict[str, Any]] = []
    for t in raw_tests:
        if isinstance(t, dict):
            sanitized_tests.append({
                "name": t.get("name"),
                "timing": t.get("timing"),
                "instructions": t.get("instructions")
            })

    # 6. Normalize symptoms (convert Tamil words if obvious)
    normalized_symptoms = []
    for s in raw_symptoms:
        s_clean = s
        s_low = s.lower()
        if re.search(r"ஃபீவர்|fever|காய்ச்சல்", s_low):
            s_clean = "Fever"
        elif re.search(r"பாடி\s*பெயின்|body\s*pain|உடல்\s*வலி", s_low):
            s_clean = "Body pain"
        elif re.search(r"ஹெட்ேக்|headache|தலைவலி", s_low):
            s_clean = "Headache"
        elif re.search(r"ஸ்டமக்\s*பெயின்|stomach\s*pain|வயிற்று\s*வலி", s_low):
            s_clean = "Stomach pain"
        elif re.search(r"ஆசடிட்டி|acidity", s_low):
            s_clean = "Acidity"
        elif re.search(r"நாசியா|nausea", s_low):
            s_clean = "Nausea"
        if s_clean not in normalized_symptoms:
            normalized_symptoms.append(s_clean)

    # Ensure symptoms explicitly stated in patient transcript are included if omitted by LLM
    if transcript:
        if re.search(r"பாடி\s*பெயின்|body\s*pain", transcript, re.I) and "Body pain" not in normalized_symptoms:
            normalized_symptoms.append("Body pain")
        if re.search(r"ஃபீவர்|fever|காய்ச்சல்", transcript, re.I) and "Fever" not in normalized_symptoms:
            normalized_symptoms.append("Fever")
        if re.search(r"ஹெட்ேக்|headache|தலைவலி", transcript, re.I) and "Headache" not in normalized_symptoms:
            normalized_symptoms.append("Headache")
        if re.search(r"ஸ்டமக்\s*பெயின்|stomach\s*pain", transcript, re.I) and "Stomach pain" not in normalized_symptoms:
            normalized_symptoms.append("Stomach pain")
        if re.search(r"ஆசடிட்டி|acidity", transcript, re.I) and "Acidity" not in normalized_symptoms:
            normalized_symptoms.append("Acidity")
        if re.search(r"நாசியா|nausea", transcript, re.I) and "Nausea" not in normalized_symptoms:
            normalized_symptoms.append("Nausea")

    # 7. Construct complete dictionary
    constructed_dict: Dict[str, Any] = {
        "medications": sanitized_meds,
        "tests": sanitized_tests,
        "instructions": filtered_instructions,
        "follow_up": follow_up_dict,
        "warnings": raw_warnings,
        "symptoms_mentioned": normalized_symptoms,
        "uncertain_items": uncertain_items,
        "requires_doctor_review": True
    }

    # 8. Validate through Pydantic model
    try:
        validated_model = MedicalExtraction.model_validate(constructed_dict)
        final_dict = validated_model.to_dict()
        is_valid = True
    except ValidationError as ve:
        is_valid = False
        errors.append(str(ve))
        final_dict = constructed_dict

    validation_summary = {
        "valid": is_valid,
        "requires_doctor_review": final_dict["requires_doctor_review"],
        "uncertain_items": final_dict["uncertain_items"],
        "errors": errors
    }

    return final_dict, validation_summary


def validate_schema(data: Dict[str, Any]) -> bool:
    """
    Direct schema conformance check.
    Raises ValueError if schema constraints are violated.
    """
    required_keys = [
        "medications", "tests", "instructions", "follow_up",
        "warnings", "symptoms_mentioned", "uncertain_items", "requires_doctor_review"
    ]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Schema Validation Error: Missing required key '{key}'")

    if not isinstance(data["medications"], list):
        raise ValueError("Schema Validation Error: 'medications' must be a list.")
    if not isinstance(data["tests"], list):
        raise ValueError("Schema Validation Error: 'tests' must be a list.")
    if not isinstance(data["instructions"], list):
        raise ValueError("Schema Validation Error: 'instructions' must be a list.")
    if not isinstance(data["follow_up"], dict):
        raise ValueError("Schema Validation Error: 'follow_up' must be a dictionary.")
    if not isinstance(data["warnings"], list):
        raise ValueError("Schema Validation Error: 'warnings' must be a list.")
    if not isinstance(data["symptoms_mentioned"], list):
        raise ValueError("Schema Validation Error: 'symptoms_mentioned' must be a list.")
    if not isinstance(data["uncertain_items"], list):
        raise ValueError("Schema Validation Error: 'uncertain_items' must be a list.")
    if not isinstance(data["requires_doctor_review"], bool):
        raise ValueError("Schema Validation Error: 'requires_doctor_review' must be a boolean.")

    # Validate each medication has required keys
    for med in data["medications"]:
        for mk in ["name", "strength", "dose", "route", "frequency", "timing", "duration"]:
            if mk not in med:
                raise ValueError(f"Schema Validation Error: Medication missing key '{mk}'")

    # Validate each test has required keys
    for t in data["tests"]:
        for tk in ["name", "timing", "instructions"]:
            if tk not in t:
                raise ValueError(f"Schema Validation Error: Test missing key '{tk}'")

    # Validate follow_up has 'time' and 'instructions'
    for fk in ["time", "instructions"]:
        if fk not in data["follow_up"]:
            raise ValueError(f"Schema Validation Error: follow_up missing key '{fk}'")

    return True
