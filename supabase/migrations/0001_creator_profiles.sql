-- Creator accounts, private voice profiles, jobs, feedback, and the consented pooled corpus.
-- Design and rationale: docs/CREATOR_PROFILES.md
-- Not yet applied to any database. Sign-ups must be disabled in Supabase Auth (invite-only).

create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text not null default '',
  -- Pooling is opt-in per creator. Null means no consent; clearing it withdraws consent.
  pooling_consent_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.voice_profiles (
  user_id uuid primary key references public.profiles on delete cascade,
  tone_summary text not null default '',
  audience text not null default '',
  platforms text[] not null default '{}',
  dialect_notes text not null default '',
  -- The creator must approve the drafted tone summary before it is used for writing.
  approved_at timestamptz,
  updated_at timestamptz not null default now()
);

create table public.voice_examples (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles on delete cascade,
  platform text not null default '',
  body text not null check (char_length(body) between 1 and 8000),
  created_at timestamptz not null default now()
);
create index on public.voice_examples (user_id);

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles on delete cascade,
  topic text not null,
  strategy_id text not null,
  state text not null default 'queued',
  result jsonb,
  created_at timestamptz not null default now()
);
create index on public.jobs (user_id, created_at desc);

create table public.feedback (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs on delete cascade,
  user_id uuid not null references public.profiles on delete cascade,
  rating smallint not null check (rating between 1 and 5),
  edited_copy text,
  created_at timestamptz not null default now()
);
create index on public.feedback (user_id);

-- Shared dialect corpus. Rows are scrubbed of names/handles by the backend before insert.
-- contributor is kept only so withdrawal or account deletion removes the rows (cascade);
-- it is never exposed to clients: RLS is on and there are no client policies.
create table public.pooled_corpus (
  id uuid primary key default gen_random_uuid(),
  contributor uuid not null references public.profiles on delete cascade,
  source_kind text not null check (source_kind in ('example', 'accepted_draft', 'edit')),
  body text not null,
  created_at timestamptz not null default now()
);
create index on public.pooled_corpus (contributor);

-- Withdrawing consent removes that creator's pooled rows.
create function public.purge_pooled_on_withdrawal() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.pooling_consent_at is not null and new.pooling_consent_at is null then
    delete from public.pooled_corpus where contributor = new.id;
  end if;
  return new;
end $$;

create trigger profiles_purge_pooled after update of pooling_consent_at on public.profiles
for each row execute function public.purge_pooled_on_withdrawal();

-- New auth users get a profile row.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
for each row execute function public.handle_new_user();

-- Row-level security: each creator sees and edits only their own rows.
alter table public.profiles enable row level security;
alter table public.voice_profiles enable row level security;
alter table public.voice_examples enable row level security;
alter table public.jobs enable row level security;
alter table public.feedback enable row level security;
alter table public.pooled_corpus enable row level security;

create policy own_profile_select on public.profiles for select using (id = (select auth.uid()));
create policy own_profile_update on public.profiles for update using (id = (select auth.uid()));

create policy own_voice_all on public.voice_profiles for all
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_examples_all on public.voice_examples for all
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- Jobs are created and updated by the backend (service role); creators only read their own.
create policy own_jobs_select on public.jobs for select using (user_id = (select auth.uid()));

create policy own_feedback_select on public.feedback for select using (user_id = (select auth.uid()));
create policy own_feedback_insert on public.feedback for insert with check (user_id = (select auth.uid()));

-- pooled_corpus: no policies on purpose. Only the backend's service role can read or write it.
