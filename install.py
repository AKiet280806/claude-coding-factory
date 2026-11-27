#!/usr/bin/env python3
"""Install the Claude Code "coding factory" setup into ~/.claude (or $CLAUDE_CONFIG_DIR).

    python3 install.py --dry-run     # show every change as a diff, write nothing
    python3 install.py               # install (backs up everything it touches)
    python3 install.py --keep-models # don't set model / advisorModel

Safe to run again: hook entries are added once, the CLAUDE.md block is replaced in
place, and an existing decider.env (your API key) is never overwritten.
"""
import argparse, difflib, json, os, shutil, stat, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "files")
START, END = "<!-- coding-factory:start -->", "<!-- coding-factory:end -->"
MODELS = {"model": "claude-sonnet-5-5", "advisorModel": "claude-opus-5-5"}


def claude_dir():
    return os.path.abspath(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"))


def shown(path):
    """Path as written into hook commands: ~/... when under $HOME."""
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def hook_entries(cd):
    b, m = shown(os.path.join(cd, "bin")), shown(os.path.join(cd, "monitor"))
    monitor = f"python3 -I {m}/hook.py"
    entries = {ev: [monitor] for ev in ("UserPromptSubmit", "PreToolUse", "PostToolUse",
                                         "PostToolUseFailure", "SubagentStart", "SubagentStop", "Stop")}
    entries["PostToolUseFailure"].append(f"python3 -I {b}/decide-hook")
    entries["PreToolUse"].append(f"python3 -I {b}/delegate-hook")
    entries["PreToolUse"].append((f"python3 -I {b}/guard-hook", "Bash", 20))
    entries["UserPromptSubmit"].append(f"python3 -I {b}/delegate-hook")
    entries["Stop"].append(f"python3 -I {b}/done-gate")
    return entries, f"Bash({b}/decide:*)"


def new_settings(cur, cd, keep_models):
    s = json.loads(json.dumps(cur))
    if not keep_models:
        s.update(MODELS)
    entries, allow = hook_entries(cd)
    hooks = s.setdefault("hooks", {})
    for ev, cmds in entries.items():
        lst = hooks.setdefault(ev, [])
        have = {h.get("command") for g in lst for h in g.get("hooks", [])}
        for item in cmds:
            c, matcher, timeout = (item, None, 15) if isinstance(item, str) else item
            if c not in have:
                group = {"hooks": [{"type": "command", "command": c, "timeout": timeout}]}
                lst.append({"matcher": matcher, **group} if matcher else group)
    al = s.setdefault("permissions", {}).setdefault("allow", [])
    if allow not in al:
        al.append(allow)
    return s


def new_claude_md(cur):
    block = f"{START}\n" + open(os.path.join(FILES, "CLAUDE.factory.md")).read().strip() + f"\n{END}\n"
    if START in cur and END in cur:
        a, b = cur.index(START), cur.index(END) + len(END)
        return cur[:a] + block.rstrip("\n") + cur[b:]
    return (cur.rstrip("\n") + "\n\n" if cur.strip() else "") + block


def plan_files(cd):
    """(src, dst, executable) for every packaged file."""
    out = []
    for sub, mode_x in (("agents", False), ("bin", True), ("monitor", None), ("skills", False)):
        root = os.path.join(FILES, sub)
        for dp, _, fs in os.walk(root):
            for f in fs:
                src = os.path.join(dp, f)
                dst = os.path.join(cd, sub, os.path.relpath(src, root))
                x = mode_x if mode_x is not None else f.endswith(".py")
                out.append((src, dst, x))
    return out


def udiff(a, b, name):
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{name}", f"b/{name}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-models", action="store_true")
    args = ap.parse_args()
    cd = claude_dir()
    sp, mp = os.path.join(cd, "settings.json"), os.path.join(cd, "CLAUDE.md")
    cur_s = json.load(open(sp)) if os.path.exists(sp) else {}
    cur_m = open(mp).read() if os.path.exists(mp) else ""
    new_s, new_m = new_settings(cur_s, cd, args.keep_models), new_claude_md(cur_m)
    files = plan_files(cd)
    env_dst = os.path.join(cd, "decider.env")

    print(f"Target: {cd}\n")
    print(udiff(json.dumps(cur_s, indent=2) + "\n", json.dumps(new_s, indent=2) + "\n", "settings.json") or "settings.json: no change\n")
    print(udiff(cur_m, new_m, "CLAUDE.md") or "CLAUDE.md: no change\n")
    for src, dst, _ in files:
        state = "new" if not os.path.exists(dst) else ("same" if open(src, "rb").read() == open(dst, "rb").read() else "UPDATE")
        print(f"  {state:6s} {shown(dst)}")
    print(f"  {'keep' if os.path.exists(env_dst) else 'new':6s} {shown(env_dst)} (API key file, never overwritten)")
    if args.dry_run:
        print("\nDry run: nothing written.")
        return

    bk = os.path.join(cd, "backups", "coding-factory-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bk, exist_ok=True)
    for p in (sp, mp):
        if os.path.exists(p):
            shutil.copy2(p, bk)
    for _, dst, _ in files:
        if os.path.exists(dst):
            rel = os.path.relpath(dst, cd)
            os.makedirs(os.path.dirname(os.path.join(bk, rel)), exist_ok=True)
            shutil.copy2(dst, os.path.join(bk, rel))
    for src, dst, x in files:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if x:
            os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if not os.path.exists(env_dst):
        shutil.copy2(os.path.join(HERE, "decider.env.example"), env_dst)
        os.chmod(env_dst, 0o600)
    with open(sp, "w") as f:
        f.write(json.dumps(new_s, indent=2, ensure_ascii=False) + "\n")
    with open(mp, "w") as f:
        f.write(new_m)
    print(f"\nInstalled. Backup: {shown(bk)}")
    print(f"Next: put an OpenRouter or Perplexity key in {shown(env_dst)}, then start a new Claude Code session.")
    print(f"Watch it work: {shown(os.path.join(cd, 'bin', 'agent-monitor'))}  ->  http://localhost:8790")


if __name__ == "__main__":
    main()
