# PostVisit AI — Verified API Contract & Next.js Frontend Readiness Guide

## 1. Executive Summary & Architecture Overview

The PostVisit AI backend is a hardened, production-ready FastAPI application backed by Supabase PostgreSQL and Supabase Authentication. It orchestrates clinical audio processing, multilingual Tamil/English medical transcription, clinical entity extraction, patient-friendly summary generation, doctor review workflows, lab report management, and medical guideline cross-referencing.

All endpoints have been verified in sandbox testing. Authentication utilizes Supabase JWT Bearer tokens with strict signature validation (`HS256`), role-based access control (RBAC), and strict patient-level data scoping.

### Base URL
- Development / Sandbox: `http://localhost:8000`
- Production: Configurable via environment variables

---

## 2. Authentication & Authorization Standard

### 2.1 Request Headers
Every authenticated request must include the standard HTTP `Authorization` header:
```http
Authorization: Bearer <supabase_jwt_token>
```

### 2.2 Token Payload & Claims
The Supabase JWT payload must contain:
- `sub`: The UUID of the authenticated user (`user_id`).
- `email`: User's registered email address.
- `exp`: Standard expiration Unix timestamp.
- Role resolution priority:
  1. `app_metadata.role` (e.g. `"doctor"` or `"patient"`)
  2. `user_metadata.role`
  3. `role` claim

### 2.3 Role Enforcement & Status Codes
| Scenario | Response Status | Response Body Pattern |
| :--- | :--- | :--- |
| Missing or empty `Authorization` header | `401 Unauthorized` | `{"detail": "Authentication required. Missing Bearer token."}` |
| Expired or tampered JWT signature | `401 Unauthorized` | `{"detail": "Invalid or expired authentication token."}` |
| Patient accessing Doctor-only routes | `403 Forbidden` | `{"detail": "Doctor access required."}` |
| Doctor accessing Patient-scoped routes | `403 Forbidden` | `{"detail": "Patient access required."}` |
| Patient attempting to access another patient's data | `403 Forbidden` | `{"detail": "Access forbidden: Patient data isolation violation."}` |

---

## 3. Complete Verified API Endpoint Catalog

### 3.1 Authentication & System Health
| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | System health, service status, environment (`test`/`production`) |
| `GET` | `/` | Public | Welcome banner and API versioning information |
| `GET` | `/api/v1/auth/me` | Authenticated | Returns caller identity, user UUID, role, and email |

---

### 3.2 Consultations & Audio Pipeline
| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/consultations` | Doctor / Authorized | Upload audio/video (`.wav`, `.mp3`, `.mp4`, `.m4a`, `.aac`, `.webm`, `.ogg`) for clinical pipeline processing |
| `GET` | `/api/v1/consultations/{id}` | Doctor / Scoped Patient | Retrieve consultation details, stage, status, audio metadata |
| `GET` | `/api/v1/consultations/{id}/status`| Doctor / Scoped Patient | Poll processing progress and active pipeline stage |
| `GET` | `/api/v1/consultations` | Doctor | List all consultations with pagination, date filters |

**Upload Consultation Schema (`multipart/form-data`):**
- `file`: Audio file binary (required)
- `doctor_id`: UUID of attending clinician (optional, defaults to authenticated caller)
- `patient_id`: UUID of patient (optional)
- `patient_name`: String (e.g., `"Jane Doe"`)
- `patient_age`: Integer (e.g., `45`)
- `patient_gender`: String (e.g., `"female"`)
- `target_language`: String (e.g., `"ta"` or `"en"`)
- `enable_guideline_check`: Boolean string (`"true"` / `"false"`)

---

### 3.3 Clinical Summaries & Doctor Sign-Off
| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/summaries/{id}` | Doctor / Scoped Patient | Retrieve summary. **Note: Unapproved summaries are 403 Forbidden to patients** |
| `GET` | `/api/v1/summaries/consultation/{id}` | Doctor / Scoped Patient | Retrieve summary by consultation ID |
| `PUT` | `/api/v1/summaries/{id}` | Doctor | Doctor edits and approves summary. Sets `doctor_reviewed=true` |
| `POST`| `/api/v1/summaries/{id}/approve` | Doctor | Quick 1-click doctor sign-off / approval |

