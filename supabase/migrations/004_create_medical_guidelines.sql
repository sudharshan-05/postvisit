-- PostVisit AI - Stage 5: Medical Guidelines & Clinical Cross-Referencing Migration
-- Adds tables for storing authoritative Indian clinical guideline sources,
-- cross-referencing evaluation results, evidence provenance, and physician review records.

-- 1. Create medical_guidelines table
create table if not exists public.medical_guidelines (
    id text primary key, -- e.g. 'icmr-diabetes-2022', 'icmr-htn-2021'
    title text not null,
    organization text not null, -- 'Indian Council of Medical Research (ICMR)', 'MoHFW India'
    country text not null default 'India',
    topic text not null,
    source_url text,
    publication_date text,
    version text not null default '1.0',
    verified boolean not null default true,
    checksum text,
    summary text,
    key_recommendations jsonb not null default '[]'::jsonb,
    evidence_passages jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 2. Create guideline_cross_references table
create table if not exists public.guideline_cross_references (
    id uuid primary key default gen_random_uuid(),
    consultation_id uuid not null references public.consultations(id) on delete cascade,
    medical_record_hash text,
    
    -- Evaluation status:
    -- 'PENDING', 'RUNNING', 'COMPLETED_WITH_FINDINGS', 'COMPLETED_NO_FINDINGS',
    -- 'NO_VERIFIED_SOURCE', 'NOT_CONFIGURED', 'FAILED', 'NEEDS_REVIEW'
    status text not null default 'PENDING',
    
    guidelines_evaluated jsonb not null default '[]'::jsonb,
    findings jsonb not null default '[]'::jsonb,
    agent_version text not null default '1.0.0',
    execution_time_sec numeric not null default 0.0,
    notes text,
    
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 3. Create guideline_reviews table
create table if not exists public.guideline_reviews (
    id uuid primary key default gen_random_uuid(),
    cross_reference_id uuid not null references public.guideline_cross_references(id) on delete cascade,
    consultation_id uuid not null references public.consultations(id) on delete cascade,
    finding_id text not null,
    doctor_id text not null,
    doctor_name text not null,
    decision text not null, -- 'acknowledged', 'dismissed', 'amended'
    notes text,
    created_at timestamptz not null default now()
);

-- 4. Create performance indexes
create index if not exists medical_guidelines_topic_idx
    on public.medical_guidelines(topic);

create index if not exists medical_guidelines_verified_idx
    on public.medical_guidelines(verified);

create index if not exists guideline_cross_refs_consultation_idx
    on public.guideline_cross_references(consultation_id);

create index if not exists guideline_cross_refs_status_idx
    on public.guideline_cross_references(status);

create index if not exists guideline_reviews_consultation_idx
    on public.guideline_reviews(consultation_id);

create index if not exists guideline_reviews_cross_ref_idx
    on public.guideline_reviews(cross_reference_id);

-- 5. Enable Row Level Security (RLS)
alter table public.medical_guidelines enable row level security;
alter table public.guideline_cross_references enable row level security;
alter table public.guideline_reviews enable row level security;

-- 6. Trigger for updated_at
drop trigger if exists set_medical_guidelines_updated_at on public.medical_guidelines;
create trigger set_medical_guidelines_updated_at
    before update on public.medical_guidelines
    for each row
    execute function public.set_current_timestamp_updated_at();

drop trigger if exists set_guideline_cross_refs_updated_at on public.guideline_cross_references;
create trigger set_guideline_cross_refs_updated_at
    before update on public.guideline_cross_references
    for each row
    execute function public.set_current_timestamp_updated_at();
