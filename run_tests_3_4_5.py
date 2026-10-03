import sys
import json
import time
from pathlib import Path

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.postvisit_pipeline import run_pipeline

test_files = ["test3.mp4", "test4.mp4", "test5.mp4"]
results = {}

print("=" * 80)
print("RUNNING POSTVISIT AI PIPELINE ON TEST3, TEST4, TEST5")
print("=" * 80)

for media_name in test_files:
    media_path = PROJECT_ROOT / media_name
    if not media_path.exists():
        print(f"[ERROR] Media file not found: {media_path}")
        continue

    print(f"\n>>> PROCESSING: {media_name} <<<")
    start_t = time.time()
    result = run_pipeline(str(media_path), language="ta", strategy="ctc")
    elapsed = time.time() - start_t

    stem = Path(media_name).stem
    out_file = PROJECT_ROOT / f"{stem}_medical.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result["medical_information"], f, ensure_ascii=False, indent=2)

    full_out_file = PROJECT_ROOT / f"{stem}_full_output.json"
    with open(full_out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    results[media_name] = result
    print(f"[SUCCESS] Saved medical JSON to: {out_file.name}")
    print(f"[SUCCESS] Saved full output to: {full_out_file.name}")
    print(f"[TIMING] Completed {media_name} in {elapsed:.2f} s")

# ---------------------------------------------------------------------------
# Automated Verification & Evaluation Audit Report (Section 14)
# ---------------------------------------------------------------------------
t3 = results.get("test3.mp4", {}).get("medical_information", {})
t4 = results.get("test4.mp4", {}).get("medical_information", {})
t5 = results.get("test5.mp4", {}).get("medical_information", {})

# Test 3 evaluations:
# Paracetamol prescribed by Doctor for 3 days night after food; Metformin not active
t3_meds = t3.get("medications", [])
t3_has_para = any(m.get("name") == "Paracetamol" for m in t3_meds)
t3_no_metformin = not any(m.get("name") and "metformin" in m.get("name").lower() for m in t3_meds)
t3_spk_pass = all(m.get("source_speaker") == "Doctor" for m in t3_meds) if t3_meds else False
t3_norm_pass = any(m.get("strength") == "650 mg" and m.get("duration") == "3 days" for m in t3_meds)
t3_assoc_pass = any(m.get("timing") == "after food" and ("night" in (m.get("specific_schedule") or [])) for m in t3_meds)
t3_halluc_pass = t3_no_metformin and len(t3_meds) == 1

# Test 4 evaluations:
# 3 medications (Pantoprazole, Paracetamol, Vitamin D), normalized, properties associated
t4_meds = t4.get("medications", [])
t4_panto = next((m for m in t4_meds if m.get("name") == "Pantoprazole"), None)
t4_para = next((m for m in t4_meds if m.get("name") == "Paracetamol"), None)
t4_vitd = next((m for m in t4_meds if m.get("name") == "Vitamin D"), None)

t4_count_pass = len(t4_meds) >= 3 and (t4_panto is not None) and (t4_para is not None) and (t4_vitd is not None)
t4_spk_pass = all(m.get("source_speaker") == "Doctor" for m in t4_meds) if t4_meds else False
t4_norm_pass = bool(
    t4_panto and t4_panto.get("strength") == "40 mg" and t4_panto.get("duration") == "30 days" and
    t4_para and t4_para.get("strength") == "500 mg" and
    t4_vitd and t4_vitd.get("duration") == "8 weeks"
)
t4_assoc_pass = bool(
    t4_panto and ("empty stomach" in (t4_panto.get("timing") or "") or "breakfast" in (t4_panto.get("timing") or "")) and
    t4_para and ("food" in (t4_para.get("timing") or "") or t4_para.get("frequency") == "as needed") and
    t4_vitd and ("lunch" in (t4_vitd.get("timing") or "") or t4_vitd.get("frequency") == "once weekly")
)
t4_dose_pass = bool(
    t4_panto and t4_panto.get("frequency") == "once daily" and
    t4_para and (t4_para.get("frequency") == "as needed" or "pain" in str(t4_para.get("timing"))) and
    t4_vitd and t4_vitd.get("frequency") == "once weekly"
)

# Test 5 evaluations:
# Symptoms (Fever, Body pain, Headache), Paracetamol twice daily 650mg 5 days, Doctor speaker, Instructions, Follow-up
t5_meds = t5.get("medications", [])
t5_symptoms = [s.lower() for s in t5.get("symptoms_mentioned", [])]
t5_symp_pass = any("fever" in s for s in t5_symptoms) and any("headache" in s for s in t5_symptoms) and any("body pain" in s for s in t5_symptoms)
t5_para = next((m for m in t5_meds if m.get("name") == "Paracetamol"), None)
t5_spk_pass = (t5_para is not None) and (t5_para.get("source_speaker") == "Doctor")
t5_med_pass = (t5_para is not None) and (t5_para.get("strength") == "650 mg")
t5_sched_pass = bool(
    t5_para and t5_para.get("frequency") == "twice daily" and
    t5_para.get("duration") == "5 days" and
    ("morning" in (t5_para.get("specific_schedule") or [])) and
    ("night" in (t5_para.get("specific_schedule") or []))
)
t5_inst_pass = len(t5.get("instructions", [])) >= 2
t5_fu_pass = bool(t5.get("follow_up", {}).get("time") and "1 week" in str(t5.get("follow_up", {}).get("time")))

print("\n" + "=" * 40)
print("POSTVISIT MEDICAL EXTRACTION TEST")
print("=" * 40)

print("\nTest 3:")
print(f"Speaker attribution:    {'PASS' if t3_spk_pass else 'FAIL'}")
print(f"Medication extraction:  {'PASS' if t3_has_para else 'FAIL'}")
print(f"Normalization:          {'PASS' if t3_norm_pass else 'FAIL'}")
print(f"Medication association: {'PASS' if t3_assoc_pass else 'FAIL'}")
print(f"Hallucination check:    {'PASS' if t3_halluc_pass else 'FAIL'}")

print("\nTest 4:")
print(f"Speaker attribution:    {'PASS' if t4_spk_pass else 'FAIL'}")
print(f"3 medications detected: {'PASS' if t4_count_pass else 'FAIL'}")
print(f"Medication association: {'PASS' if t4_assoc_pass else 'FAIL'}")
print(f"Dose/frequency/timing:  {'PASS' if t4_dose_pass else 'FAIL'}")
print(f"Normalization:          {'PASS' if t4_norm_pass else 'FAIL'}")

print("\nTest 5:")
print(f"Speaker attribution:    {'PASS' if t5_spk_pass else 'FAIL'}")
print(f"Symptoms:               {'PASS' if t5_symp_pass else 'FAIL'}")
print(f"Medication:             {'PASS' if t5_med_pass else 'FAIL'}")
print(f"Schedule:               {'PASS' if t5_sched_pass else 'FAIL'}")
print(f"Instructions:           {'PASS' if t5_inst_pass else 'FAIL'}")
print(f"Follow-up:              {'PASS' if t5_fu_pass else 'FAIL'}")

print("=" * 40)
