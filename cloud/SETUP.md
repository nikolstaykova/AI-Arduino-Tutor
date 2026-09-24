# Accounts + shared lessons (Supabase, free)

With these set up, the hosted app asks people to **Sign in with Google**, keeps
each person's stars/XP in their account, and shares every created lesson with
everyone ("made by Mert"). Without them the app runs on local files as before.

## 1. Supabase project (2 min)
1. Go to **supabase.com** → sign in with GitHub → **New project** (free plan). Pick any name, a database password (keep it), and a region near you.
2. When it's ready: **SQL Editor → New query** → paste all of [`supabase.sql`](./supabase.sql) → **Run**. (It makes the `profiles` and `lessons` tables.)

## 2. A Google login client (5 min)
1. Go to **console.cloud.google.com** → create a project (e.g. "CircuitQuest").
2. **APIs & Services → OAuth consent screen**: External, app name "CircuitQuest", your email → save. Under **Audience / Test users**, add your Gmail and your friends' (e.g. Mert's) — or press **Publish app** so any Google account can sign in (name + email only, no Google review needed).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID** → *Web application*.
   Under **Authorized redirect URIs** add: `https://<your-project-ref>.supabase.co/auth/v1/callback`
   (the exact address is shown in Supabase → Authentication → Sign In / Providers → Google).
4. Copy the **Client ID** and **Client secret**.

## 3. Turn Google on in Supabase
1. **Authentication → Sign In / Providers → Google** → enable → paste the Client ID and secret → Save.
2. **Authentication → URL Configuration**: Site URL = your Render address (`https://circuitquest-xxxx.onrender.com`). Under Redirect URLs also add `http://localhost:8765` if you want accounts locally too.

## 4. Give the app the keys
In Supabase **Project Settings → API** (or *API Keys*) copy:
- **Project URL** → `SUPABASE_URL`
- **anon / publishable key** → `SUPABASE_ANON_KEY` (public — it's only for signing in)
- **service_role / secret key** → `SUPABASE_SERVICE_KEY` (**secret** — server only, never in git)

Render → your service → **Environment** → add the three → **Save** (it redeploys).
Locally (optional): put them in `.env`.

The log then says `Accounts: Sign in with Google (Supabase)`.
