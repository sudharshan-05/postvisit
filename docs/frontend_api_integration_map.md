# PostVisit AI — Frontend API Integration Map
**Source of Truth:** Verified FastAPI Backend Implementation (`api/` and `src/`)  
**Date:** October 4, 2026  
**Security Standard:** Supabase JWT Bearer Token (`HS256`) or Sandbox Test Mode Header

---

## 1. Authentication & System Health

### 1.1 `GET /health`
- **Method:** `GET`
- **Sync/Async:** Synchronous
- **Auth Required:** None (Public)
- **Authorized Role:** Any
- **Request Body:** None
- **Response Structure (200 OK):**
  ```json
  {
    "status": "ok",
    "service": "PostVisit AI API",
    "version": "1.0.0"
  }
  ```
- **Error Responses:** 500 `INTERNAL_SERVER_ERROR`

### 1.2 `GET /api/v1/auth/me`
- **Method:** `GET`
- **Sync/Async:** Synchronous
- **Auth Required:** `Authorization: Bearer <token>` (or `X-User-Role` / `X-User-Id` in `APP_ENV=test`)
- **Authorized Role:** `doctor` or `patient`
- **Request Body:** None
- **Response Structure (200 OK):**
  ```json
  {
    "user_id": "uuid-or-id",
    "name": "Dr. A. Ramanathan",
    "role": "doctor", // or "patient"
    "patient_id": "uuid-if-patient",
    "permissions": ["consultations:read", "consultations:write", ...],
    "is_test_identity": false
  }
  ```
- **Error Responses:**
  - 401 `UNAUTHORIZED` (Missing, expired, or invalid JWT)

---

## 2. Consultations & Audio Pipeline (`api/routes/consultations.py`)

### 2.1 `POST /api/v1/consultations/process` (and `/api/v1/consultations`)
- **Method:** `POST`
- **Sync/Async:** Asynchronous background workflow by default (`?sync=true` for synchronous execution)
- **Auth Required:** Doctor or authorized caller
- **Content-Type:** `multipart/form-data`
- **Request Body:**
  - `file`: Binary audio file (`.wav`, `.mp3`, `.mp4`, `.m4a`, `.flac`, `.ogg`, max 50MB)
  - `sync`: Optional query boolean (default `false`)
- **Response Structure (200 OK):**
  ```json
  {
    "consultation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "status": "queued",
    "workflow_job_id": "job-uuid",
    "filename": "encounter_tamil.wav",
    "created_at": "2026-10-04T12:00:00Z"
  }
  ```
- **Error Responses:**
  - 400 `INVALID_FILENAME` / `EMPTY_FILE`
  - 413 `FILE_TOO_LARGE`
  - 415 `UNSUPPORTED_FILE_TYPE`
  - 500 `AUDIO_PROCESSING_FAILED`

### 2.2 `GET /api/v1/consultations/{consultation_id}`
- **Method:** `GET`
- **Sync/Async:** Synchronous
- **Auth Required:** Doctor or authorized patient
- **Response Structure (200 OK):**
  ```json
  {
    "consultation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "status": "pending_doctor_review", // or "completed", "failed", "processing"
    "active_step": "doctor_review",
    "doctor_reviewed": false,
    "patient_name": "Jane Doe",
    "patient_id": "pt-101",
    "audio_metadata": { "duration": 182.5, "channels": 1 },
    "medical_data": {
      "symptoms": ["chest discomfort", "dizziness"],
      "hpi": "45-year-old male presenting with intermittent chest discomfort...",
      "vital_signs": { "blood_pressure": "130/85", "pulse": 78 },
      "medications": [
        { "name": "Metformin", "dose": "500mg", "timing": "twice daily", "notes": "After food" },
        { "name": "Atorvastatin", "dose": "20mg", "timing": "at bedtime" }
      ],
      "investigations": ["HbA1c", "ECG"],
      "recommendations": ["Low salt diet", "Regular cardio walking"],
      "follow_up": "2 weeks"
    }
  }
  ```
- **Error Responses:** 404 `CONSULTATION_NOT_FOUND`

