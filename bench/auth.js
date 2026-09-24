// Sign in with Google (Supabase Auth) — only when the server has accounts on
// (core/cloud.py). The page keeps the access token in window.__cqToken and
// app.js's api() sends it with every request; supabase-js refreshes it.
// Without accounts this is a no-op and the app runs on local files.
export async function setupAuth() {
  const cfg = await fetch("/api/auth_config", { method: "POST", body: "{}" }).then((r) => r.json()).catch(() => ({ enabled: false }));
  if (!cfg.enabled) return { enabled: false, user: null };
  const { createClient } = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm");
  const sb = createClient(cfg.url, cfg.anon_key, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
  const { data } = await sb.auth.getSession();
  const session = data && data.session;
  window.__cqToken = session ? session.access_token : null;
  sb.auth.onAuthStateChange((_event, s) => { window.__cqToken = s ? s.access_token : null; });
  // tidy the address bar after the Google redirect
  if (location.hash.includes("access_token") || location.search.includes("code=")) history.replaceState(null, "", location.pathname);
  const u = session && session.user, meta = (u && u.user_metadata) || {};
  return {
    enabled: true,
    user: u ? { id: u.id, email: u.email, name: meta.full_name || meta.name || (u.email || "").split("@")[0], avatar: meta.avatar_url || meta.picture } : null,
    signIn: () => sb.auth.signInWithOAuth({ provider: "google", options: { redirectTo: location.origin + location.pathname } }),
    signOut: async () => { await sb.auth.signOut(); window.__cqToken = null; location.reload(); },
  };
}
