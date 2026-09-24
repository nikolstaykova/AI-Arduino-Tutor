"""Accounts and shared lessons (core/cloud.py) against a fake Supabase, the
"might be the same" check (core/similar.py), and unique lesson ids."""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import bench_server
from core import cloud, lesson_gen, similar

USERS = {"tok-nikol": {"id": "11111111-1111-1111-1111-111111111111", "email": "nikol@example.com", "user_metadata": {"full_name": "Nikol", "avatar_url": "https://x/n.png"}},
         "tok-mert": {"id": "22222222-2222-2222-2222-222222222222", "email": "mert@example.com", "user_metadata": {"full_name": "Mert"}}}


class FakeSupabase(BaseHTTPRequestHandler):
    tables = {"profiles": {}, "lessons": {}}

    def log_message(self, *a):
        pass

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/auth/v1/user":
            token = self.headers["Authorization"].split(" ", 1)[1]
            return self._json(200, USERS[token]) if token in USERS else self._json(401, {"msg": "bad token"})
        assert self.headers["apikey"] == "service-key"            # only the server's key reads tables
        table = url.path.rsplit("/", 1)[1]
        q = urllib.parse.parse_qs(url.query)
        rows = list(self.tables[table].values())
        if "user_id" in q:
            rows = [r for r in rows if r["user_id"] == q["user_id"][0].removeprefix("eq.")]
        return self._json(200, rows)

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        assert self.headers["apikey"] == "service-key"
        table, key = url.path.rsplit("/", 1)[1], urllib.parse.parse_qs(url.query)["on_conflict"][0]
        for row in json.loads(self.rfile.read(int(self.headers["Content-Length"]))):
            self.tables[table][row[key]] = {**self.tables[table].get(row[key], {}), **row}
        self.send_response(201); self.send_header("Content-Length", "0"); self.end_headers()


