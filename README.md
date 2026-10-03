# PostVisit AI — Clinical Consultation AI Platform

Clinical consultation speech recognition, speaker diarization, structured medical information extraction, and persistent cloud consultation memory for multilingual healthcare.

---

## 1. Project Stages Overview

* **Stage 1 (Complete):** Core AI Pipeline & FastAPI REST API
  * Audio extraction and peak normalization (MP3, MP4, WAV, FLAC, OGG, M4A).
  * Acoustic turn segmentation and MFCC Gaussian KL diarization.
  * IndicConformer ASR for Indian languages (Tamil).
  * Groq LLM clinical extraction with schedule binding and source turn evidence preservation.
  * Deterministic normalization and safety validation (`requires_doctor_review: true`).
  * FastAPI REST API (`/health`, `/`, `/docs`, `/api/v1/consultations/process`).

* **Stage 2 (Complete):** Supabase Cloud Persistence & Consultation Memory
  * PostgreSQL `consultations` table with JSONB storage for transcripts, medical records, and validation.
  * Private Supabase Storage bucket (`postvisit-media`) for immutable consultation recordings.
  * Unique consultation UUID generation (`id`) establishing correlation across storage, database, and API.
  * Consultation retrieval endpoint: `GET /api/v1/consultations/{consultation_id}`.
  * Consultation collection listing: `GET /api/v1/consultations`.
  * Failure state tracking (`status='failed'` with safe `error_code` and `error_message`).
  * Row Level Security (RLS) enabled on `public.consultations`.
  * Dedicated `ConsultationRepository` with service-role security and local offline in-memory fallback.

---

## 2. System Architecture

```text
                     CLIENT / FRONTEND
                            │
                            ▼
                    ┌───────────────┐
                    │ FastAPI Layer │ (api/main.py)
                    └───┬───┬───┬───┘
                        │   │   │
        ┌───────────────┘   │   └───────────────┐
        ▼                   ▼                   ▼
    GET /health      GET /consultations   POST /consultations/process
    GET /docs        GET /consultations/{id}    │
                            │                   ▼
                            │          ┌──────────────────────┐
                            │          │ Consultation Service │ (api/services/)
                            │          └──────────┬───────────┘
                            │                     │
                            │         ┌───────────┴───────────┐
                            │         ▼                       ▼
                            │   Supabase Storage        Pipeline Service
                            │   (postvisit-media)      (src/postvisit_pipeline.py)
                            │   original audio/video          │
                            │                                 ▼
                            │                           Audio Normalization
                            │                                 ▼
                            │                           Acoustic Diarization
                            │                                 ▼
                            │                           IndicConformer ASR
                            │                                 ▼
                            │                           Groq Clinical LLM
                            │                                 ▼
                            │                           Safety Normalizer
                            │                                 │
                            └────────────────┐                │
                                             ▼                ▼
                                      ┌──────────────────────────────┐
                                      │ Supabase Database            │
                                      │ (public.consultations table) │
                                      │  - transcript (jsonb)        │
                                      │  - medical_record (jsonb)    │
                                      │  - validation_result (jsonb) │
                                      └──────────────────────────────┘
```

---

## 3. Installation & Setup

### Prerequisites
* Python 3.11 (64-bit)
* Windows, Linux, or macOS

### 1. Clone & Activate Virtual Environment
```bash
python -m venv venv
```

**Windows:**
```powershell
.\venv\Scripts\activate
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 4. Environment Configuration

Copy the example template to `.env`:
```bash
cp .env.example .env
```

Configure your `.env` file:
```env
# Groq LLM Configuration
GROQ_API_KEY=your_groq_api_key_here
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
LLM_API_KEY=your_groq_api_key_here

# Supabase Persistence (Stage 2)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_secret_key
SUPABASE_STORAGE_BUCKET=postvisit-media

