"""Generating lessons through the learner's own Claude Code login
(`claude -p` structured output) — with a fake CLI, so tests never spend usage."""
import json
import subprocess

import pytest

from core import lesson_gen


class FakeRun:
    def __init__(self, stdout, returncode=0):
        self.stdout, self.returncode, self.calls = stdout, returncode, []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, self.returncode, stdout=self.stdout, stderr="")


@pytest.fixture(autouse=True)
def cli_present(monkeypatch):
    monkeypatch.setattr(lesson_gen.shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)


def test_structured_output_is_returned_and_the_call_is_locked_down():
    run = FakeRun(json.dumps({"is_error": False, "subtype": "success", "result": "{}", "structured_output": {"a": 1}}))
    data, raw = lesson_gen._call_claude_code("SYSTEM", [{"role": "user", "content": "hi"}], {"type": "object"}, run=run)
    assert data == {"a": 1} and json.loads(raw) == {"a": 1}
    cmd, kw = run.calls[0]
    assert cmd[:2] == ["/usr/local/bin/claude", "-p"]
    assert cmd[cmd.index("--json-schema") + 1] == '{"type": "object"}'
    assert cmd[cmd.index("--system-prompt") + 1] == "SYSTEM"
    assert cmd[cmd.index("--tools") + 1] == ""              # no tools: it only writes the lesson
    assert "--no-session-persistence" in cmd
    assert kw["input"] == "hi" and kw["cwd"] != str(lesson_gen.LESSONS_ROOT.parent)


def test_repair_conversation_is_folded_into_one_prompt():
    text = lesson_gen._flatten([{"role": "user", "content": "Write a lesson"},
                                {"role": "assistant", "content": "{draft}"},
                                {"role": "user", "content": "Fix: pin 13 missing"}])
    assert text.index("Write a lesson") < text.index("{draft}") < text.index("Fix: pin 13 missing")
    assert "previous answer" in text


def test_not_logged_in_is_ai_unavailable():
    run = FakeRun(json.dumps({"is_error": True, "result": "Invalid API key · Please run /login"}))
    with pytest.raises(lesson_gen.AIUnavailable):
        lesson_gen._call_claude_code("S", [{"role": "user", "content": "x"}], {}, run=run)


def test_other_failures_are_plain_errors():
    run = FakeRun(json.dumps({"is_error": True, "subtype": "error_max_turns", "result": "stopped"}))
    with pytest.raises(RuntimeError) as err:
        lesson_gen._call_claude_code("S", [{"role": "user", "content": "x"}], {}, run=run)
    assert not isinstance(err.value, lesson_gen.AIUnavailable)


def test_backend_choice(monkeypatch):
    monkeypatch.delenv("CQ_AI_BACKEND", raising=False)
    monkeypatch.setattr(lesson_gen, "_api_ready", lambda: False)
    assert lesson_gen.backend() == "claude-code"
    monkeypatch.setattr(lesson_gen, "_api_ready", lambda: True)
    assert lesson_gen.backend() == "api"
    monkeypatch.setenv("CQ_AI_BACKEND", "claude-code")
    assert lesson_gen.backend() == "claude-code"
    monkeypatch.setenv("CQ_AI_BACKEND", "none")
    assert lesson_gen.backend() is None
    monkeypatch.delenv("CQ_AI_BACKEND")
    monkeypatch.setattr(lesson_gen, "_api_ready", lambda: False)
    monkeypatch.setattr(lesson_gen.shutil, "which", lambda name: None)
    assert lesson_gen.backend() is None
    with pytest.raises(lesson_gen.AIUnavailable):
        lesson_gen._call_model("S", [{"role": "user", "content": "x"}], {})