@pytest.fixture
def supabase(monkeypatch, tmp_path):
    FakeSupabase.tables = {"profiles": {}, "lessons": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSupabase)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("SUPABASE_URL", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    cloud._users.clear(); cloud._last_sync[0] = 0
    yield FakeSupabase.tables
    bench_server._request.user = None      # never leak a signed-in user into other tests
    server.shutdown()


def as_user(token):
    bench_server._request.user = cloud.user_from_token(token) if token else None


def test_accounts_are_off_without_the_keys(monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert not cloud.enabled() and cloud.public_config() == {"enabled": False, "url": None, "anon_key": None}
    assert cloud.user_from_token("anything") is None


def test_the_page_gets_the_public_key_never_the_service_key(supabase):
    cfg = cloud.public_config()
    assert cfg["enabled"] and cfg["anon_key"] == "anon-key" and "service-key" not in json.dumps(cfg)


def test_a_google_token_becomes_a_user_and_a_bad_one_doesnt(supabase):
    u = cloud.user_from_token("tok-nikol")
    assert u["name"] == "Nikol" and u["avatar"] == "https://x/n.png" and u["email"] == "nikol@example.com"
    assert cloud.user_from_token("forged") is None


def test_each_account_keeps_its_own_progress(supabase):
    as_user("tok-nikol")
    bench_server._save_progress({**bench_server.core.progress.empty_progress(), "xp": 155})
    as_user("tok-mert")
    assert bench_server._load_progress()["xp"] == 0
    bench_server._save_progress({**bench_server.core.progress.empty_progress(), "xp": 40})
    as_user("tok-nikol")
    assert bench_server._load_progress()["xp"] == 155
    assert bench_server.api_profile({})["name"] == "Nikol"
    assert len(supabase["profiles"]) == 2


def test_signed_out_on_a_hosted_app_cannot_spend_claude(supabase):
    as_user(None)
    assert bench_server.api_generate({"request": "a traffic light"})[1] == 401
    assert bench_server.api_guide({"url": "https://example.com"})[1] == 401


def test_a_lesson_mert_creates_shows_up_for_everyone(supabase, tmp_path, monkeypatch):
    # Mert's server saves and publishes a lesson …
    src = tmp_path / "mert"; (src / "gen-night-light").mkdir(parents=True)
    (src / "gen-night-light" / "lesson.json").write_text(json.dumps({"id": "gen-night-light", "title": "Night Light", "description": "LED on in the dark", "source": {"url": "https://example.com/night"}}))
    (src / "gen-night-light" / "diagram.json").write_text("{}")
    (src / "gen-night-light" / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    monkeypatch.setattr(cloud, "LESSONS_ROOT", src)
    cloud.save_lesson("gen-night-light", cloud.user_from_token("tok-mert"))
    row = supabase["lessons"]["gen-night-light"]
    assert row["creator_name"] == "Mert" and row["source_url"] == "https://example.com/night"
    # … and another server (yours) syncs it down, signed "made by Mert"
    mine = tmp_path / "mine"; mine.mkdir()
    monkeypatch.setattr(cloud, "LESSONS_ROOT", mine)
    assert cloud.sync_lessons(force=True) == 1
    data = json.loads((mine / "gen-night-light" / "lesson.json").read_text())
    assert data["creator"] == "Mert" and (mine / "gen-night-light" / "code.ino").read_text().startswith("void setup")
    assert cloud.sync_lessons(force=True) == 0          # nothing new the second time


def test_two_people_making_the_same_lesson_never_overwrite_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr(lesson_gen, "LESSONS_ROOT", tmp_path)
    assert lesson_gen._free_id("gen-traffic-light") == "gen-traffic-light"
    (tmp_path / "gen-traffic-light").mkdir()
    assert lesson_gen._free_id("gen-traffic-light") == "gen-traffic-light-2"
    (tmp_path / "gen-traffic-light-2").mkdir()
    assert lesson_gen._free_id("gen-traffic-light") == "gen-traffic-light-3"


# ---- "this might be the same" --------------------------------------------------------------
LESSONS = [
    {"id": "gen-traffic-light", "title": "Traffic Light", "description": "Red, yellow and green LEDs cycle like a real traffic light."},
    {"id": "blink", "title": "Blink", "description": "Make the built-in LED blink.", "source": {"url": "https://docs.arduino.cc/built-in-examples/basics/Blink/"}},
    {"id": "gen-usb-flashlight", "title": "USB Flashlight: Five LEDs on USB Power", "description": "Five LEDs switched on and off",
     "source": {"url": "https://www.build-electronic-circuits.com/usb-flashlight/"}},
    {"id": "gen-fade-led", "title": "Fade an LED", "description": "PWM fades an LED in and out."},
]


@pytest.mark.parametrize("request_text, url, expected", [
    ("", "http://build-electronic-circuits.com/usb-flashlight?ref=share#top", "gen-usb-flashlight"),   # same page, other spelling
    ("https://docs.arduino.cc/built-in-examples/basics/Blink", None, "blink"),
    ("a traffic light", None, "gen-traffic-light"),
    ("stoplight with three leds", None, "gen-traffic-light"),
    ("make a flashlight", None, "gen-usb-flashlight"),
    ("fading led", None, "gen-fade-led"),
])
def test_it_finds_a_lesson_that_might_be_the_same(request_text, url, expected):
    matches = similar.find_similar(request_text, LESSONS, url=url)
    assert matches and matches[0]["id"] == expected and matches[0]["why"]


@pytest.mark.parametrize("request_text", ["a thermometer with a display", "an led", "a night light with a light sensor",
                                          "https://example.com/some-other-project"])
def test_it_stays_quiet_for_a_different_project(request_text):
    assert similar.find_similar(request_text, LESSONS) == []


def test_every_hand_made_lesson_links_the_tutorial_it_follows():
    for lid in ("blink", "digital-read-serial", "analog-read-serial"):
        data = json.loads((bench_server.ROOT / "lessons" / lid / "lesson.json").read_text())
        assert data["source"]["url"].startswith("https://docs.arduino.cc/built-in-examples/")


# ---- your own Claude: locked until connected, stored sealed, used only for you ------------
from core import secretbox

SECRET = "x" * 40
KEY = "sk-ant-api03-" + "A" * 40 + "wxyz"


def test_a_key_is_sealed_and_only_the_secret_opens_it(monkeypatch):
    monkeypatch.setenv("CQ_SECRET_KEY", SECRET)
    sealed = secretbox.seal(KEY)
    assert KEY not in sealed and "AAAA" not in sealed and secretbox.open_(sealed) == KEY
    assert secretbox.seal(KEY) != sealed                                       # fresh nonce each time
    tampered = sealed[:-3] + ("A" if sealed[-3] != "A" else "B") + sealed[-2:]
    with pytest.raises(ValueError):
        secretbox.open_(tampered)
    monkeypatch.setenv("CQ_SECRET_KEY", "y" * 40)
    with pytest.raises(ValueError):
        secretbox.open_(sealed)
    monkeypatch.delenv("CQ_SECRET_KEY")
    assert not secretbox.available()


@pytest.fixture
def claude_setup(supabase, monkeypatch):
    monkeypatch.setenv("CQ_SECRET_KEY", SECRET)
    monkeypatch.setenv("CQ_OWNER_EMAILS", "nikol@example.com")
    monkeypatch.setattr(bench_server, "_check_anthropic_key", lambda key: key == KEY)
    seen = []
    def fake_generate(request, inventory=None, **kw):
        seen.append(lesson_gen._user_key.get())
        return {"ok": False, "lesson_id": None, "attempts": [], "errors": ["(test)"]}
    monkeypatch.setattr(lesson_gen, "generate_lesson", fake_generate)
    return seen


def test_create_is_locked_until_you_connect_your_own_claude(claude_setup):
    as_user("tok-mert")
    body, status = bench_server.api_generate({"request": "a traffic light"})
    assert status == 403 and body["locked"] == "claude" and claude_setup == []
    assert bench_server.api_ai_status({})["claude"] == {"ready": False, "mode": "locked"}


def test_a_connected_key_is_stored_sealed_and_used_only_for_its_owner(claude_setup, supabase):
    as_user("tok-mert")
    assert bench_server.api_claude_key({"key": "sk-ant-wrong-" + "B" * 30})[1] == 400      # Anthropic says no
    assert bench_server.api_claude_key({"key": "hello"})[1] == 400                          # not a key at all
    assert bench_server.api_claude_key({"key": KEY}) == {"connected": True, "hint": "wxyz"}
    row = supabase["profiles"][USERS["tok-mert"]["id"]]
    assert KEY not in json.dumps(row) and row["claude_key_hint"] == "wxyz"                  # never in plain text
    bench_server._save_progress({**bench_server.core.progress.empty_progress(), "xp": 10})  # saving progress keeps the key
    assert supabase["profiles"][USERS["tok-mert"]["id"]]["claude_key"] == row["claude_key"]
    bench_server.api_generate({"request": "a traffic light"})
    assert claude_setup == [KEY]                                                             # Mert's lesson ran on Mert's key
    assert bench_server.api_ai_status({})["claude"] == {"ready": True, "mode": "own", "hint": "wxyz"}
    assert bench_server.api_claude_key({"remove": True}) == {"connected": False}
    assert supabase["profiles"][USERS["tok-mert"]["id"]]["claude_key"] is None
    assert bench_server.api_generate({"request": "x"})[1] == 403


def test_the_owner_may_use_the_servers_own_claude_nobody_else(claude_setup, monkeypatch):
    monkeypatch.setattr(lesson_gen, "backend", lambda: "claude-code")
    as_user("tok-nikol")                                   # in CQ_OWNER_EMAILS
    bench_server.api_generate({"request": "a traffic light"})
    assert claude_setup == [None]                          # ran on the server's own login
    assert bench_server.api_ai_status({})["claude"]["mode"] == "owner"
    as_user("tok-mert")
    assert bench_server.api_generate({"request": "a traffic light"})[1] == 403
    assert claude_setup == [None]


def test_keys_are_refused_when_the_server_cant_seal_them(claude_setup, monkeypatch):
    monkeypatch.delenv("CQ_SECRET_KEY")
    as_user("tok-mert")
    assert bench_server.api_claude_key({"key": KEY})[1] == 503


def test_locally_nothing_changes(monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"):
        monkeypatch.delenv(k, raising=False)
    bench_server._request.user = None
    assert bench_server._claude_for_request() == (None, None)
    assert bench_server.api_ai_status({})["claude"]["mode"] == "local"


def test_privacy_and_terms_pages_exist_for_google(monkeypatch):
    monkeypatch.setenv("CQ_CONTACT_EMAIL", "owner@example.com")
    privacy = bench_server._legal_page("privacy")
    assert "Privacy policy" in privacy and "mailto:owner@example.com" in privacy
    assert "Limited Use" in privacy and "encrypted" in privacy and "{{" not in privacy
    assert "Terms of use" in bench_server._legal_page("terms")
    monkeypatch.delenv("CQ_CONTACT_EMAIL")
    assert "person who runs this" in bench_server._legal_page("privacy")
    assert 'href="/privacy"' in (bench_server.PAGE).read_text()      # the homepage links it
