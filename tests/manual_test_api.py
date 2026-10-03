"""
PostVisit AI - Manual API Regression Test Script (Stage 1 + Stage 2)
Executes real consultations (test3.mp4, test4.mp4, test5.mp4) via the FastAPI HTTP layer.
Validates:
1. Stage 1: Transcript attribution, medical entity extraction, evidence preservation, normalization.
2. Stage 2: Consultation UUID assignment, storage media path, persistence in database,
   retrieval by ID (GET /consultations/{id}), and listing (GET /consultations).
"""

import sys
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
import httpx
from api.main import app


def run_api_consultation_test(
    file_path: Path,
    client: Any
) -> Tuple[int, Dict[str, Any], float]:
    """
    Submits a consultation media file to POST /api/v1/consultations/process.
    """
    start_time = time.time()
    filename = file_path.name
    endpoint = "/api/v1/consultations/process"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": (filename, file_bytes, "video/mp4")}
    resp = client.post(endpoint, files=files)
    elapsed = round(time.time() - start_time, 2)

    status_code = resp.status_code
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text}

    return status_code, data, elapsed


def retrieve_consultation_by_id(consultation_id: str, client: Any) -> Tuple[int, Dict[str, Any]]:
    """Calls GET /api/v1/consultations/{consultation_id}."""
    resp = client.get(f"/api/v1/consultations/{consultation_id}")
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {"raw_text": resp.text}


def list_consultations(client: Any) -> Tuple[int, Dict[str, Any]]:
    """Calls GET /api/v1/consultations."""
    resp = client.get("/api/v1/consultations")
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {"raw_text": resp.text}


def evaluate_test3(resp_data: Dict[str, Any]) -> Dict[str, bool]:
    """Evaluates test3.mp4 criteria."""
    checks = {
        "transcript": False,
        "doctor_attribution": False,
        "medication_extraction": False,
        "metformin_excluded_from_active": False,
        "normalization": False,
        "validation": False
    }

    transcript = resp_data.get("transcript", [])
    if transcript and any(t.get("speaker") == "Doctor" for t in transcript):
        checks["transcript"] = True

    med_record = resp_data.get("medical_record", {})
    meds = med_record.get("medications", [])
    instructions = med_record.get("instructions", [])

    # Doctor attribution
    if meds and all(m.get("source_speaker") == "Doctor" for m in meds):
        checks["doctor_attribution"] = True

    # Paracetamol extracted
    para_med = next((m for m in meds if "paracetamol" in (m.get("name") or "").lower()), None)
    if para_med:
        checks["medication_extraction"] = True
        has_650 = para_med.get("strength") == "650 mg"
        has_3days = "3 days" in (para_med.get("duration") or "")
        has_night = "night" in (para_med.get("specific_schedule") or [])
        has_after_food = "after food" in (para_med.get("timing") or "")
        if has_650 and (has_3days or has_night or has_after_food):
            checks["normalization"] = True

    # Metformin must NOT be in active medications
    metformin_in_meds = any("metformin" in (m.get("name") or "").lower() for m in meds)
    metformin_in_instr = any("metformin" in inst.lower() for inst in instructions)
    if not metformin_in_meds and metformin_in_instr:
        checks["metformin_excluded_from_active"] = True

    val = resp_data.get("validation", {})
    if val.get("status") == "valid":
        checks["validation"] = True

    return checks


def evaluate_test4(resp_data: Dict[str, Any]) -> Dict[str, bool]:
    """Evaluates test4.mp4 criteria."""
    checks = {
        "transcript": False,
        "doctor_attribution": False,
        "three_medications_detected": False,
        "dose_frequency_timing": False,
        "normalization": False,
        "validation": False
    }

    transcript = resp_data.get("transcript", [])
    if transcript and any(t.get("speaker") == "Doctor" for t in transcript):
        checks["transcript"] = True

    med_record = resp_data.get("medical_record", {})
    meds = med_record.get("medications", [])

    if len(meds) >= 3:
        checks["three_medications_detected"] = True

    if meds and all(m.get("source_speaker") == "Doctor" for m in meds):
        checks["doctor_attribution"] = True

    panto = next((m for m in meds if "panto" in (m.get("name") or "").lower()), None)
    para = next((m for m in meds if "paracetamol" in (m.get("name") or "").lower()), None)
    vitd = next((m for m in meds if "vitamin" in (m.get("name") or "").lower()), None)

    if panto and para and vitd:
        panto_ok = (panto.get("strength") == "40 mg") and ("empty stomach" in (panto.get("timing") or ""))
        vitd_ok = ("weekly" in (vitd.get("frequency") or "")) and ("after lunch" in (vitd.get("timing") or ""))
        para_ok = ("as needed" in (para.get("frequency") or "") or para.get("strength") == "500 mg")
        if panto_ok and vitd_ok and para_ok:
            checks["dose_frequency_timing"] = True
            checks["normalization"] = True

    val = resp_data.get("validation", {})
    if val.get("status") == "valid":
        checks["validation"] = True

    return checks


