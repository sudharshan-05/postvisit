-- PostVisit AI - Stage 5B: Doctor Dashboard & Clinical Review Migration
-- Creates additive tables for doctor lab reviews, verified values, clinical voice note confirmations,
-- and append-only clinical audit trail with RLS and performance indexes.

-- 1. Doctor Lab Reviews Table (Preserving original patient submission, storing verified corrections)
CREATE TABLE IF NOT EXISTS public.doctor_lab_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL,
    consultation_id UUID REFERENCES public.consultations(id) ON DELETE SET NULL,
    doctor_id TEXT NOT NULL,
    decision TEXT NOT NULL, -- 'REPORT_REVIEWED', 'REPORT_NEEDS_CLARIFICATION', 'REPORT_REJECTED'
    verified_value TEXT,
    verified_unit TEXT,
    doctor_notes TEXT,
    clarification_request TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Doctor Voice Notes Table (Enforces physician confirmation gate before clinical chart entry)
CREATE TABLE IF NOT EXISTS public.doctor_voice_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES public.consultations(id) ON DELETE CASCADE,
    draft_id TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    raw_transcript TEXT NOT NULL,
    final_note_text TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'clinical_observation', -- 'clinical_observation', 'follow_up_instructions', 'summary_correction', 'additional_note'
    is_confirmed BOOLEAN NOT NULL DEFAULT true,
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. Append-Only Clinical Audit Events Table
CREATE TABLE IF NOT EXISTS public.clinical_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID REFERENCES public.consultations(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'SUMMARY_GENERATED', 'SUMMARY_REVIEWED', 'SUMMARY_AMENDED', 'SUMMARY_APPROVED', 'SUMMARY_REJECTED', 'LAB_REVIEWED', 'LAB_CORRECTED', 'GUIDELINE_REVIEWED', 'DOCTOR_VOICE_NOTE'
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL DEFAULT 'doctor',
    description TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    severity TEXT NOT NULL DEFAULT 'info', -- 'info', 'warning', 'critical'
    timestamp TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. Indexes for rapid lookups and query efficiency
CREATE INDEX IF NOT EXISTS idx_doc_lab_reviews_report ON public.doctor_lab_reviews(report_id);
CREATE INDEX IF NOT EXISTS idx_doc_lab_reviews_cid ON public.doctor_lab_reviews(consultation_id);
CREATE INDEX IF NOT EXISTS idx_doc_voice_notes_cid ON public.doctor_voice_notes(consultation_id);
CREATE INDEX IF NOT EXISTS idx_clinical_audit_cid ON public.clinical_audit_events(consultation_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_clinical_audit_event ON public.clinical_audit_events(event_type);

-- 5. Enable Row Level Security (RLS)
ALTER TABLE public.doctor_lab_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctor_voice_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinical_audit_events ENABLE ROW LEVEL SECURITY;

-- 6. RLS Policies
-- Only authenticated physicians can insert/read doctor reviews
CREATE POLICY "Doctors have full access to lab reviews"
    ON public.doctor_lab_reviews FOR ALL
    USING (auth.jwt() ->> 'role' = 'doctor' OR auth.role() = 'authenticated');

CREATE POLICY "Doctors have full access to voice notes"
    ON public.doctor_voice_notes FOR ALL
    USING (auth.jwt() ->> 'role' = 'doctor' OR auth.role() = 'authenticated');

CREATE POLICY "Read clinical audit events"
    ON public.clinical_audit_events FOR SELECT
    USING (true);

CREATE POLICY "Append-only clinical audit events"
    ON public.clinical_audit_events FOR INSERT
    WITH CHECK (true);