---

### 3.4 Doctor Portal & Dashboard
| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/doctor/dashboard` | Doctor | Doctor dashboard overview with active stats and pending reviews (Route alias: `/overview`) |
| `GET` | `/api/v1/doctor/pending-reviews` | Doctor | List consultations awaiting doctor review and sign-off (Route alias: `/consultations?status=awaiting_review`) |
| `GET` | `/api/v1/doctor/consultations` | Doctor | Filterable consultation queue (`status`, `search`, `limit`, `offset`) |
| `GET` | `/api/v1/doctor/consultations/{id}`| Doctor | Detailed consultation view including diarized transcript, extracted entities, and summary |
| `POST`| `/api/v1/doctor/consultations/{id}/approve`| Doctor | Approve consultation summary with optional clinician notes |
| `POST`| `/api/v1/doctor/voice-note` | Doctor | Doctor clinical voice dictation note upload & transcription (Route alias: `/voice-transcribe`) |
| `POST`| `/api/v1/doctor/ask-ai` | Doctor | Clinician clinical copilot query (Route alias: `/chat`) |
| `GET` | `/api/v1/doctor/patients` | Doctor | Distinct patient directory with encounter counts |

---

### 3.5 Patient Portal & Dashboard
| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/patient/dashboard` | Patient | Patient personalized health dashboard (Route alias: `/overview`) |
| `GET` | `/api/v1/patient/summaries` | Patient | Approved visit summaries list (strictly filtered to caller) |
| `GET` | `/api/v1/patient/summaries/{id}` | Patient | Detailed approved visit summary with medications & precautions |
| `GET` | `/api/v1/patient/medications` | Patient | Active medication schedule and instructions |
| `GET` | `/api/v1/patient/health-trends` | Patient | Vitals, HbA1c, and health tracking trends (Route alias: `/trends`) |
| `POST`| `/api/v1/patient/ask-ai` | Patient | Patient AI question query (`{"message": "..."}` or `{"question": "..."}`) |
| `POST`| `/api/v1/patient/voice-note` | Patient | Patient voice query transcription (Route alias: `/voice-transcribe`) |
| `POST`| `/api/v1/patient/lab-report` | Patient | Patient lab report upload (`multipart/form-data`) |
| `GET` | `/api/v1/patient/lab-reports` | Patient | List patient's uploaded lab reports |

---

### 3.6 Medical Guidelines
| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/guidelines/search` | Authenticated | Curated Indian guideline registry search (ICMR, RSSDI, CSI, API) with HTML sanitization |
| `GET` | `/api/v1/guidelines/stats` | Authenticated | Clinical guidelines coverage statistics |
| `GET` | `/api/v1/guidelines/{id}` | Authenticated | Detailed guideline document by ID |
| `POST`| `/api/v1/guidelines/cross-reference` | Doctor | Cross-reference consultation entities against clinical guidelines |

---

## 4. Frontend State & Integration Guidelines for Next.js

1. **Supabase Auth Hook (`@supabase/auth-helpers-nextjs` or `@supabase/ssr`):**
   - Store Supabase session and pass `session.access_token` in `Authorization: Bearer ${token}`.
   - Read `user.app_metadata.role` or `user.user_metadata.role` to route users to `/doctor` or `/patient`.
2. **Patient Data Isolation:**
   - The frontend should NOT send patient IDs in headers or query parameters for identity spoofing; the backend reliably extracts the patient UUID from the authenticated JWT `sub` claim.
3. **Optimistic Updates & Polling:**
   - When an audio consultation is uploaded via `/api/v1/consultations`, poll `/api/v1/consultations/{id}/status` until status equals `completed` or `awaiting_review`.
4. **Summary Approval Guard:**
   - Unapproved summaries will receive a `403 Forbidden` if requested by patients. In the patient UI, show "Pending Doctor Review" until approval timestamp is set.
