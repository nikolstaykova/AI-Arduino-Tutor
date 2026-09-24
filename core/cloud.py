"""Accounts and shared lessons through Supabase (optional).

When SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY are set, the
hosted app gets:
  - sign-in with Google (Supabase Auth; the page signs in, the server checks
    the access token on every request with /auth/v1/user);
  - one profile row per account (name, progress, parts) in `profiles`;
  - every created lesson in `lessons`, shared with everyone — a lesson
    Mert creates shows up on your map too ("made by Mert").

Without those variables nothing here runs and the app keeps its local
files (profile.json, lessons/) — your own machine needs no account.

Only the server talks to the database, with the service key (row-level
security is on and grants the public nothing); the browser only ever gets
the anon key, which is public by design and only good for signing in.
Standard library only: plain HTTPS calls to Supabase's REST API.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .lesson import LESSONS_ROOT

TIMEOUT = 15


def config():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon, service = os.environ.get("SUPABASE_ANON_KEY", ""), os.environ.get("SUPABASE_SERVICE_KEY", "")
    return {"url": url, "anon": anon, "service": service} if url and anon and service else None


def enabled():
    return config() is not None


def public_config():
    """What the page needs to show "Sign in with Google" (never the service key)."""
    c = config()
    return {"enabled": bool(c), "url": c["url"] if c else None, "anon_key": c["anon"] if c else None}


def _call(method, path, body=None, *, token=None, headers=None, key="service"):
    c = config()
    req = urllib.request.Request(c["url"] + path, method=method,
                                 data=None if body is None else json.dumps(body).encode())
    req.add_header("apikey", c[key])
    # a user's token, or a legacy JWT key; the newer sb_publishable_/sb_secret_ keys
    # aren't JWTs and go in the apikey header only
    bearer = token or (c[key] if c[key].startswith("eyJ") else None)
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        raw = res.read()
    return json.loads(raw) if raw else None


# ---- who is signed in ------------------------------------------------------------------
_users, _users_lock = {}, threading.Lock()
USER_CACHE_SECONDS = 300


def user_from_token(token):
    """The signed-in account for a Supabase access token, or None.
    {"id", "email", "name", "avatar"}; cached a few minutes per token."""
    if not token or not enabled():
        return None
    now = time.time()
    with _users_lock:
        hit = _users.get(token)
        if hit and hit[1] > now:
            return hit[0]
    try:
        u = _call("GET", "/auth/v1/user", token=token, key="anon")
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if not u or not u.get("id"):
        return None
    meta = u.get("user_metadata") or {}
    user = {"id": u["id"], "email": u.get("email"),
            "name": (meta.get("full_name") or meta.get("name") or (u.get("email") or "friend").split("@")[0]).strip(),
            "avatar": meta.get("avatar_url") or meta.get("picture")}
    with _users_lock:
        if len(_users) > 500:
            _users.clear()
        _users[token] = (user, now + USER_CACHE_SECONDS)
    return user


# ---- profiles ----------------------------------------------------------------------------
def load_profile(user):
    rows = _call("GET", f"/rest/v1/profiles?user_id=eq.{user['id']}&select=*")
    if rows:
        row = rows[0]
        return {"name": row.get("name") or user["name"], "difficulty": row.get("difficulty") or "beginner",
                "progress": row.get("progress") or {}, "parts": row.get("parts") or [],
                "claude_key_hint": row.get("claude_key_hint")}
    return {"name": user["name"]}


# ---- guests (typed a name, no Google): progress under a random id their browser keeps ----
GUEST_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def valid_guest_id(gid):
    return bool(gid and GUEST_ID.match(gid))


def load_guest(gid):
    rows = _call("GET", f"/rest/v1/guests?id=eq.{gid}&select=*")
    if rows:
        row = rows[0]
        return {"name": row.get("name"), "difficulty": row.get("difficulty") or "beginner", "progress": row.get("progress") or {}}
    return {}


def save_guest(gid, profile):
    row = {"id": gid, "name": (profile.get("name") or "")[:40] or None, "difficulty": profile.get("difficulty", "beginner"),
           "progress": profile.get("progress") or {}, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _call("POST", "/rest/v1/guests?on_conflict=id", [row], headers={"Prefer": "resolution=merge-duplicates,return=minimal"})


# ---- the learner's own Claude (an Anthropic API key, sealed with CQ_SECRET_KEY) ------------
def save_claude_key(user, sealed, hint):
    """Store (or with sealed=None, remove) a learner's key. Only the sealed
    form and its last 4 characters ever reach the database."""
    row = {"user_id": user["id"], "email": user.get("email"), "name": user["name"],
           "claude_key": sealed, "claude_key_hint": hint}
    _call("POST", "/rest/v1/profiles?on_conflict=user_id", [row], headers={"Prefer": "resolution=merge-duplicates,return=minimal"})


def sealed_claude_key(user):
    rows = _call("GET", f"/rest/v1/profiles?user_id=eq.{user['id']}&select=claude_key")
    return (rows[0].get("claude_key") if rows else None) or None


def save_profile(user, profile):
    # (the Claude key columns are left alone: saving progress never touches them)
    row = {"user_id": user["id"], "email": user.get("email"), "name": profile.get("name") or user["name"],
           "avatar": user.get("avatar"), "difficulty": profile.get("difficulty", "beginner"),
           "progress": profile.get("progress") or {}, "parts": profile.get("parts") or [],
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _call("POST", "/rest/v1/profiles?on_conflict=user_id", [row],
          headers={"Prefer": "resolution=merge-duplicates,return=minimal"})


# ---- shared lessons ------------------------------------------------------------------------
def save_lesson(lesson_id, user=None):
    """Publish a saved lesson folder (lesson.json, diagram.json, code.ino)."""
    folder = LESSONS_ROOT / lesson_id
    data = json.loads((folder / "lesson.json").read_text())
    row = {"id": lesson_id, "title": data.get("title", lesson_id), "description": data.get("description", ""),
           "source_url": (data.get("source") or {}).get("url"),
           "creator_id": user["id"] if user else None, "creator_name": user["name"] if user else None,
           "data": data, "diagram": json.loads((folder / "diagram.json").read_text()),
           "code": (folder / "code.ino").read_text(),
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _call("POST", "/rest/v1/lessons?on_conflict=id", [row], headers={"Prefer": "resolution=merge-duplicates,return=minimal"})


_last_sync = [0.0]
_sync_lock = threading.Lock()
SYNC_SECONDS = 20


def sync_lessons(force=False):
    """Bring everyone's lessons down into lessons/ so the engine can load
    them like any other lesson. At most every SYNC_SECONDS. Returns the
    number written."""
    if not enabled():
        return 0
    with _sync_lock:
        if not force and time.time() - _last_sync[0] < SYNC_SECONDS:
            return 0
        _last_sync[0] = time.time()
        try:
            rows = _call("GET", "/rest/v1/lessons?select=id,data,diagram,code,creator_name,updated_at")
        except (urllib.error.URLError, OSError, ValueError):
            return 0
        written = 0
        for row in rows or []:
            lesson_id = row["id"]
            if not lesson_id or "/" in lesson_id or lesson_id.startswith("."):
                continue
            folder = LESSONS_ROOT / lesson_id
            data = {**(row.get("data") or {}), "id": lesson_id}
            if row.get("creator_name"):
                data["creator"] = row["creator_name"]
            text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            path = folder / "lesson.json"
            if path.exists() and path.read_text() == text:
                continue
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            (folder / "diagram.json").write_text(json.dumps(row.get("diagram") or {}, indent=2) + "\n")
            code = row.get("code") or ""
            (folder / "code.ino").write_text(code if code.endswith("\n") else code + "\n")
            written += 1
        return written
