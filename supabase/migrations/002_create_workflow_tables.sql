-- PostVisit AI - Stage 3: Workflow Runs, Steps, and Agent Executions Migration
-- Extends the Supabase persistence layer with durable workflow state tracking,
-- step-level retries, and agent execution audit logs.

-- 1. Create workflow_runs table
create table if not exists public.workflow_runs (
    id uuid primary key default gen_random_uuid(),
    consultation_id uuid not null references public.consultations(id) on delete cascade,

    -- Explicit workflow state machine status
    status text not null default 'queued',
    current_step text,
    workflow_version text not null default '1.0.0',

    started_at timestamptz,
    completed_at timestamptz,
    failed_at timestamptz,

    error_code text,
    error_message text,
    metadata jsonb default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 2. Create workflow_steps table
create table if not exists public.workflow_steps (
    id uuid primary key default gen_random_uuid(),
    workflow_run_id uuid not null references public.workflow_runs(id) on delete cascade,

    step_name text not null,
    step_type text not null, -- 'guardrail', 'service', 'agent', 'persistence', 'review'
    status text not null default 'pending', -- 'pending', 'running', 'completed', 'failed', 'retrying', 'skipped', 'needs_review'

    attempt integer not null default 1,
    max_attempts integer not null default 3,

    started_at timestamptz,
    completed_at timestamptz,

    error text,
    input_reference jsonb,
    output_reference jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 3. Create agent_executions table
create table if not exists public.agent_executions (
    id uuid primary key default gen_random_uuid(),
    workflow_run_id uuid not null references public.workflow_runs(id) on delete cascade,
    step_id uuid references public.workflow_steps(id) on delete set null,

    agent_name text not null,
    agent_version text not null default '1.0.0',
    status text not null default 'running', -- 'running', 'completed', 'failed', 'retrying'

    attempt integer not null default 1,
    input_hash text,

    started_at timestamptz not null default now(),
    completed_at timestamptz,

    error text,
    metadata jsonb default '{}'::jsonb,

    created_at timestamptz not null default now()
);

-- 4. Optimal performance indexes
create index if not exists workflow_runs_consultation_id_idx
    on public.workflow_runs(consultation_id);

create index if not exists workflow_runs_status_idx
    on public.workflow_runs(status);

create index if not exists workflow_runs_created_at_idx
    on public.workflow_runs(created_at desc);

create index if not exists workflow_steps_run_id_idx
    on public.workflow_steps(workflow_run_id);

create index if not exists workflow_steps_status_idx
    on public.workflow_steps(status);

create index if not exists agent_executions_run_id_idx
    on public.agent_executions(workflow_run_id);

create index if not exists agent_executions_agent_name_idx
    on public.agent_executions(agent_name);

create index if not exists agent_executions_input_hash_idx
    on public.agent_executions(input_hash);

-- 5. Row Level Security (RLS) enabled
alter table public.workflow_runs enable row level security;
alter table public.workflow_steps enable row level security;
alter table public.agent_executions enable row level security;

-- 6. Auto-update updated_at triggers
drop trigger if exists set_workflow_runs_updated_at on public.workflow_runs;
create trigger set_workflow_runs_updated_at
    before update on public.workflow_runs
    for each row
    execute function public.set_current_timestamp_updated_at();

drop trigger if exists set_workflow_steps_updated_at on public.workflow_steps;
create trigger set_workflow_steps_updated_at
    before update on public.workflow_steps
    for each row
    execute function public.set_current_timestamp_updated_at();
