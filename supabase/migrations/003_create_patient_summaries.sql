-- PostVisit AI - Stage 4: Patient Summaries & Audit Persistence Migration
-- Adds tables for storing multilingual patient-friendly medical summaries,
-- physician review decisions, amendments, and security audit logs.

-- 1. Create patient_summaries table
create table if not exists public.patient_summaries (
    id uuid primary key default gen_random_uuid(),
    consultation_id uuid not null references public.consultations(id) on delete cascade,

    -- Language code ('en', 'ta', 'kn', 'te', 'ml')
    language text not null default 'en',
    version integer not null default 1,

    -- Summary review lifecycle status
    -- 'SUMMARY_QUEUED', 'GENERATING_SUMMARY', 'VALIDATING_SUMMARY',
    -- 'PENDING_SUMMARY_REVIEW', 'SUMMARY_APPROVED', 'SUMMARY_REJECTED',
    -- 'SUMMARY_FAILED', 'NEEDS_REVIEW'
    status text not null default 'PENDING_SUMMARY_REVIEW',

    -- Generated and reviewed summary contents (JSONB)
    generated_summary jsonb not null,
    reviewed_summary jsonb,

    -- Doctor review metadata
    reviewed_by text,
    reviewed_at timestamptz,
    review_decision text, -- 'approved', 'rejected', 'amended'
    review_notes text,

    -- Integrity & version correlation
    source_record_hash text,
    idempotency_key text,
    agent_version text not null default '1.0.0',
    prompt_version text not null default '1.0.0',

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 2. Create patient_summary_audits table
create table if not exists public.patient_summary_audits (
    id uuid primary key default gen_random_uuid(),
    summary_id uuid not null references public.patient_summaries(id) on delete cascade,
    consultation_id uuid not null references public.consultations(id) on delete cascade,

    action text not null, -- 'generated', 'validated', 'reviewed', 'approved', 'rejected', 'amended'
    actor_id text not null,
    actor_role text not null, -- 'doctor', 'patient', 'system', 'agent'
    notes text,
    changes jsonb,

    created_at timestamptz not null default now()
);

-- 3. Optimal performance and uniqueness indexes
create index if not exists patient_summaries_consultation_id_idx
    on public.patient_summaries(consultation_id);

create index if not exists patient_summaries_status_idx
    on public.patient_summaries(status);

create index if not exists patient_summaries_lang_idx
    on public.patient_summaries(language);

create index if not exists patient_summaries_idempotency_idx
    on public.patient_summaries(idempotency_key);

create index if not exists patient_summary_audits_summary_id_idx
    on public.patient_summary_audits(summary_id);

-- Prevent duplicate summaries for the same consultation, language, and version
create unique index if not exists patient_summaries_consultation_lang_ver_idx
    on public.patient_summaries(consultation_id, language, version);

-- 4. Enable Row Level Security (RLS)
alter table public.patient_summaries enable row level security;
alter table public.patient_summary_audits enable row level security;

-- 5. Auto-update updated_at triggers
drop trigger if exists set_patient_summaries_updated_at on public.patient_summaries;
create trigger set_patient_summaries_updated_at
    before update on public.patient_summaries
    for each row
    execute function public.set_current_timestamp_updated_at();
