#!/usr/bin/env python3
"""Agent monitor: streams $MONITOR_DIR/events.jsonl to a live page.

Usage: python3 server.py [--port 8790]   then open http://localhost:8790
Starting the server turns logging on ($MONITOR_DIR/on); Ctrl+C turns it off.
"""
import json, os, signal, sys, time
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.environ.get("MONITOR_DIR") or os.path.join(CLAUDE_DIR, "monitor")
LOG = os.path.join(DIR, "events.jsonl")
FLAG = os.path.join(DIR, "on")
BACKLOG = 2000

def config():
    try:
        s = json.load(open(os.path.join(CLAUDE_DIR, "settings.json")))
    except Exception:
        s = {}
    agents = {}
    adir = os.path.join(CLAUDE_DIR, "agents")
    for f in sorted(os.listdir(adir)) if os.path.isdir(adir) else []:
        if f.endswith(".md"):
            head = open(os.path.join(adir, f), encoding="utf-8").read().split("---")[1:2]
            meta = dict(l.split(":", 1) for l in (head[0].strip().splitlines() if head else []) if ":" in l)
            agents[meta.get("name", f[:-3]).strip()] = {k.strip(): v.strip() for k, v in meta.items()}
    dmodel = "?"
    try:
        for line in open(os.path.join(CLAUDE_DIR, "decider.env")):
            if line.startswith("DECIDER_MODEL=") and line.strip() != "DECIDER_MODEL=":
                dmodel = line.split("=", 1)[1].strip()
    except Exception:
        pass
    if dmodel == "?":
        dmodel = "perplexity/pplx-decider-v1.3:free"
    try:
        pricing = json.load(open(os.path.join(HERE, "pricing.json")))
    except Exception:
        pricing = {}
    return {"model": s.get("model", "?"), "advisor": s.get("advisorModel", "?"), "agents": agents,
            "decider": dmodel, "pricing": pricing}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, open(os.path.join(HERE, "ui.html"), "rb").read(), "text/html")
        if self.path == "/config":
            return self._send(200, {**config(), "on": os.path.exists(FLAG)})
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                os.makedirs(DIR, exist_ok=True); open(LOG, "a").close()
                with open(LOG, encoding="utf-8") as f:
                    lines = f.readlines()[-BACKLOG:]
                    self.wfile.write(b"event: reset\ndata: {}\n\n")
                    for l in lines:
                        if l.strip(): self.wfile.write(f"data: {l.strip()}\n\n".encode())
                    self.wfile.flush()
                    idle = 0
                    while True:
                        l = f.readline()
                        if l:
                            if l.endswith("\n") and l.strip():
                                self.wfile.write(f"data: {l.strip()}\n\n".encode()); self.wfile.flush()
                            idle = 0
                            continue
                        if os.path.getsize(LOG) < f.tell():      # log was cleared
                            f.seek(0); self.wfile.write(b"event: reset\ndata: {}\n\n"); self.wfile.flush()
                        time.sleep(0.15); idle += 1
                        if idle >= 100:
                            self.wfile.write(b": ping\n\n"); self.wfile.flush(); idle = 0
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/on":
            os.makedirs(DIR, exist_ok=True); open(FLAG, "w").close()
        elif self.path == "/off":
            if os.path.exists(FLAG): os.remove(FLAG)
        elif self.path == "/clear":
            open(LOG, "w").close()
        else:
            return self._send(404, {"error": "not found"})
        self._send(200, {"on": os.path.exists(FLAG)})

def stop(*_):
    if os.path.exists(FLAG): os.remove(FLAG)
    sys.exit(0)

if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8790
    os.makedirs(DIR, exist_ok=True); open(FLAG, "w").close()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    print(f"agent monitor: http://localhost:{port}  (log: {LOG})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