### 2.3 `GET /api/v1/consultations/{consultation_id}/progress`
- **Method:** `GET`
- **Sync/Async:** Synchronous polling endpoint
- **Response Structure (200 OK):**
  ```json
  {
    "consultation_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "status": "processing",
    "current_stage": "clinical_extraction",
    "steps": [
      { "name": "audio_validation", "status": "completed", "elapsed_seconds": 1.2 },
      { "name": "speech_to_text", "status": "completed", "elapsed_seconds": 4.8 },
      { "name": "diarization", "status": "completed", "elapsed_seconds": 3.1 },
      { "name": "clinical_extraction", "status": "in_progress", "elapsed_seconds": 2.0 },
      { "name": "summary_generation", "status": "pending" },
      { "name": "doctor_review", "status": "pending" }
    ],
    "is_completed": false
  }
  ```

### 2.4 `POST /api/v1/consultations/{consultation_id}/review`
- **Method:** `POST`
- **Sync/Async:** Synchronous mutation
- **Auth Required:** Doctor
- **Request Body (JSON):**
  ```json
  {
    "doctor_name": "Dr. A. Ramanathan",
    "decision": "approved", // or "amended", "rejected"
    "notes": "Clinically verified. Patient educated on medication timing.",
    "corrected_medical_record": null // or modified medical JSON
  }
  ```
- **Response Structure (200 OK):**
  ```json
  {
    "consultation_id": "uuid",
    "status": "completed",
    "doctor_reviewed": true,
    "review_timestamp": "2026-10-04T12:05:00Z"
  }
  ```

---

## 3. Patient Summaries (`api/routes/summaries.py`)

### 3.1 `POST /api/v1/consultations/{consultation_id}/summaries`
- **Method:** `POST`
- **Sync/Async:** Synchronous
- **Auth Required:** Doctor or system
- **Request Body (JSON):**
  ```json
  {
    "target_language": "en", // "en" or "ta"
    "idempotency_key": "unique-client-key"
  }
  ```
- **Response (200 OK):** Detailed PatientSummaryRecord

### 3.2 `GET /api/v1/summaries/{summary_id}`
- **Method:** `GET`
- **Sync/Async:** Synchronous
- **Auth Required:** Doctor or Scoped Patient
- **Security Guard:** **Patients receive 403 FORBIDDEN if `doctor_reviewed == false`**
- **Response (200 OK):**
  ```json
  {
    "id": "sum-uuid",
    "consultation_id": "c-uuid",
    "patient_id": "pt-101",
    "language": "en",
    "doctor_reviewed": true,
    "review_decision": "approved",
    "summary_content": {
      "patient_name": "Jane Doe",
      "visit_date": "2026-10-04",
      "doctor_name": "Dr. A. Ramanathan",
      "reason_for_visit": "Routine checkup and blood sugar review",
      "diagnosis_summary": "Type 2 Diabetes Mellitus - well controlled",
      "medications_list": [
        { "name": "Metformin", "dosage": "500mg", "instructions": "Take twice daily with meals" }
      ],
      "precautions": ["Avoid skipping meals", "Keep glucose logs"],
      "follow_up": "Return in 3 months for HbA1c"
    }
  }
  ```

### 3.3 `POST /api/v1/summaries/{summary_id}/review`
- **Method:** `POST`
- **Sync/Async:** Synchronous
- **Auth Required:** Doctor
- **Request Body (JSON):**
  ```json
  {
    "doctor_name": "Dr. A. Ramanathan",
    "decision": "approved", // "approved", "rejected", "amended"
    "notes": "Reviewed and confirmed for patient release",
    "corrected_summary": null
  }
  ```

---

## 4. Doctor Portal (`api/routes/doctor.py`)