def evaluate_test5(resp_data: Dict[str, Any]) -> Dict[str, bool]:
    """Evaluates test5.mp4 criteria."""
    checks = {
        "transcript": False,
        "doctor_attribution": False,
        "symptoms": False,
        "medication": False,
        "schedule": False,
        "instructions": False,
        "follow_up": False,
        "validation": False
    }

    transcript = resp_data.get("transcript", [])
    if transcript and any(t.get("speaker") == "Doctor" for t in transcript):
        checks["transcript"] = True

    med_record = resp_data.get("medical_record", {})
    meds = med_record.get("medications", [])

    para_med = next((m for m in meds if "paracetamol" in (m.get("name") or "").lower()), None)
    if para_med:
        checks["medication"] = True
        if para_med.get("source_speaker") == "Doctor":
            checks["doctor_attribution"] = True

        sched = para_med.get("specific_schedule") or []
        timing = para_med.get("timing") or ""
        freq = para_med.get("frequency") or ""
        if ("morning" in sched and "night" in sched) or "twice daily" in freq or "after food" in timing:
            checks["schedule"] = True

    symptoms = [s.lower() for s in med_record.get("symptoms_mentioned", [])]
    if any("fever" in s for s in symptoms) and any("headache" in s or "body" in s for s in symptoms):
        checks["symptoms"] = True

    instructions = [i.lower() for i in med_record.get("instructions", [])]
    if any("water" in i or "fluids" in i for i in instructions) or any("rest" in i for i in instructions):
        checks["instructions"] = True

    follow_up = med_record.get("follow_up", {})
    if follow_up.get("time") or follow_up.get("instructions"):
        checks["follow_up"] = True

    val = resp_data.get("validation", {})
    if val.get("status") == "valid":
        checks["validation"] = True

    return checks


def main():
    parser = argparse.ArgumentParser(description="PostVisit AI Manual API Regression Test")
    parser.add_argument("--url", default=None, help="Base API URL (e.g. http://127.0.0.1:8000). Omit for direct TestClient.")
    parser.add_argument("--files", nargs="*", default=["test3.mp4", "test4.mp4", "test5.mp4"], help="Media files to test")
    args = parser.parse_args()

    print("========================================")
    print("POSTVISIT AI - STAGE 2 PERSISTENCE & API TEST")
    print("========================================")
    if args.url:
        print(f"Target Server: {args.url}")
        http_client = httpx.Client(base_url=args.url.rstrip('/'), timeout=300.0)
    else:
        print("Target: In-Process FastAPI TestClient")
        http_client = TestClient(app)

    print(f"Test Files:    {args.files}")
    print("========================================\n")

    consultation_ids = []

    try:
        for fname in args.files:
            fpath = PROJECT_ROOT / fname
            if not fpath.exists():
                print(f"[SKIP] File not found: {fpath}")
                continue

            print(f"--- Running API test for: {fname} ---")
            status_code, data, elapsed = run_api_consultation_test(fpath, client=http_client)
            pipeline_status = data.get("status", "failed")
            cid = data.get("consultation_id")
            storage_path = data.get("media_storage_path")

            if cid:
                consultation_ids.append(cid)

            # Stage 1 clinical checks
            if "test3" in fname:
                checks = evaluate_test3(data)
            elif "test4" in fname:
                checks = evaluate_test4(data)
            elif "test5" in fname:
                checks = evaluate_test5(data)
            else:
                checks = {"response_ok": status_code == 200}

            # Stage 2 persistence checks
            persistence_checks = {
                "consultation_id_assigned": cid is not None,
                "media_storage_path": storage_path is not None,
                "retrieval_by_id": False,
                "listing_includes_record": False
            }

            if cid:
                # Test GET /consultations/{id}
                get_code, get_data = retrieve_consultation_by_id(cid, client=http_client)
                if get_code == 200 and get_data.get("consultation_id") == cid and get_data.get("status") == "completed":
                    persistence_checks["retrieval_by_id"] = True

                # Test GET /consultations
                list_code, list_data = list_consultations(client=http_client)
                if list_code == 200 and any(item.get("consultation_id") == cid for item in list_data.get("items", [])):
                    persistence_checks["listing_includes_record"] = True

            # Print per-file report
            print("========================================")
            print("POSTVISIT API TEST")
            print("========================================")
            print(f"File:            {fname}")
            print(f"HTTP Status:     {status_code}")
            print(f"Pipeline Status: {pipeline_status}")
            print(f"Consultation ID: {cid}")
            print(f"Storage Path:    {storage_path}")
            print(f"Processing Time: {elapsed:.2f}s\n")

            print("--- Stage 1 Clinical Checks ---")
            for check_name, passed in checks.items():
                display_name = check_name.replace("_", " ").title()
                print(f"{display_name:<28}: {'PASS' if passed else 'FAIL'}")

            print("\n--- Stage 2 Persistence Checks ---")
            for check_name, passed in persistence_checks.items():
                display_name = check_name.replace("_", " ").title()
                print(f"{display_name:<28}: {'PASS' if passed else 'FAIL'}")

            print("========================================\n")

            # Save resulting response JSON
            out_file = PROJECT_ROOT / f"api_result_{Path(fname).stem}.json"
            with open(out_file, "w", encoding="utf-8") as out_f:
                json.dump(data, out_f, ensure_ascii=False, indent=2)
            print(f"Saved response payload to: {out_file}\n")

        # Global multi-consultation assertion
        print("========================================")
        print("STAGE 2 MULTI-CONSULTATION SUMMARY")
        print("========================================")
        print(f"Total Consultations Processed: {len(consultation_ids)}")
        all_unique = len(consultation_ids) == len(set(consultation_ids)) and len(consultation_ids) > 0
        print(f"Unique Consultation UUIDs:     {'PASS' if all_unique else 'FAIL'} ({consultation_ids})")
        print("========================================\n")

    finally:
        if hasattr(http_client, "close"):
            http_client.close()


if __name__ == "__main__":
    main()
