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
  claude_key       text,     -- the learner's own Anthropic API key, sealed (encrypted) by the app
  claude_key_hint  text,     -- its last 4 characters, to show "connected (…abcd)"
  updated_at  timestamptz default now()
);
-- (if you ran an older version of this file:)
alter table public.profiles add column if not exists claude_key text;
alter table public.profiles add column if not exists claude_key_hint text;

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

-- guests: people who just typed a name (no Google). Keyed by a random id
-- their browser keeps; progress only, no lessons.
create table if not exists public.guests (
  id          uuid primary key,
  name        text,
  difficulty  text default 'beginner',
  progress    jsonb default '{}'::jsonb,
  updated_at  timestamptz default now()
);

alter table public.profiles enable row level security;
alter table public.guests   enable row level security;
alter table public.lessons  enable row level security;
