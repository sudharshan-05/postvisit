-- PostVisit AI - Stage 2: Consultations Table Migration
-- Creates the consultations persistence table, indexes, RLS, and auto-updating timestamps.

-- 1. Enable pgcrypto / uuid-ossp if gen_random_uuid() is needed (built-in in PostgreSQL 13+)
create extension if not exists "pgcrypto";

-- 2. Create consultations table
create table if not exists public.consultations (
    id uuid primary key default gen_random_uuid(),

    -- Processing lifecycle: 'processing', 'completed', 'failed'
    status text not null default 'processing',

    original_filename text,
    media_type text,
    media_storage_path text,

    duration_seconds numeric,

    -- JSONB clinical data structures
    transcript jsonb,
    medical_record jsonb,
    validation_result jsonb,

    -- Error tracking for failed processing
    error_code text,
    error_message text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 3. Optimal performance indexes
create index if not exists consultations_status_idx
    on public.consultations(status);

create index if not exists consultations_created_at_idx
    on public.consultations(created_at desc);

-- 4. Enable Row Level Security (RLS)
alter table public.consultations enable row level security;

-- NOTE ON RLS IN STAGE 2:
-- Stage 2 uses server-side access via the Supabase Service Role Key exclusively on the FastAPI backend.
-- The Service Role Key bypasses RLS.
-- We intentionally DO NOT create a public 'using (true)' policy, preserving database security.
-- Fine-grained user/doctor/patient policies will be introduced alongside Authentication in subsequent stages.

-- 5. Auto-update updated_at timestamp trigger
create or replace function public.set_current_timestamp_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists set_consultations_updated_at on public.consultations;
create trigger set_consultations_updated_at
    before update on public.consultations
    for each row
    execute function public.set_current_timestamp_updated_at();
