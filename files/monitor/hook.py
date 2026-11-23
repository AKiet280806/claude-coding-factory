#!/usr/bin/env python3
"""Claude Code hook: append a compact event to the agent monitor log.

Does nothing unless the monitor is on (the file $MONITOR_DIR/on exists), so it costs
one stat() per hook when idle. Never prints, never blocks: any error exits 0.
"""
import json, os, sys, time
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")

DIR = os.environ.get("MONITOR_DIR") or os.path.join(CLAUDE_DIR, "monitor")

def short(v, n=160):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"

def summarize_input(tool, ti):
    if not isinstance(ti, dict):
        return ""
    if tool in ("Agent", "Task"):
        return f'{ti.get("subagent_type") or "general"}: {ti.get("description") or ti.get("prompt", "")}'
    for k in ("file_path", "path", "pattern", "command", "url", "query", "skill"):
        if ti.get(k):
            return f"{k}={ti[k]}"
    return json.dumps(ti, ensure_ascii=False)

def main():
    if not os.path.exists(os.path.join(DIR, "on")):
        return
    d = json.load(sys.stdin)
    ev = d.get("hook_event_name", "")
    tool = d.get("tool_name", "")
    out = {"t": time.time(), "ev": ev, "session": (d.get("session_id") or "")[:8],
           "agent_id": d.get("agent_id", ""), "agent_type": d.get("agent_type", "")}
    if tool:
        out["tool"] = tool
        inp = summarize_input(tool, d.get("tool_input"))
        cwd = d.get("cwd") or ""
        if cwd:
            inp = inp.replace(cwd.rstrip("/") + "/", "").replace(cwd, ".")
        out["input"] = short(inp.replace(os.path.expanduser("~"), "~"))
        out["tool_use_id"] = d.get("tool_use_id", "")
    if "duration_ms" in d:
        out["ms"] = d["duration_ms"]
    if ev == "PostToolUseFailure":
        out["error"] = short(d.get("error") or d.get("tool_response") or "", 200)
    if ev == "PostToolUse" and (tool.lower() == "advisor" or tool in ("Agent", "Task")):
        out["result"] = short(d.get("tool_response") or "", 400)
    if ev == "SubagentStop":
        out["result"] = short(d.get("last_assistant_message") or "", 300)
    if ev == "UserPromptSubmit":
        out["prompt"] = short(d.get("prompt") or "", 160)
    os.makedirs(DIR, exist_ok=True)
    lines = [out]
    # Token usage and advisor calls fire no hook, so read them from the transcripts
    # (new lines only): the main one after each main-session step, a subagent's own
    # transcript when it stops.
    import fcntl                      # parallel subagents fire hooks at the same time
    lock = open(os.path.join(DIR, ".lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    # A subagent's last message lands in its transcript after SubagentStop fires, so
    # remember each subagent transcript and rescan it on later main-session steps.
    subs_file = os.path.join(DIR, "subagent_transcripts.json")
    try:
        subs = json.load(open(subs_file))
    except Exception:
        subs = {}
    if ev == "SubagentStop" and d.get("agent_transcript_path"):
        subs[d["agent_transcript_path"]] = {"type": d.get("agent_type", ""), "session": out["session"], "t": time.time()}
    rescan = ev in ("PostToolUse", "PostToolUseFailure", "Stop", "SubagentStop") and not d.get("agent_id")
    if rescan:
        for p, info in list(subs.items()):
            if time.time() - info["t"] > 1800 or not os.path.exists(p):
                subs.pop(p)          # stop watching after 30 minutes
                continue
            lines = scan_transcript(p, info["session"], "subagent", info["type"]) + lines
    json.dump(subs, open(subs_file, "w"))
    if ev in ("PostToolUse", "PostToolUseFailure", "Stop") and not d.get("agent_id") and d.get("transcript_path"):
        lines = scan_transcript(d["transcript_path"], out["session"], "main") + lines
    with open(os.path.join(DIR, "events.jsonl"), "a", encoding="utf-8") as f:
        for o in lines:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

FIELDS = ("in", "out", "cw5", "cw1h", "cr")

def tokens(u):
    cc = u.get("cache_creation") or {}
    cw1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    cw5 = cc.get("ephemeral_5m_input_tokens")
    if cw5 is None:
        cw5 = max(0, (u.get("cache_creation_input_tokens") or 0) - cw1h)
    return {"in": u.get("input_tokens") or 0, "out": u.get("output_tokens") or 0,
            "cw5": cw5 or 0, "cw1h": cw1h, "cr": u.get("cache_read_input_tokens") or 0}

def scan_transcript(path, session, role, agent_type=""):
    """Read new transcript lines; emit Usage deltas per message (and Advisor calls).

    One API message is written as several lines sharing message.id, each carrying the
    usage so far, so we remember the last totals per (message, model) and emit only
    the difference.
    """
    from datetime import datetime
    state_file = os.path.join(DIR, "transcript_state.json")
    try:
        state = json.load(open(state_file))
    except Exception:
        state = {}
    st = state.get(path, {"off": 0, "seen": [], "msgs": {}})
    found = []
    with open(path, encoding="utf-8") as f:
        f.seek(st["off"])
        for line in f:
            if '"usage"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            u = msg.get("usage")
            if rec.get("type") != "assistant" or not u or not msg.get("id"):
                continue
            try:
                t = datetime.fromisoformat(rec["timestamp"].replace("Z", "+00:00")).timestamp()
            except Exception:
                t = time.time()
            iters = u.get("iterations") or []
            parts = []   # (key, model, role, tokens)
            if iters:
                ex = {k: 0 for k in FIELDS}
                for it in iters:
                    if it.get("type") == "advisor_message":
                        continue
                    for k, v in tokens(it).items():
                        ex[k] += v
                parts.append(("x", msg.get("model", ""), role, ex))
                for n, it in enumerate(i for i in iters if i.get("type") == "advisor_message"):
                    parts.append((f"a{n}", it.get("model", ""), "advisor", tokens(it)))
            else:
                parts.append(("x", msg.get("model", ""), role, tokens(u)))
            for key, model, r, tk in parts:
                mk = f'{msg["id"]}:{key}'
                prev = st["msgs"].get(mk, {})
                delta = {k: max(0, tk[k] - prev.get(k, 0)) for k in FIELDS}
                st["msgs"][mk] = tk
                if any(delta.values()):
                    prompt = tk["in"] + tk["cw5"] + tk["cw1h"] + tk["cr"]
                    found.append({"t": t, "ev": "Usage", "session": session, "agent_id": "",
                                  "agent_type": agent_type, "role": r, "model": model,
                                  "long": prompt > 100_000, **delta})
            # advisor calls (once per server_tool_use id)
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            adv = [i for i in iters if i.get("type") == "advisor_message"]
            for n, tid in enumerate(b.get("id") for b in content
                                    if b.get("type") == "server_tool_use" and b.get("name") == "advisor"):
                if tid in st["seen"]:
                    continue
                st["seen"].append(tid)
                it = adv[n] if n < len(adv) else {}
                found.append({"t": t, "ev": "Advisor", "session": session, "agent_id": "", "agent_type": "",
                              "model": it.get("model", ""), "tokens_in": it.get("input_tokens", 0),
                              "tokens_out": it.get("output_tokens", 0)})
        st["off"] = f.tell()
    st["seen"] = st["seen"][-200:]
    st["msgs"] = dict(list(st["msgs"].items())[-400:])
    state[path] = st
    if len(state) > 200:                      # forget the oldest transcripts
        state = dict(list(state.items())[-200:])
    json.dump(state, open(state_file, "w"))
    return found

try:
    main()
except Exception:
    pass
sys.exit(0)
