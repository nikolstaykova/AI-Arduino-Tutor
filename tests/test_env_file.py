"""bench_server reads secrets from a local, git-ignored .env — without ever
overriding what's already in the real environment."""
import os
import subprocess

import bench_server


def test_env_file_loads_keys_and_never_overrides(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nCLAUDE_CODE_OAUTH_TOKEN="fake-token-123"\nexport CQ_CLAUDE_MODEL=opus\nALREADY=from-file\n\n')
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("CQ_CLAUDE_MODEL", raising=False)
    monkeypatch.setenv("ALREADY", "from-shell")
    loaded = bench_server.load_env(env)
    assert sorted(loaded) == ["CLAUDE_CODE_OAUTH_TOKEN", "CQ_CLAUDE_MODEL"]
    assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "fake-token-123" and os.environ["CQ_CLAUDE_MODEL"] == "opus"
    assert os.environ["ALREADY"] == "from-shell"
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN"); monkeypatch.delenv("CQ_CLAUDE_MODEL")


def test_missing_env_file_is_fine(tmp_path):
    assert bench_server.load_env(tmp_path / "nope.env") == []


def test_dot_env_is_git_ignored():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=root)
    assert r.returncode == 0
