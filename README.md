# PostVisit AI — Clinical Consultation AI & Care Continuity Platform

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.2-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%20%26%20Storage-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![Groq](https://img.shields.io/badge/Groq-Fast%20Inference-F05A28)](https://groq.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red)](#)

> **PostVisit AI** is an intelligent clinical consultation speech-to-record platform tailored for multilingual healthcare. It captures doctor-patient spoken dialogues (supporting Indian languages like Tamil and code-switched English), performs speaker diarization and automated speech recognition (ASR), extracts structured electronic health records (EHR) with strict provenance, enforces human-in-the-loop doctor verification, and delivers bilingual, safety-gated discharge summaries and grounded care plans to patients.

---

## Table of Contents

- [1. Executive Overview](#1-executive-overview)
- [2. What We Have Built](#2-what-we-have-built)
  - [2.1 Acoustic Audio & Speech Processing Pipeline](#21-acoustic-audio--speech-processing-pipeline)
  - [2.2 Clinical Information Extraction & Safety Guardrails](#22-clinical-information-extraction--safety-guardrails)
  - [2.3 Hybrid Persistence & Secure Storage Architecture](#23-hybrid-persistence--secure-storage-architecture)
  - [2.4 Clinical Verification & Doctor-Gated Release Workflow](#24-clinical-verification--doctor-gated-release-workflow)
  - [2.5 Multimodal Lab Report OCR Service](#25-multimodal-lab-report-ocr-service)
  - [2.6 Grounded Patient AI Care Assistant](#26-grounded-patient-ai-care-assistant)
  - [2.7 Modern Next.js Web Portals (Doctor & Patient)](#27-modern-nextjs-web-portals-doctor--patient)
  - [2.8 End-to-End Automated Test & Security Suite](#28-end-to-end-automated-test--security-suite)
- [3. How the System Works](#3-how-the-system-works)
  - [3.1 End-to-End Processing Architecture](#31-end-to-end-processing-architecture)
  - [3.2 Consultation Review & Gated Release Lifecycle](#32-consultation-review--gated-release-lifecycle)
  - [3.3 Lab OCR & Clinical Verification Pipeline](#33-lab-ocr--clinical-verification-pipeline)
  - [3.4 Grounded Patient AI Copilot Logic](#34-grounded-patient-ai-copilot-logic)
- [4. Technology Stack](#4-technology-stack)
- [5. Project Directory Structure](#5-project-directory-structure)
- [6. Installation & Setup Guide](#6-installation--setup-guide)
  - [6.1 Prerequisites](#61-prerequisites)
  - [6.2 Backend Installation](#62-backend-installation)
  - [6.3 Frontend Installation](#63-frontend-installation)
  - [6.4 Supabase Database Migration](#64-supabase-database-migration)
  - [6.5 Running Locally](#65-running-locally)
- [7. Verification & Testing](#7-verification--testing)
- [8. What We Are Yet to Work On (Future Roadmap)](#8-what-we-are-yet-to-work-on-future-roadmap)
- [9. Security, Privacy & Compliance](#9-security-privacy--compliance)

---

## 1. Executive Overview

Clinical consultations in outpatient departments (OPDs) across India and emerging economies suffer from severe communication breakdowns:
1. **High Patient Volume & Time Constraints:** Physicians have minutes per consultation, leading to handwritten, illegible notes or omitted verbal explanations.
2. **Multilingual & Code-Switching Complexity:** Encounters frequently blend local languages (e.g., Tamil) with English medical terminology ("ஃபீவர்", "டேப்லெட்", "சாப்பாட்டுக்கு அப்புறம்").
3. **Discharge Comprehension Gaps:** Patients often leave clinics unsure of medication schedules, dietary restrictions, or critical warning signs.
4. **Safety Risks in Unchecked AI:** Generic generative AI risks hallucinating medication dosages or issuing inappropriate medical recommendations directly to patients.

**PostVisit AI solves this by introducing a clinically grounded, doctor-supervised intelligence loop:**
- Ambiently transcribes and diarizes the clinical dialogue into Doctor and Patient speakers.
- Extracts structured clinical entities (symptoms, vitals, prescriptions, lab tests, follow-up timelines).
- **Mandates Human-in-the-Loop Doctor Review:** Patient discharge summaries remain strictly locked (`403 Forbidden`) until the attending clinician explicitly validates or amends the extracted record.
- Empowers patients with a personalized, bilingual portal featuring interactive recovery checklists, medication schedules, lab report OCR verification, and a safe, grounded AI assistant that strictly refuses dosage tampering.

---

## 2. What We Have Built

### 2.1 Acoustic Audio & Speech Processing Pipeline
- **Broad Format Support:** Ingests `.wav`, `.mp3`, `.mp4`, `.m4a`, `.flac`, and `.ogg` files up to 100MB.
- **Audio Extraction & Peak Normalization:** Strips video streams, converts audio to mono 16kHz standard PCM, and applies loudness normalization.
- **Speaker Diarization:** Segment acoustic turns using energy-based voice activity detection (VAD) and MFCC Gaussian Kullback-Leibler divergence clustering to separate clinician from patient dialogue.
- **Multilingual Indic ASR:** Integrated IndicConformer models fine-tuned on conversational Indian speech, accurately processing Tamil phonetic tokens alongside English medical loanwords.

### 2.2 Clinical Information Extraction & Safety Guardrails
- **LLM Medical Extraction Engine:** High-throughput inference via Groq (`Qwen 2.5 32B/72B` and `Llama 3.3 70B`) running structured prompts designed for clinical fact extraction.
- **Schedule Binding & Food Relations:** Parses nuanced dosing frequencies (`morning`, `afternoon`, `night`) and relations (`before food`, `after food`, `SOS/as needed`).
- **Turn Evidence & Provenance:** Every extracted medication and symptom maintains back-references to original audio segment timestamps and speaker turns for auditability.
- **Safety Normalizer:** Flags non-standard formulations, identifies missing durations or strengths, and sets `requires_doctor_review: true`.

### 2.3 Hybrid Persistence & Secure Storage Architecture
- **Supabase PostgreSQL Persistence:** Relational schema storing consultations, structured clinical JSONB documents, review states, vitals, and audit records.
- **Private Media Storage:** Secure Supabase Storage bucket (`postvisit-media`) housing immutable consultation audio/video recordings.
- **Resilient Offline Fallback:** Dual-mode repository architecture that falls back to thread-safe in-memory storage during network interruptions or offline test environments.
- **Row Level Security (RLS) & RBAC:** Enforced database policies and FastAPI JWT/header middleware ensuring strict isolation between doctors and patients.

### 2.4 Clinical Verification & Doctor-Gated Release Workflow
- **Transcript Editing & Speaker Reassignment:** Clinicians can correct ASR errors, swap speaker labels, and lock confirmed transcripts.
- **Side-by-Side Summary Review & Diffs:** Visual comparison between raw AI-generated clinical records and the doctor’s verified amendments.
- **Strict Patient Gating:** The patient portal and API refuse access to consultation summaries (`403 Forbidden`) until the doctor marks the review as `approved`.
- **EHR Vitals Tracking:** Supports height, weight, blood pressure, pulse, SpO2, and temperature with clinical provenance tracking (`clinician_entry` vs patient self-report).
- **Verified Age Computation:** Automatically derives patient age dynamically from verified Date of Birth (DOB) to eliminate chart discrepancies.

### 2.5 Multimodal Lab Report OCR Service
- **Multimodal Document Parsing:** Ingests lab reports (images and PDFs) to extract test parameters (e.g., Fasting Blood Glucose, HbA1c, Serum Creatinine, Lipid profiles).
- **Two-Phase Verification Flow:**
  1. *Patient Confirmation:* Extracted test values and units are presented to the patient to confirm accuracy.
  2. *Doctor Clinical Validation:* The clinician reviews the report, verifies or amends the numerical values, and incorporates them into the active EHR history.

### 2.6 Grounded Patient AI Care Assistant
- **Strictly Grounded Retrieval:** Answers patient inquiries exclusively using approved consultation records, discharge summaries, and verified medications.
- **Dosage Modification Guardrail:** Detects and hard-rejects requests to adjust prescription dosages or frequency, redirecting patients to their physician.
- **Emergency Red-Flag Detection:** Instantly identifies life-threatening symptoms (chest pain, acute breathlessness, sudden neurological deficits) and presents emergency hotlines and hospital escalation guidance.
- **Bilingual & Voice-Enabled:** Communicates fluently in both English and Tamil, featuring voice input dictation for non-tech-savvy patients.

### 2.7 Modern Next.js Web Portals (Doctor & Patient)
- Built with **Next.js 14 (App Router)**, **TypeScript**, and **Tailwind CSS**.
- **Doctor Portal Features:**
  - Real-time consultation queue with multi-state filters (`awaiting_review`, `completed`, `needs_attention`).
  - Interactive Diarized Audio Transcript player with timestamp scrubbing.
  - Side-by-side Summary Review & Comparison component with diff highlight.
  - Doctor AI Copilot (`/ask`) with Indian clinical guidelines citations (ICMR, RSSDI, CSI).
  - Voice Note Dictation with live transcription and confirmation modal.
  - 10-step consultation pipeline timeline and immutable audit trail.
- **Patient Portal Features:**
  - Personalized health overview with vital trends (blood pressure, fasting glucose, weight).
  - Doctor-reviewed discharge instructions in clear patient-friendly language.
  - Interactive daily Recovery Plan with task checkboxes (medication times, hydration, exercise).
  - Active medication cards displaying dosages, food timings, and cautionary advice.
  - Lab report uploader with OCR parameter preview.
  - Conversational AI chat with integrated Tamil audio dictation.

### 2.8 End-to-End Automated Test & Security Suite
- Comprehensive test suite (`tests/test_core_clinical_workflow.py`) validating all clinical workflows across 17 automated end-to-end test specs:
  - Audio processing, transcript editing, and doctor summary approval.
  - Unapproved summary gating security.
  - Vitals provenance attribution and DOB-calculated age consistency.
  - Lab report OCR extraction and doctor verification.
  - Grounded patient assistant responses, dosage-change rejection, and emergency response.
  - Doctor clinical copilot and guideline evidence linkage.
  - Role-Based Access Control (RBAC) and cross-patient isolation.
  - Resilient error handling for unsupported media formats and non-existent IDs.

---

## 3. How the System Works

### 3.1 End-to-End Processing Architecture

```text
                     DOCTOR-PATIENT ENCOUNTER
               (Spoken Dialogue: Tamil / English)
                               │
                               ▼
               ┌───────────────────────────────┐
               │    Client App (Next.js 14)    │
               │   Audio / Video File Upload   │
               └───────────────┬───────────────┘
                               │ POST /api/v1/consultations/process
                               ▼
               ┌───────────────────────────────┐
               │       FastAPI Gateway         │
               │   (api/routes/consultations)  │
               └───────────────┬───────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   ┌──────────────────┐               ┌──────────────────────┐
   │ Supabase Storage │               │ PostVisit AI Service │
   │ (postvisit-media)│               │ (src/postvisit_      │
   │  Raw Audio/Video │               │       pipeline.py)   │
   └──────────────────┘               └──────────┬───────────┘
                                                 │
            ┌────────────────────────────────────┼────────────────────────────────────┐
            ▼                                    ▼                                    ▼
   ┌──────────────────┐                 ┌──────────────────┐                 ┌──────────────────┐
   │  Normalization   │                 │ Speaker Diarize  │                 │ IndicConformer   │
   │  & Preprocessing │ ──────────────> │ (MFCC + KL Div)  │ ──────────────> │ ASR (Tamil / En) │
   │  16kHz Mono PCM  │                 │ Turn Segments    │                 │ Timed Transcript │
   └──────────────────┘                 └──────────────────┘                 └────────┬─────────┘
                                                                                      │
                                                                                      ▼
   ┌──────────────────────────────────────────────────────────────────────────────────┴─────────┐
   │                                     Groq Clinical LLM                                      │
   │           - Medical Entity Extraction (Prescriptions, Vitals, Symptoms, Follow-up)         │
   │           - Turn-Level Evidence Preservation & Provenance Binding                          │
   │           - Schedule & Meal Timing Normalization                                           │
   └──────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                              │
                                              ▼
   ┌────────────────────────────────────────────────────────────────────────────────────────────┐
   │                                 Safety & Guardrail Engine                                  │
   │           - Deterministic Validation (Range checks, drug strength, duration)               │
   │           - Mandatory Flag: requires_doctor_review = True                                  │
   └──────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                              │
                                              ▼
   ┌────────────────────────────────────────────────────────────────────────────────────────────┐
   │                                   Supabase PostgreSQL                                      │
   │  Status: 'pending_doctor_review' | Transcript (JSONB) | Medical Record (JSONB)             │
   └────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Consultation Review & Gated Release Lifecycle

```text
                                  Pending Review
                                        │
                                        ▼
                     ┌─────────────────────────────────────┐
                     │ Doctor Opens Consultation Dashboard │
                     │  - Plays audio & edits transcript   │
                     │  - Adjusts diagnoses & medications  │
                     │  - Adds clinician vitals            │
                     └──────────────────┬──────────────────┘
                                        │
                                        ▼
                     ┌─────────────────────────────────────┐
                     │     Doctor Approves & Finalizes     │
                     │  POST /api/v1/consultations/{id}/   │
                     │                 review              │
                     └──────────────────┬──────────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
              [ Status: 'completed' ]       [ Doctor Reviewed: True ]
                         │                             │
                         └──────────────┬──────────────┘
                                        │
                                        ▼
                     ┌─────────────────────────────────────┐
                     │ Bilingual Patient Summary Generated │
                     │   (English & Tamil translations)    │
                     └──────────────────┬──────────────────┘
                                        │
                                        ▼
                     ┌─────────────────────────────────────┐
                     │     Unlocked for Patient Portal     │
                     │  - Interactive Medication Plan      │
                     │  - Daily Recovery Checklist         │
                     │  - Grounded AI Assistant Unlocked   │
                     └─────────────────────────────────────┘
```

### 3.3 Lab OCR & Clinical Verification Pipeline

```text
  Patient Uploads Report (Image/PDF)
               │
               ▼
  Document OCR Extraction Engine (src/services/document_ocr_service.py)
  Extracts: Test Name, Measured Value, Unit, Reference Range, Confidence
               │
               ▼
  Phase 1: Patient Confirmation Modal
  Patient confirms or adjusts report metadata & preliminary values
               │
               ▼
  Status: 'patient_confirmed' (Pending Doctor Verification)
               │
               ▼
  Phase 2: Doctor Clinical Review (Doctor Portal)
  Doctor reviews extracted parameters, overrides if necessary, and marks 'verified'
               │
               ▼
  Status: 'verified' -> Ingested into Patient EHR Trend History
```

### 3.4 Grounded Patient AI Copilot Logic

```text
                  Patient Query (Text / Spoken Voice)
                                   │
                                   ▼
                  Input Sanitization & Guardrails
                                   │
             ┌─────────────────────┴─────────────────────┐
             ▼                                           ▼
   Emergency Red-Flag Check?                   Dosage Change Request?
   - Chest pain, severe breathlessness         - "Can I take 1000mg instead?"
             │                                           │
             ├────────────► [ YES ]                      ├────────────► [ YES ]
             │         Return immediate                  │         Block request & reply:
             │         hospital emergency                │         "Only your doctor can
             │         escalation advice                 │         change your dosage."
             ▼                                           ▼
          [ NO ]                                      [ NO ]
             │                                           │
             └─────────────────────┬─────────────────────┘
                                   │
                                   ▼
                 Grounded Retrieval from Approved EHR
                 - Prescriptions, food timings, warnings
                 - Attending doctor instructions
                                   │
                                   ▼
                 Bilingual Generative Response (EN / TA)
                 Includes source citations & clinical disclaimer
```

---

## 4. Technology Stack

| Domain | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** (Python 3.11) | High-performance asynchronous REST API |
| **Data Validation** | **Pydantic V2** | Type validation and schema contracts |
| **Database & Cloud Storage** | **Supabase** (PostgreSQL + Storage) | JSONB document storage, RLS policies, encrypted media bucket |
| **Inference Engine** | **Groq API** | Low-latency LLM inference (`Qwen 2.5`, `Llama 3.3`) |
| **Speech & Audio** | **IndicConformer & Librosa** | Multilingual ASR (Tamil/English), audio normalization, MFCC diarization |
| **Document Processing** | **PyPDF & Pillow (PIL)** | Multimodal lab report parsing and parameter extraction |
| **Frontend Framework** | **Next.js 14** (App Router, React 19) | Server and client rendered clinical dashboards |
| **Frontend Styling** | **Tailwind CSS** | Clinical UI design system with responsive layouts |
| **Testing & CI** | **Pytest & FastAPI TestClient** | Automated regression, security RBAC, and workflow testing |

---

## 5. Project Directory Structure

```text
POSTVIST/
├── api/                                    # FastAPI Backend Service
│   ├── config.py                           # App settings, environment vars, and keys
│   ├── main.py                             # FastAPI application factory and routing
│   ├── repositories/                       # Data persistence abstractions
│   │   ├── consultation_repository.py      # Supabase & in-memory consultation repo
│   │   ├── guideline_repository.py         # Clinical guidelines search repo
│   │   ├── patient_repository.py           # Patient profile, vitals & EHR repository
│   │   └── summary_repository.py           # Patient discharge summary repository
│   ├── routes/                             # REST API route handlers
│   │   ├── consultations.py                # Audio intake, processing & progress polling
│   │   ├── doctor.py                       # Doctor portal, review queue, AI copilot
│   │   ├── guidelines.py                   # Indian clinical guidelines search
│   │   ├── patient.py                      # Patient portal, recovery tasks, lab upload
│   │   └── summaries.py                    # Bilingual summary generation & review
│   └── schemas/                            # API request/response Pydantic models
├── docs/                                   # Architectural and API specifications
│   └── frontend_api_integration_map.md     # Full frontend-backend API contract map
├── postvisit-frontend/                     # Next.js 14 Frontend Application
│   ├── app/                                # Next.js App Router
│   │   ├── (auth)/login/                   # Doctor & Patient role-based authentication
│   │   ├── doctor/                         # Doctor dashboard, reviews, audio player
│   │   └── patient/                        # Patient care portal, recovery tasks, chat
│   ├── components/                         # Modular UI component library
│   │   ├── clinical/                       # Diarized transcript, summary comparison
│   │   └── layout/                         # Responsive sidebars, navigation bars
│   ├── lib/                                # Client API connectors and state utilities
│   └── types/                              # TypeScript interfaces matching backend models
├── src/                                    # Core AI & Clinical Workflow Engine
│   ├── guardrails/                         # Input validation, sanitization & guardrails
│   ├── guidelines/                         # Clinical guideline rule engines
│   ├── schemas/                            # Core Pydantic domain models
│   ├── services/                           # Business logic services
│   │   ├── doctor_service.py               # Doctor clinical operations
│   │   ├── document_ocr_service.py         # Lab report multimodal OCR extraction
│   │   ├── patient_service.py              # Patient data & grounded AI assistant
│   │   └── summary_service.py              # Clinical summary translation & formatting
│   ├── tools/                              # Audio extraction, diarization & ASR tools
│   ├── workflow/                           # Background job execution engine
│   └── postvisit_pipeline.py               # Main CLI audio pipeline processor
├── supabase/                               # Database schema and migrations
│   └── migrations/                         # SQL scripts with RLS & trigger definitions
├── tests/                                  # Automated Test Suite
│   ├── test_consultation_api.py            # API endpoint integration tests
│   ├── test_consultation_persistence.py    # Supabase persistence tests
│   ├── test_core_clinical_workflow.py      # 17-step end-to-end clinical workflow suite
│   └── test_health.py                      # System health and ping tests
├── requirements.txt                        # Backend Python dependencies
└── README.md                               # Project documentation
```

---

## 6. Installation & Setup Guide

### 6.1 Prerequisites
- **Python 3.11 (64-bit)**
- **Node.js 18+ & npm**
- **Git**
- Active **Supabase** project (URL and Service Role key)
- Active **Groq API** key

### 6.2 Backend Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sudharshan-05/postvisit.git
   cd postvisit
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Fill in your API credentials:
   ```env
   # Groq LLM
   GROQ_API_KEY=gsk_your_groq_api_key_here
   LLM_PROVIDER=groq
   LLM_MODEL=qwen/qwen3.8-27b
   LLM_API_KEY=gsk_your_groq_api_key_here

   # Supabase Persistence
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
   SUPABASE_STORAGE_BUCKET=postvisit-media

   # System Limits
   MAX_UPLOAD_SIZE_MB=100
   API_VERSION=1.0.0
   APP_ENV=development
   ```

### 6.3 Frontend Installation

1. **Navigate to the frontend directory:**
   ```bash
   cd postvisit-frontend
   ```

2. **Install npm dependencies:**
   ```bash
   npm install
   ```

3. **Configure frontend environment (optional):**
   Create a `.env.local` if custom backend URL is desired:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

### 6.4 Supabase Database Migration

Execute the schema migration script in your Supabase SQL editor:
```sql
-- File: supabase/migrations/001_create_consultations.sql
```
This migration provisions the `consultations` table, indexes on query fields, Row Level Security (RLS) policies, and automatic `updated_at` timestamp triggers.

### 6.5 Running Locally

1. **Start the FastAPI Backend:**
   ```bash
   # From the project root with venv activated
   uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```
   - Interactive API Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

2. **Start the Next.js Frontend:**
   ```bash
   # In a separate terminal inside postvisit-frontend/
   cd postvisit-frontend
   npm run dev
   ```
   - Application URL: [http://localhost:3000](http://localhost:3000)
   - Doctor Portal: [http://localhost:3000/doctor](http://localhost:3000/doctor)
   - Patient Portal: [http://localhost:3000/patient](http://localhost:3000/patient)

---

## 7. Verification & Testing

Execute the comprehensive automated test suite to verify all clinical workflows:

```bash
# Windows
.\venv\Scripts\python.exe -m pytest tests/test_core_clinical_workflow.py -v

# Linux / macOS
pytest tests/test_core_clinical_workflow.py -v
```

### Verified Test Cases:
| Test ID | Scenario | Verification Criteria | Status |
| :--- | :--- | :--- | :--- |
| `test_a1` | Transcript Editing | Doctor updates speaker segment text & reassigns turns | **PASSED** |
| `test_a2` | Gated Summary Access | Patient receives 403 Forbidden on unapproved summaries | **PASSED** |
| `test_a3` | Summary Approval | Doctor amends record, approves, and unlocks patient release | **PASSED** |
| `test_b1` | Vitals Entry & Provenance | Clinician records BP, pulse, temp with author attribution | **PASSED** |
| `test_b2` | Verified DOB Age | Patient age is calculated dynamically from verified DOB | **PASSED** |
| `test_b3` | Identity Consistency | Doctor and patient portals share identical verified demographic data | **PASSED** |
| `test_c1` | Lab OCR Extraction | Correctly extracts parameters (HbA1c, FBS) and reference ranges | **PASSED** |
| `test_c2` | Two-Phase Lab Verification | Patient confirms values -> Doctor validates into EHR history | **PASSED** |
| `test_d1` | Grounded Patient Assistant | Patient AI answers questions strictly based on approved meds | **PASSED** |
| `test_d2` | Dosage Change Rejection | AI refuses dosage alteration requests with safety warning | **PASSED** |
| `test_d3` | Emergency Symptoms | AI flags chest pain/dyspnea with emergency escalation steps | **PASSED** |
| `test_e1` | Clinical Guidelines | Doctor queries and links RSSDI/ICMR guideline evidence | **PASSED** |
| `test_e2` | Doctor AI Copilot | Clinician uses `/ask` endpoint for grounded EHR summaries | **PASSED** |
| `test_f1` | Patient RBAC Isolation | Patient A cannot read Patient B's clinical records | **PASSED** |
| `test_f2` | Privilege Escalation Block | Patient cannot trigger doctor approval endpoints | **PASSED** |
| `test_g1` | Not Found Handling | Non-existent consultation UUID returns clean 404 response | **PASSED** |
| `test_g2` | Unsupported Media Handling | Reject invalid file formats cleanly without crash | **PASSED** |

---

## 8. What We Are Yet to Work On (Future Roadmap)

While the core consultation pipeline, human-in-the-loop review, lab OCR, and patient care portals are fully operational, the following enhancements represent our active roadmap:

### 1. Real-Time Streaming ASR (WebSockets)
- Replace batch audio file uploads with low-latency WebSocket streaming.
- Provide live, rolling transcription and speaker diarization directly in the examination room as the consultation takes place.

### 2. Clinic Hardware & Acoustic Noise Suppression
- Implement active background noise cancellation tuned for noisy Indian Outpatient Department (OPD) environments (fans, hallway chatter, street noise).
- Support dual-microphone array directional beamforming to distinguish doctor voice from patient and attendants.

### 3. Expansion of Indic Languages
- Extend beyond Tamil and English to support Hindi, Telugu, Kannada, Malayalam, Bengali, and Marathi conversational code-switching.
- Integrate region-specific dialect variations and colloquial medical idioms.

### 4. FHIR R4 & ABDM (Ayushman Bharat Digital Mission) Compliance
- Implement HL7 FHIR Release 4 resource serialization for consultations (`Encounter`, `Condition`, `MedicationRequest`, `Observation`).
- Integrate ABDM Milestone 1, 2, and 3 APIs to enable Ayushman Bharat Health Account (ABHA) linking, patient discovery, and consent-based health data exchange.

### 5. Automated SNOMED CT & ICD-10 Coding
- Automatically tag extracted diagnoses with ICD-10 diagnostic codes and map medications to SNOMED CT / RxNorm clinical concepts.

### 6. Native Mobile Applications
- Develop native iOS and Android lightweight mobile applications (React Native / Flutter) optimized for low-bandwidth rural health workers and primary health centers (PHCs).
- Offline-first audio caching with automatic sync upon regaining cellular connectivity.

### 7. Vector Database & Semantic Clinical Retrieval
- Implement `pgvector` in Supabase for semantic search over full institutional clinical guideline corpuses, drug interaction databases, and historical patient visit trajectories.

---

## 9. Security, Privacy & Compliance

- **Role-Based Access Control (RBAC):** Strict boundary separation between clinicians and patients enforced by JWT authentication and permission gates.
- **Doctor Approval Barrier:** Medical recommendations and summaries are never released to patients without explicit clinician sign-off.
- **Secret Hygiene:** All API credentials, JWT secrets, and database connection strings are managed via `.env` and are strictly excluded from source control.
- **Audit Logging:** Every consultation mutation, transcript edit, and approval decision generates an immutable audit record containing clinician ID, timestamp, and modification details.

---

## 10. License & Acknowledgements

- **Proprietary & Confidential:** Developed for PostVisit AI healthcare operations.
- Powered by open research in speech recognition from **AI4Bharat (IndicConformer)** and high-speed LLM inference by **Groq**.
