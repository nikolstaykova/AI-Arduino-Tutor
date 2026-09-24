# Accounts, shared lessons and "bring your own Claude" (Supabase, free)

With this set up, the hosted app:
- asks people to **Sign in with Google** and keeps each person's stars/XP in their account;
- shares every created lesson with everyone ("made by Mert");
- keeps **Create my own lesson locked** until a person connects **their own Claude**
  (an Anthropic API key — checked with Anthropic, stored encrypted). Your own Claude
  login is only used for the emails you list in `CQ_OWNER_EMAILS`.

Without it the app runs on local files as before.

## 1. Supabase project (≈3 min)
1. **supabase.com** → *Start your project* → sign in with GitHub → **New project** (Free). Any name, a database password (save it somewhere), a region near you → *Create*. Wait ~1 minute.
2. Left menu **SQL Editor** → *New query* → paste everything from [`supabase.sql`](./supabase.sql) → **Run**. It should say *Success. No rows returned.*

## 2. A Google sign-in client (≈5 min)
1. **console.cloud.google.com** → top bar project picker → *New project* → "CircuitQuest" → *Create*, and select it.
2. Menu **APIs & Services → OAuth consent screen** → *Get started*: app name "CircuitQuest", your email → *Audience: External* → contact email → *Create*.
3. **Audience** → either *Add users* (your Gmail, Mert's …) or **Publish app** so any Google account can sign in (only name + email are used, so no Google review is needed).
4. **Clients → Create client** → *Web application* → name "CircuitQuest".
   Under **Authorized redirect URIs** → *Add URI* → `https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback`
   (copy the exact one from Supabase → **Authentication → Sign In / Providers → Google**, "Callback URL").
   → *Create*, and copy the **Client ID** and **Client secret**.

## 3. Turn Google on in Supabase
1. **Authentication → Sign In / Providers → Google** → enable → paste Client ID + Client secret → *Save*.
2. **Authentication → URL Configuration** → *Site URL* = your Render address (`https://circuitquest-xxxx.onrender.com`) → *Save*.
   (Optional, for accounts on your Mac too: under *Redirect URLs* add `http://localhost:8765`.)

## 4. Give the app the keys (Render)
Supabase **Project Settings → API Keys** (and **Data API** for the URL):
| Render variable | Where from | Secret? |
|---|---|---|
| `SUPABASE_URL` | Project URL, `https://xxxx.supabase.co` | no |
| `SUPABASE_ANON_KEY` | *anon / publishable* key | no (public, sign-in only) |
| `SUPABASE_SERVICE_KEY` | *service_role / secret* key | **yes** — only ever in Render |
| `CQ_OWNER_EMAILS` | your Google email (comma-separate several) | no |
| `CQ_SECRET_KEY` | Render generates it (blueprint) — or any 40+ random characters | **yes** |

Render → your **circuitquest** service → **Environment** → *Add environment variable* for each → **Save, rebuild and deploy**.

The log then shows `Accounts: Sign in with Google (Supabase)`.

## 5. Each person's own Claude (they do this in the app)
Create → **Connect your Claude**: get a key at **console.anthropic.com → Settings → API keys** (sign up, add a few dollars of credit, optionally set a monthly limit), paste it, *Connect*. It's checked with Anthropic, sealed with `CQ_SECRET_KEY`, and only its last 4 characters are ever shown. *Disconnect* deletes it.