### 4.1 `GET /api/v1/doctor/consultations` (and `/api/v1/doctor/pending-reviews`)
- **Method:** `GET`
- **Auth Required:** Doctor
- **Query Params:** `filter_type` ("all", "pending_review", "completed", "needs_attention"), `start_date`, `end_date`, `patient_id`, `page`, `page_size`
- **Response Structure (200 OK):**
  ```json
  {
    "consultations": [
      {
        "id": "c-uuid",
        "patient_id": "PT-89241",
        "patient_name": "Ananya Patel",
        "created_at": "2026-10-04T09:30:00Z",
        "status": "awaiting_review",
        "language": "ta",
        "duration_seconds": 145,
        "needs_attention": false
      }
    ],
    "total": 42,
    "page": 1,
    "page_size": 20
  }
  ```

### 4.2 `GET /api/v1/doctor/patient/{patient_id}/overview`
- **Method:** `GET`
- **Auth Required:** Doctor
- **Response Structure (200 OK):** Complete clinical overview including last visit, visit history, symptoms, medications, lab reports, guideline findings, and audit trail.

### 4.3 `GET /api/v1/doctor/consultations/{consultation_id}/quick-summary`
- **Method:** `GET`
- **Auth Required:** Doctor
- **Response Structure (200 OK):** Compact organization quick summary.

### 4.4 `GET /api/v1/doctor/lab-reports` & `POST /api/v1/doctor/lab-reports/{report_id}/review`
- **Method:** `GET` / `POST`
- **Auth Required:** Doctor
- **Review Request Body:**
  ```json
  {
    "decision": "verified", // "verified", "rejected", "clarification_needed"
    "verified_value": "7.2",
    "verified_unit": "%",
    "doctor_notes": "Consistent with lab report printout",
    "clarification_request": null
  }
  ```

### 4.5 `GET /api/v1/doctor/consultations/{consultation_id}/guidelines` & Review
- **Method:** `GET` / `POST`
- **Auth Required:** Doctor
- **Review Finding Request Body:**
  ```json
  {
    "decision": "relevant", // "relevant", "not_relevant", "review_later", "add_note"
    "doctor_notes": "Statin indicated based on RSSDI 2024 guidelines"
  }
  ```

### 4.6 `POST /api/v1/doctor/consultations/{consultation_id}/ask` (and `/ask-ai`)
- **Method:** `POST`
- **Auth Required:** Doctor
- **Request Body (JSON):**
  ```json
  {
    "consultation_id": "c-uuid",
    "query": "Explain documented follow-up instructions and statin justification",
    "context_type": "all" // "symptoms", "medications", "guidelines", "all"
  }
  ```
- **Response Structure (200 OK):**
  ```json
  {
    "answer": "The patient was prescribed Atorvastatin 20mg based on lipid risk...",
    "source_data_used": ["medications", "hpi"],
    "ai_summary_used": "Current consultation summary v1",
    "guideline_evidence": "RSSDI 2024 Dyslipidemia recommendations",
    "ai_interpretation": "Patient has elevated cardiovascular risk..."
  }
  ```

### 4.7 `POST /api/v1/doctor/consultations/{consultation_id}/voice-note/transcribe` & `/confirm`
- **Method:** `POST`
- **Auth Required:** Doctor
- **Confirm Request Body:**
  ```json
  {
    "draft_id": "draft-uuid",
    "consultation_id": "c-uuid",
    "final_note_text": "Doctor's confirmed note text",
    "category": "clinical_observation",
    "is_confirmed": true
  }
  ```

### 4.8 `GET /api/v1/doctor/consultations/{consultation_id}/timeline` & `/audit-trail`
- **Method:** `GET`
- **Auth Required:** Doctor
- **Returns:** Truthful 10-step pipeline timeline and immutable append-only audit entries.

---

## 5. Patient Portal (`api/routes/patient.py`)

### 5.1 `GET /api/v1/patient/overview` (and `/dashboard`)
- **Method:** `GET`
- **Auth Required:** Patient (strictly scoped to `caller_id == sub`)
- **Response Structure (200 OK):**
  ```json
  {
    "patient_id": "pt-101",
    "patient_name": "Ananya Patel",
    "last_visit_date": "2026-10-04",
    "last_consultation_id": "c-uuid",
    "summary_status": "approved",
    "health_trends": [
      { "date": "2026-08-01", "systolic_bp": 135, "diastolic_bp": 88, "fasting_glucose": 142, "weight_kg": 68.5 },
      { "date": "2026-10-04", "systolic_bp": 124, "diastolic_bp": 80, "fasting_glucose": 118, "weight_kg": 67.2 }
    ],
    "active_medications_count": 3,
    "pending_lab_reports_count": 1
  }
  ```

