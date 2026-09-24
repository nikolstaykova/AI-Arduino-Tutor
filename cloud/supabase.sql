-- CircuitQuest: run this once in Supabase → SQL Editor → New query → Run.
-- Two tables. Only the app's server reads and writes them (with the service
-- key); row-level security is on with no policies, so the public anon key
-- can't touch them.

create table if not exists public.profiles (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  email       text,
  name        text,
  avatar      text,
  difficulty  text default 'beginner',
  progress    jsonb default '{}'::jsonb,
  parts       jsonb default '[]'::jsonb,
  updated_at  timestamptz default now()
);

create table if not exists public.lessons (
  id            text primary key,
  title         text not null,
  description   text,
  source_url    text,
  creator_id    uuid references auth.users (id) on delete set null,
  creator_name  text,
  data          jsonb not null,
  diagram       jsonb not null,
  code          text not null,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);
create index if not exists lessons_source_url on public.lessons (source_url);

alter table public.profiles enable row level security;
alter table public.lessons  enable row level security;
