#!/usr/bin/env python3
"""Write a synthetic events.jsonl so the monitor can be shown without real data.

    python3 docs/make_demo_events.py /tmp/demo-monitor
    MONITOR_DIR=/tmp/demo-monitor python3 files/monitor/server.py --port 8792
"""
import json, os, sys, time

out_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo-monitor"
os.makedirs(out_dir, exist_ok=True)
t = time.time() - 50           # the story ends "now", so the UI shows it as live
S = "7c2e91ab"
ev = []

def e(dt, **kw):
    global t
    t += dt
    ev.append({"t": round(t, 3), "session": S, "agent_id": "", "agent_type": "", **kw})

def usage(dt, role, model, inp, out, cr, cw1h=0, agent_type=""):
    e(dt, ev="Usage", role=role, model=model, agent_type=agent_type,
      **{"in": inp, "out": out, "cw5": 0, "cw1h": cw1h, "cr": cr}, long=False)

def sub(dt, kind, aid, task, tool, result, secs):
    e(dt, ev="PreToolUse", tool="Agent", input=f"{kind}: {task}", tool_use_id=f"t{aid}")
    e(0.2, ev="SubagentStart", agent_id=aid, agent_type=kind)
    e(0.8, ev="PreToolUse", agent_id=aid, agent_type=kind, tool=tool[0], input=tool[1])
    e(secs, ev="SubagentStop", agent_id=aid, agent_type=kind, result=result)
    usage(0.1, "subagent", "claude-haiku-5-5", 40, 900, 38000, 12000, kind)

e(0, ev="UserPromptSubmit", prompt="Checkout total is off by a cent for some carts. Find the cause, fix it, and make sure nothing else breaks.")
usage(1.5, "main", "claude-sonnet-5-5", 12, 600, 0, 61000)
e(2, ev="Advisor", model="claude-opus-5-5", tokens_in=64000, tokens_out=820)
usage(0.1, "advisor", "claude-opus-5-5", 64000, 820, 0)
sub(3, "search", "a1", "Map the pricing and checkout modules", ("Glob", "pattern=src/**/pricing*"),
    "Pricing lives in src/pricing/{money,cart,discounts}.py; checkout calls cart.total().", 6.1)
sub(0.3, "grep", "a2", "Find every caller of round_money", ("Grep", "pattern=round_money"),
    "round_money is called in cart.py:41, discounts.py:18, refunds.py:9 and invoice.py:27.", 4.8)
e(1, ev="Decide", q="Which subagent fits the remaining exploration best?", options=["search", "grep"], choice="grep", conf=0.91, ms=640)
e(2, ev="PreToolUse", tool="Edit", input="file_path=src/pricing/money.py")
e(1, ev="PreToolUse", tool="Bash", input="command=python3 -m pytest tests/pricing -q")
e(4, ev="PostToolUseFailure", tool="Bash", error="ModuleNotFoundError: No module named 'src'")
e(0.2, ev="Decide", q="Should this failed shell command be retried as-is, retried after fixing something, or stopped?", options=["retry_same", "fix_then_retry", "stop_and_ask"], choice="fix_then_retry", conf=0.96, ms=710)
e(1, ev="Decide", q="Which file should be edited first: money.py or cart.py?", options=["money.py", "cart.py"], choice="money.py", conf=0.88, ms=590)
usage(0.5, "main", "claude-sonnet-5-5", 30, 2400, 180000, 9000)
sub(2, "test", "a3", "Run the pricing and checkout tests", ("Bash", "command=PYTHONPATH=. python3 -m pytest -q"),
    "41 passed, 0 failed. New test test_half_up_rounding passes; it failed before the fix.", 9.4)
e(1, ev="Decide", q="Should this failed shell command be retried?", options=["retry_same", "stop_and_ask"], choice="retry_same", conf=0.55, ms=600)
usage(0.5, "main", "claude-sonnet-5-5", 20, 1800, 240000, 6000)
# audit still running in the screenshot
e(2, ev="PreToolUse", tool="Agent", input="audit: Review the final diff against the acceptance criteria", tool_use_id="ta4")
e(0.2, ev="SubagentStart", agent_id="a4", agent_type="audit")
e(0.6, ev="PreToolUse", agent_id="a4", agent_type="audit", tool="Read", input="file_path=src/pricing/money.py")

with open(os.path.join(out_dir, "events.jsonl"), "w") as f:
    for x in ev:
        f.write(json.dumps(x) + "\n")
open(os.path.join(out_dir, "on"), "w").close()
print(f"wrote {len(ev)} demo events to {out_dir}/events.jsonl")