### 5.2 `GET /api/v1/patient/last-visit`
- **Method:** `GET`
- **Auth Required:** Patient
- **Security:** Returns 403 Forbidden if consultation summary is unreviewed/unapproved.
- **Response Structure (200 OK):** 14 clinical sections with clear patient-friendly explanations.

### 5.3 `GET /api/v1/patient/history`
- **Method:** `GET`
- **Auth Required:** Patient
- **Query Params:** `page`, `page_size`, `status_filter`
- **Response:** Chronological visit timeline.

### 5.4 `GET /api/v1/patient/recovery-plan` & `POST /api/v1/patient/recovery-plan/toggle`
- **Method:** `GET` / `POST`
- **Auth Required:** Patient
- **Toggle Body:**
  ```json
  {
    "consultation_id": "c-uuid",
    "task_key": "take_morning_metformin",
    "completed": true,
    "notes": "Taken with breakfast"
  }
  ```

### 5.5 `GET /api/v1/patient/medications`
- **Method:** `GET`
- **Auth Required:** Patient
- **Response:** Prescribed medications with dosage, timing, instructions, and warnings.

### 5.6 `GET /api/v1/patient/lab-reports` & `POST /api/v1/patient/lab-reports/upload` & `/manual`
- **Method:** `GET` / `POST`
- **Auth Required:** Patient
- **Upload:** `multipart/form-data` with `file`, `test_name`, `report_date`, `facility_name`, `patient_notes`.
- **Manual Body:**
  ```json
  {
    "test_name": "Fasting Blood Glucose",
    "test_value": "118",
    "unit": "mg/dL",
    "report_date": "2026-10-03",
    "facility_name": "Dr. Lal PathLabs",
    "patient_notes": "Done after 10 hours overnight fasting"
  }
  ```

### 5.7 `POST /api/v1/patient/chat` (and `/ask-ai`) & `GET /api/v1/patient/chat/history`
- **Method:** `POST` / `GET`
- **Auth Required:** Patient
- **Request Body (JSON):**
  ```json
  {
    "message": "When should I take my morning medicine?",
    "consultation_id": "c-uuid", // optional
    "context_type": "medications", // optional
    "language": "en" // "en" or "ta"
  }
  ```
- **Response Structure (200 OK):**
  ```json
  {
    "answer": "Your doctor prescribed Metformin 500mg to be taken twice daily with meals...",
    "session_id": "sess-uuid",
    "safety_disclaimer": "This AI assistant provides information from your approved consultation...",
    "grounded_sources": ["approved_medications"]
  }
  ```

### 5.8 `POST /api/v1/patient/voice-transcribe` (and `/voice-note`)
- **Method:** `POST`
- **Auth Required:** Patient
- **Content-Type:** `multipart/form-data` with `audio` blob, `language` ("auto", "ta", "en").
- **Response (200 OK):**
  ```json
  {
    "transcript": "நான் எப்போது மாத்திரை சாப்பிட வேண்டும்?",
    "language_detected": "ta",
    "confidence": 0.94
  }
  ```

---

## 6. Medical Guidelines (`api/routes/guidelines.py`)

### 6.1 `GET /api/v1/guidelines/search`
- **Method:** `GET`
- **Auth Required:** Authenticated user
- **Query Params:** `q` (search keywords like "diabetes", "metformin", "hypertension")
- **Response (200 OK):** List of matching Indian clinical guidelines (ICMR, RSSDI, CSI, API) with XSS sanitization.

### 6.2 `GET /api/v1/guidelines/{guideline_id}`
- **Method:** `GET`
- **Auth Required:** Authenticated user
- **Response (200 OK):** Full guideline details or 404.
