#!/usr/bin/env python3
"""Remove the coding factory setup from ~/.claude (or $CLAUDE_CONFIG_DIR).

    python3 uninstall.py --dry-run
    python3 uninstall.py                  # keeps decider.env and your model settings
    python3 uninstall.py --reset-models   # also removes model / advisorModel
    python3 uninstall.py --purge-key      # also deletes decider.env
"""
import argparse, json, os, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install import START, END, MODELS, claude_dir, plan_files, shown, udiff  # noqa: E402

OUR_CMDS = ("/monitor/hook.py", "/bin/decide-hook", "/bin/delegate-hook", "/bin/done-gate", "/bin/guard-hook")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset-models", action="store_true")
    ap.add_argument("--purge-key", action="store_true")
    args = ap.parse_args()
    cd = claude_dir()
    sp, mp = os.path.join(cd, "settings.json"), os.path.join(cd, "CLAUDE.md")
    cur_s = json.load(open(sp)) if os.path.exists(sp) else {}
    new_s = json.loads(json.dumps(cur_s))
    for ev, groups in list(new_s.get("hooks", {}).items()):
        kept = []
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if not any(c in h.get("command", "") for c in OUR_CMDS)]
            if g["hooks"]:
                kept.append(g)
        new_s["hooks"][ev] = kept
        if not kept:
            del new_s["hooks"][ev]
    allow = new_s.get("permissions", {}).get("allow", [])
    new_s.get("permissions", {})["allow"] = [a for a in allow if not a.endswith("/bin/decide:*)")] if allow else allow
    if new_s.get("hooks") == {}:
        new_s.pop("hooks")
    perms = new_s.get("permissions")
    if isinstance(perms, dict):
        if not perms.get("allow"):
            perms.pop("allow", None)
        if not perms:
            new_s.pop("permissions")
    if args.reset_models:
        for k, v in MODELS.items():
            if new_s.get(k) == v:
                del new_s[k]
    cur_m = open(mp).read() if os.path.exists(mp) else ""
    new_m = cur_m
    if START in cur_m and END in cur_m:
        a, b = cur_m.index(START), cur_m.index(END) + len(END)
        new_m = (cur_m[:a].rstrip("\n") + "\n" + cur_m[b:].lstrip("\n")).strip("\n") + "\n"
        if not new_m.strip():
            new_m = ""
    files = [dst for _, dst, _ in plan_files(cd) if os.path.exists(dst)]
    extra = [os.path.join(cd, p) for p in ("monitor", "state/delegate_streak.json")]
    if args.purge_key:
        extra.append(os.path.join(cd, "decider.env"))

    print(udiff(json.dumps(cur_s, indent=2) + "\n", json.dumps(new_s, indent=2) + "\n", "settings.json") or "settings.json: no change\n")
    print(udiff(cur_m, new_m, "CLAUDE.md") or "CLAUDE.md: no change\n")
    for p in files + [e for e in extra if os.path.exists(e)]:
        print(f"  remove {shown(p)}")
    if args.dry_run:
        print("\nDry run: nothing changed.")
        return
    bk = os.path.join(cd, "backups", "coding-factory-uninstall-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bk, exist_ok=True)
    for p in (sp, mp):
        if os.path.exists(p):
            shutil.copy2(p, bk)
    with open(sp, "w") as f:
        f.write(json.dumps(new_s, indent=2, ensure_ascii=False) + "\n")
    if new_m.strip():
        with open(mp, "w") as f:
            f.write(new_m)
    elif os.path.exists(mp):
        os.remove(mp)                         # it only held our block
    for p in files:
        os.remove(p)
    for p in extra:
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    for d in (os.path.join(cd, "skills", "research-playbook"), os.path.join(cd, "skills"),
              os.path.join(cd, "agents"), os.path.join(cd, "bin"), os.path.join(cd, "state")):
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)                       # only directories left empty by this uninstall
    print(f"\nUninstalled. Backup of settings.json and CLAUDE.md: {shown(bk)}")


if __name__ == "__main__":
    main()
