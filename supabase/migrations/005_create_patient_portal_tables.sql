-- PostVisit AI - Stage 5A: Patient Portal & Health Dashboard Migration
-- Creates tables for patient profiles, health metrics, lab reports, recovery plan tracking,
-- AI chat history, and patient voice recordings with RLS and performance indexes.

-- 1. Patient Profiles Table
CREATE TABLE IF NOT EXISTS public.patient_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT UNIQUE NOT NULL, -- e.g. 'PT-89241'
    name TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    phone TEXT,
    blood_group TEXT,
    allergies JSONB NOT NULL DEFAULT '[]'::jsonb,
    chronic_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Patient Lab Reports Table (Document uploads and manual summaries)
CREATE TABLE IF NOT EXISTS public.patient_lab_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    consultation_id UUID REFERENCES public.consultations(id) ON DELETE SET NULL,
    test_name TEXT NOT NULL,
    report_date DATE NOT NULL,
    laboratory_name TEXT,
    result_summary TEXT NOT NULL,
    units TEXT,
    reference_range TEXT,
    patient_notes TEXT,
    entry_mode TEXT NOT NULL DEFAULT 'manual', -- 'manual' or 'upload'
    file_storage_path TEXT,
    file_name TEXT,
    file_type TEXT,
    file_size_bytes BIGINT,
    review_status TEXT NOT NULL DEFAULT 'unreviewed', -- 'unreviewed' or 'physician_reviewed'
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    doctor_feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. Patient Health Metrics Table (Actual dated measurements for trends)
CREATE TABLE IF NOT EXISTS public.patient_health_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    consultation_id UUID REFERENCES public.consultations(id) ON DELETE SET NULL,
    metric_type TEXT NOT NULL, -- 'blood_pressure', 'glucose', 'heart_rate', 'weight'
    metric_name TEXT NOT NULL,
    value NUMERIC NOT NULL,
    value_secondary NUMERIC, -- for Diastolic BP
    unit TEXT NOT NULL, -- 'mmHg', 'mg/dL', 'bpm', 'kg'
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    source TEXT NOT NULL DEFAULT 'consultation', -- 'consultation' or 'patient_entry'
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. Patient Recovery Tracking Table (Checklist task completion)
CREATE TABLE IF NOT EXISTS public.patient_recovery_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    consultation_id UUID NOT NULL REFERENCES public.consultations(id) ON DELETE CASCADE,
    task_key TEXT NOT NULL,
    task_type TEXT NOT NULL, -- 'medication', 'lab_test', 'self_care', 'lifestyle'
    task_title TEXT NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(patient_id, consultation_id, task_key)
);

-- 5. Patient Chat Messages Table (Session conversational history)
CREATE TABLE IF NOT EXISTS public.patient_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    consultation_id UUID REFERENCES public.consultations(id) ON DELETE SET NULL,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    context_topic TEXT, -- 'medication', 'lab_report', 'last_visit', 'health_trend', 'general'
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 6. Patient Voice Notes Table (Audio recordings & reviewed transcripts)
CREATE TABLE IF NOT EXISTS public.patient_voice_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    storage_path TEXT,
    audio_filename TEXT NOT NULL,
    audio_format TEXT NOT NULL,
    transcription TEXT,
    language TEXT NOT NULL DEFAULT 'ta',
    duration_seconds NUMERIC,
    status TEXT NOT NULL DEFAULT 'transcribed', -- 'recorded', 'transcribed', 'reviewed'
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 7. Performance & Uniqueness Indexes
CREATE INDEX IF NOT EXISTS idx_patient_lab_reports_patient ON public.patient_lab_reports(patient_id, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_patient_health_metrics_patient ON public.patient_health_metrics(patient_id, metric_type, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_patient_recovery_tracking_cid ON public.patient_recovery_tracking(patient_id, consultation_id);
CREATE INDEX IF NOT EXISTS idx_patient_chat_session ON public.patient_chat_messages(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_patient_voice_notes_patient ON public.patient_voice_notes(patient_id, created_at DESC);

-- 8. Enable Row Level Security (RLS)
ALTER TABLE public.patient_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_lab_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_health_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_recovery_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_voice_notes ENABLE ROW LEVEL SECURITY;
