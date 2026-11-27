"""Install / uninstall round trips in a throwaway HOME.  Run: python3 -m pytest -q"""
import json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(home, script, *args):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
    env["HOME"] = str(home)
    return subprocess.run([sys.executable, "-I", str(ROOT / script), *args],
                          env=env, capture_output=True, text=True, check=True)


def setup_home(tmp_path):
    cd = tmp_path / ".claude"
    (cd / "agents").mkdir(parents=True)
    (cd / "agents" / "mine.md").write_text("# my agent\n")
    (cd / "settings.json").write_text(json.dumps({
        "theme": "dark",
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "my-stop-hook.sh"}]}]}}))
    (cd / "CLAUDE.md").write_text("# My rules\n- Always use tabs.\n")
    return cd


def commands(settings, event):
    return [h["command"] for g in settings["hooks"].get(event, []) for h in g["hooks"]]


def test_dry_run_writes_nothing(tmp_path):
    cd = setup_home(tmp_path)
    before = (cd / "settings.json").read_text()
    out = run(tmp_path, "install.py", "--dry-run").stdout
    assert "Dry run: nothing written." in out
    assert (cd / "settings.json").read_text() == before
    assert not (cd / "bin").exists()


def test_install_twice_is_idempotent_and_keeps_user_config(tmp_path):
    cd = setup_home(tmp_path)
    run(tmp_path, "install.py")
    run(tmp_path, "install.py")
    s = json.loads((cd / "settings.json").read_text())
    assert commands(s, "Stop") == ["my-stop-hook.sh",
                                   "python3 -I ~/.claude/monitor/hook.py",
                                   "python3 -I ~/.claude/bin/done-gate"]
    pre = [(g.get("matcher"), h["command"]) for g in s["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert pre.count(("Bash", "python3 -I ~/.claude/bin/guard-hook")) == 1
    assert s["theme"] == "dark"
    assert s["model"] == "claude-sonnet-5-5" and s["advisorModel"] == "claude-opus-5-5"
    assert s["permissions"]["allow"] == ["Bash(ls:*)", "Bash(~/.claude/bin/decide:*)"]
    md = (cd / "CLAUDE.md").read_text()
    assert "Always use tabs." in md and md.count("coding-factory:start") == 1
    assert oct((cd / "decider.env").stat().st_mode & 0o777) == "0o600"
    for f in ("decide", "decide-hook", "delegate-hook", "done-gate", "guard-hook", "agent-monitor"):
        assert os.access(cd / "bin" / f, os.X_OK), f


def test_keep_models(tmp_path):
    cd = setup_home(tmp_path)
    run(tmp_path, "install.py", "--keep-models")
    assert "model" not in json.loads((cd / "settings.json").read_text())


def test_existing_key_file_is_never_overwritten(tmp_path):
    cd = setup_home(tmp_path)
    (cd / "decider.env").write_text("OPENROUTER_API_KEY=keep-me\n")
    run(tmp_path, "install.py")
    assert (cd / "decider.env").read_text() == "OPENROUTER_API_KEY=keep-me\n"


def test_uninstall_restores_original(tmp_path):
    cd = setup_home(tmp_path)
    original = json.loads((cd / "settings.json").read_text())
    run(tmp_path, "install.py")
    run(tmp_path, "uninstall.py", "--reset-models", "--purge-key")
    assert json.loads((cd / "settings.json").read_text()) == original
    assert (cd / "CLAUDE.md").read_text() == "# My rules\n- Always use tabs.\n"
    left = sorted(p.relative_to(cd).as_posix() for p in cd.rglob("*") if "backups" not in p.parts)
    assert left == ["CLAUDE.md", "agents", "agents/mine.md", "settings.json"]


def test_installed_hooks_run_quietly(tmp_path):
    cd = setup_home(tmp_path)
    run(tmp_path, "install.py")
    env = dict(os.environ, HOME=str(tmp_path))
    env.pop("CLAUDE_CONFIG_DIR", None)
    for script, payload in (
            ("bin/done-gate", {"hook_event_name": "Stop", "transcript_path": "/nonexistent"}),
            ("bin/delegate-hook", {"hook_event_name": "PreToolUse", "session_id": "s",
                                   "tool_name": "Grep", "tool_input": {"pattern": "x"}}),
            ("bin/decide-hook", {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
                                 "tool_input": {"command": "x"}, "error": "boom"}),
            ("bin/guard-hook", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}),
            ("monitor/hook.py", {"hook_event_name": "Stop"})):
        p = subprocess.run([sys.executable, "-I", str(cd / script)], input=json.dumps(payload),
                           env=env, capture_output=True, text=True)
        assert p.returncode == 0 and p.stdout == "", (script, p.stdout, p.stderr)