# API & Upload Limits
MAX_UPLOAD_SIZE_MB=100
API_VERSION=1.0.0
```

> **Security Guardrail:** The `SUPABASE_SERVICE_ROLE_KEY` has elevated admin privileges and must remain strictly server-side. It is never exposed in API responses or delivered to frontend clients. `.env` is ignored by git.

---

## 5. Supabase SQL Migration

Run the provided migration in the Supabase SQL Editor:
```sql
-- File: supabase/migrations/001_create_consultations.sql
```

The migration automatically creates:
* `public.consultations` table with JSONB columns.
* Indexes on `status` and `created_at desc`.
* Row Level Security (RLS) enabled.
* Automated `updated_at` trigger function.

---

## 6. Starting the FastAPI Backend

Run the server with Uvicorn:
```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive documentation:
* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 7. API Endpoints Reference

### 1. Process & Persist Consultation
```http
POST /api/v1/consultations/process
Content-Type: multipart/form-data
```
**Request Form Data:** `file`: UploadFile (`.wav`, `.mp3`, `.mp4`, `.m4a`, `.flac`, `.ogg`)

**Response:**
```json
{
  "status": "completed",
  "consultation_id": "f97e66a2-824e-4a27-b901-be39fe10866b",
  "media_storage_path": "consultations/f97e66a2-824e-4a27-b901-be39fe10866b/original.mp4",
  "input": {
    "filename": "test5.mp4",
    "media_type": "video/mp4",
    "duration_seconds": 28.48
  },
  "transcript": [
    {
      "start": 0.57,
      "end": 8.38,
      "speaker": "Patient",
      "text": "டாக்டர் எனக்கு ஒரு த்ரீ டேஸாக ஃபீவர் இருக்குது..."
    },
    {
      "start": 9.81,
      "end": 17.32,
      "speaker": "Doctor",
      "text": "ஓகே கவலைப்பட வேண்டாம் பேராசிட்டமால் சிக்ஸ் ஃபிஃப்டி எம்ஜி..."
    }
  ],
  "medical_record": {
    "medications": [
      {
        "name": "Paracetamol",
        "strength": "650 mg",
        "dose": "1 tablet",
        "route": "oral",
        "frequency": "twice daily",
        "specific_schedule": ["morning", "night"],
        "timing": "after food",
        "duration": "5 days",
        "source_speaker": "Doctor",
        "source_text": "பேராசிட்டமால் சிக்ஸ் ஃபிஃப்டி எம்ஜி...",
        "source_start": 9.0,
        "source_end": 18.0
      }
    ],
    "instructions": ["Drink plenty of water", "Take proper rest"],
    "follow_up": {"time": "1 week", "instructions": "Come for follow-up"},
    "symptoms_mentioned": ["Fever", "Body pain", "Headache"],
    "requires_doctor_review": true
  },
  "validation": {
    "status": "valid",
    "errors": [],
    "warnings": []
  }
}
```

### 2. Retrieve Consultation by UUID
```http
GET /api/v1/consultations/{consultation_id}
```
**Response (200 OK):** Returns full consultation detail matching the structure above.

### 3. List Consultations
```http
GET /api/v1/consultations?limit=50&offset=0
```
**Response (200 OK):**
```json
{
  "items": [
    {
      "consultation_id": "f97e66a2-824e-4a27-b901-be39fe10866b",
      "status": "completed",
      "original_filename": "test5.mp4",
      "media_type": "video/mp4",
      "duration_seconds": 28.48,
      "created_at": "2026-09-29T21:39:27.123456+00:00",
      "updated_at": "2026-09-29T21:39:38.654321+00:00"
    }
  ],
  "total": 1
}
```

---

## 8. Testing & Verification

### Run Automated Unit & Persistence Tests (Pytest)
```bash
python -m pytest tests/test_health.py tests/test_consultation_api.py tests/test_consultation_persistence.py -v
```

### Run Stage 2 End-to-End Regression Suite (test3, test4, test5)
```bash
python tests/manual_test_api.py
```

### Direct CLI Verification (Backwards Compatibility)
```bash
python src/postvisit_pipeline.py test5.mp4
```
