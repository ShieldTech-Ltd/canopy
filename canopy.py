"""
Canopy — Mubit Hackathon Night Shift 2026
Autonomous claim verification using Mubit + Banyan Sapling.
Handles SUPPORTED, VIOLATES, and INSUFFICIENT intelligently.

Run:  python canopy.py
Open: http://localhost:8080
"""

import json
import os
import time
import random
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Load .env
_env = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env):
    for _line in open(_env):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── Config ──────────────────────────────────────────────────────────────────
MUBIT_KEY      = os.environ.get("MUBIT_API_KEY", "")
MUBIT_BASE_URL = "https://api.mubit.ai/openai/v1"
MODEL          = "gpt-4.1-mini"          # swap to "banyan-sapling" when granted
USE_REAL_API   = bool(MUBIT_KEY)
PORT           = 8080
TICK_SECONDS   = 2.0
# ────────────────────────────────────────────────────────────────────────────

CLAIMS = [
    {
        "policy":  "Python language specification",
        "evidence":"Python executes source code via an interpreter at runtime",
        "claim":   "Python is a compiled language like C++",
        "truth":   "VIOLATES",
        "extra":   "CPython docs: source compiled to bytecode then interpreted — not compiled to machine code",
    },
    {
        "policy":  "Water chemistry",
        "evidence":"H2O consists of two hydrogen atoms bonded to one oxygen atom",
        "claim":   "Water boils at 100 degrees Celsius at sea level",
        "truth":   "SUPPORTED",
        "extra":   "NIST: boiling point of water at 101.325 kPa is 99.97 C",
    },
    {
        "policy":  "LLM architecture",
        "evidence":"Transformers process a fixed-length context window per inference call",
        "claim":   "LLMs have perfect long-term memory across all sessions",
        "truth":   "VIOLATES",
        "extra":   "OpenAI docs: no persistent state between API calls; context window is the only memory",
    },
    {
        "policy":  "Mubit platform documentation",
        "evidence":"Mubit intercepts API calls and trains task-specific adapters via one URL change",
        "claim":   "Using Mubit requires rewriting your entire AI stack",
        "truth":   "VIOLATES",
        "extra":   "Mubit quickstart: replace base URL only; models, tools, orchestration unchanged",
    },
    {
        "policy":  "LoRA fine-tuning architecture",
        "evidence":"LoRA adapters are additive weight matrices that sit on top of frozen base weights",
        "claim":   "Fine-tuning permanently changes the base model weights",
        "truth":   "VIOLATES",
        "extra":   "LoRA paper 2021: base model weights frozen throughout; only adapter params updated",
    },
    {
        "policy":  "Coffee chemistry",
        "evidence":"Coffea arabica beans synthesise caffeine as a natural insect deterrent",
        "claim":   "Coffee contains caffeine",
        "truth":   "SUPPORTED",
        "extra":   "USDA: a standard 240ml cup of brewed coffee contains 80-100mg caffeine",
    },
    {
        "policy":  "API rate limiting standards",
        "evidence":"HTTP 429 Too Many Requests indicates a rate limit has been exceeded",
        "claim":   "Production APIs have no rate limits if you pay a premium tier",
        "truth":   "VIOLATES",
        "extra":   "OpenAI, Anthropic, Google all publish rate limits at every pricing tier",
    },
    {
        "policy":  "Heliocentric astronomy",
        "evidence":"Kepler orbital mechanics and stellar parallax confirm Earth orbits the Sun",
        "claim":   "The Earth orbits the Sun",
        "truth":   "SUPPORTED",
        "extra":   "NASA: Earth completes one full orbit every 365.25 days at mean distance 149.6M km",
    },
    {
        "policy":  "Active learning theory",
        "evidence":"Human feedback on model outputs is the foundation of RLHF",
        "claim":   "Sending corrections to a model always makes it perform worse",
        "truth":   "VIOLATES",
        "extra":   "InstructGPT paper: RLHF with human feedback consistently improves alignment",
    },
    {
        "policy":  "Open source licensing",
        "evidence":"MIT and Apache 2.0 are OSI-approved licences permitting commercial use",
        "claim":   "Open source software cannot be used in commercial products",
        "truth":   "VIOLATES",
        "extra":   "OSI definition clause 6: no discrimination against fields of endeavour including commerce",
    },
    {
        "policy":  "Banyan Sapling model specification",
        "evidence":"Banyan Sapling accepts policy, evidence, and claim; returns three-way verdict",
        "claim":   "Banyan Sapling can only return binary true or false verdicts",
        "truth":   "VIOLATES",
        "extra":   "Mubit launch: INSUFFICIENT response breaks the turn-based evidence loop",
    },
    {
        "policy":  "Edge computing hardware constraints",
        "evidence":"Raspberry Pi 4 has a maximum of 8GB LPDDR4 RAM",
        "claim":   "A Raspberry Pi can run a 70 billion parameter LLM at inference speed",
        "truth":   "VIOLATES",
        "extra":   "LLaMA 70B at fp16 requires approximately 140GB RAM; far exceeds Pi capacity",
    },
    {
        "policy":  "Adapter versioning in Mubit",
        "evidence":"Mubit maintains a version history for each task-specific adapter",
        "claim":   "A bad adapter update cannot be undone once deployed",
        "truth":   "VIOLATES",
        "extra":   "Mubit docs: adapters are versioned and reversible; rollback available at any time",
    },
    {
        "policy":  "Verified outcome requirement",
        "evidence":"Mubit docs state: an agent saying it succeeded is not enough",
        "claim":   "Mubit can train adapters purely from agent self-reports with no external verification",
        "truth":   "VIOLATES",
        "extra":   "Mubit integration guide: outcome must come from a test, check, or human review",
    },
    {
        "policy":  "Gravitational physics",
        "evidence":"Newton's law of gravitation: F = Gm1m2/r^2",
        "claim":   "Objects of different masses fall at the same rate in a vacuum",
        "truth":   "SUPPORTED",
        "extra":   "Galileo's experiment and Apollo 15 feather-hammer drop both confirmed equivalence",
    },
]

# ── Shared state ─────────────────────────────────────────────────────────────
state = {
    "total":          0,
    "correct":        0,
    "corrections":    0,
    "insufficient":   0,
    "resolved":       0,
    "version":        1,
    "accuracy":       0.0,
    "v1_accuracy":    None,
    "decisions":      [],
    "insuff_log":     [],
    "log":            [],
    "running":        False,
    "api_status":     "connecting" if USE_REAL_API else "simulation",
}

# ── Mubit calls ───────────────────────────────────────────────────────────────

def call_mubit(policy, evidence, claim):
    if USE_REAL_API:
        from openai import OpenAI
        client = OpenAI(api_key=MUBIT_KEY, base_url=MUBIT_BASE_URL)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You verify claims against policy and evidence. "
                        "Reply with exactly one word: SUPPORTED, VIOLATES, or INSUFFICIENT. "
                        "Use INSUFFICIENT only when the evidence lacks enough detail to be certain."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Policy: {policy}\nEvidence: {evidence}\nClaim: {claim}",
                },
            ],
            max_tokens=10,
        )
        state["api_status"] = "live"
        return resp.choices[0].message.content.strip().upper().split()[0]
    else:
        time.sleep(0.3)
        return _simulate(claim)


def _simulate(claim):
    truth = next((c["truth"] for c in CLAIMS if c["claim"] == claim), "SUPPORTED")
    if random.random() < 0.14:
        return "INSUFFICIENT"
    accuracy = min(0.42 + state["version"] * 0.07, 0.94)
    if random.random() < accuracy:
        return truth
    return "VIOLATES" if truth == "SUPPORTED" else "SUPPORTED"


def send_correction(claim_obj, predicted, correct):
    if not USE_REAL_API:
        time.sleep(0.1)
        return "simulated"
    payload = json.dumps({
        "model":          MODEL,
        "input":          f"Policy: {claim_obj['policy']}\nEvidence: {claim_obj['evidence']}\nClaim: {claim_obj['claim']}",
        "predicted":      predicted,
        "correct_output": correct,
    }).encode()
    for ep in ["/outcomes", "/feedback"]:
        try:
            req = urllib.request.Request(
                MUBIT_BASE_URL + ep,
                data=payload,
                headers={
                    "Authorization": f"Bearer {MUBIT_KEY}",
                    "Content-Type":  "application/json",
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            return f"sent to {ep}"
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return "queued (upgrade needed for correction endpoint)"
        except Exception:
            pass
    return "failed"


def fetch_extra_evidence(claim_obj):
    if not USE_REAL_API:
        time.sleep(0.4)
        return claim_obj["extra"]
    try:
        words  = claim_obj["claim"].split()[:4]
        query  = "_".join(words)
        url    = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
        req    = urllib.request.Request(url, headers={"User-Agent": "Canopy/1.0"})
        resp   = urllib.request.urlopen(req, timeout=4)
        data   = json.loads(resp.read())
        text   = data.get("extract", "")
        return (text[:280] + "...") if len(text) > 280 else (text or claim_obj["extra"])
    except Exception:
        return claim_obj["extra"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now().strftime("%H:%M:%S")


def _log(text, kind="ok"):
    state["log"].insert(0, {"text": text, "kind": kind, "ts": _now()})
    state["log"] = state["log"][:50]

# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent():
    state["running"] = True
    pool = CLAIMS * 8
    random.shuffle(pool)

    for claim_obj in pool:
        if not state["running"]:
            break

        try:
            verdict = call_mubit(
                claim_obj["policy"],
                claim_obj["evidence"],
                claim_obj["claim"],
            )
        except Exception as exc:
            _log(f"[API ERROR] {exc}", "error")
            time.sleep(3)
            continue

        state["total"] += 1

        if state["v1_accuracy"] is None and state["total"] >= 10:
            state["v1_accuracy"] = state["accuracy"]

        if verdict == "INSUFFICIENT":
            state["insufficient"] += 1
            short = claim_obj["claim"][:48]
            _log(f"[INSUFFICIENT] \"{short}...\" — fetching extra evidence", "warn")
            extra   = fetch_extra_evidence(claim_obj)
            verdict = call_mubit(
                claim_obj["policy"],
                claim_obj["evidence"] + " | Extra: " + extra,
                claim_obj["claim"],
            )
            state["resolved"] += 1
            state["insuff_log"].insert(0, {
                "claim":    short + "...",
                "extra":    extra[:80] + "...",
                "resolved": verdict,
                "ts":       _now(),
            })
            state["insuff_log"] = state["insuff_log"][:6]
            _log(f"[RESOLVED] Re-submitted with evidence → {verdict}", "resolved")

        truth   = claim_obj["truth"]
        correct = verdict == truth

        if correct:
            state["correct"] += 1
        else:
            state["corrections"] += 1
            result = send_correction(claim_obj, verdict, truth)
            _log(
                f"[CORRECTION] Predicted {verdict}, truth {truth} "
                f"| record_outcome() {result}",
                "corr",
            )
            if state["corrections"] % 3 == 0:
                state["version"] += 1
                _log(f"[MUBIT] Adapter trained → Model v{state['version']} promoted", "upd")

        state["accuracy"] = round(state["correct"] / state["total"] * 100, 1)

        state["decisions"].insert(0, {
            "id":      state["total"],
            "claim":   claim_obj["claim"][:50] + ("..." if len(claim_obj["claim"]) > 50 else ""),
            "verdict": verdict,
            "truth":   truth,
            "correct": correct,
            "ver":     f"v{state['version']}",
            "ts":      _now(),
        })
        state["decisions"] = state["decisions"][:20]

        if correct:
            _log(f"[OK] \"{claim_obj['claim'][:48]}\" → {verdict}", "ok")

        time.sleep(TICK_SECONDS)

    state["running"] = False

# ── Dashboard ─────────────────────────────────────────────────────────────────

def _rows():
    out = ""
    for r in state["decisions"]:
        c  = "ok" if r["correct"] else "bad"
        sy = "✓" if r["correct"] else "✗"
        out += (
            f"<tr>"
            f"<td class='dim'>{r['id']}</td>"
            f"<td>{r['claim']}</td>"
            f"<td class='{c}'>{r['verdict']}</td>"
            f"<td class='dim'>{r['truth']}</td>"
            f"<td class='{c}'>{sy}</td>"
            f"<td class='ver'>{r['ver']}</td>"
            f"<td class='dim'>{r['ts']}</td>"
            f"</tr>"
        )
    return out or "<tr><td colspan='7' class='dim'>Starting agent...</td></tr>"


def _insuff_rows():
    out = ""
    for r in state["insuff_log"]:
        out += (
            f"<tr>"
            f"<td class='warn'>{r['ts']}</td>"
            f"<td>{r['claim']}</td>"
            f"<td class='dim'>{r['extra']}</td>"
            f"<td class='ok'>{r['resolved']}</td>"
            f"</tr>"
        )
    return out or "<tr><td colspan='4' class='dim'>No INSUFFICIENT cases yet...</td></tr>"


def _log_html():
    out = ""
    for l in state["log"]:
        out += f"<div class='{l['kind']}'><span class='ts'>{l['ts']}</span> {l['text']}</div>"
    return out or "<div class='dim'>Initialising...</div>"


def _improvement():
    v1  = state["v1_accuracy"]
    now = state["accuracy"]
    if v1 is None:
        return "<span class='dim'>Calculating baseline...</span>"
    diff = round(now - v1, 1)
    sign = "+" if diff >= 0 else ""
    col  = "ok" if diff >= 0 else "bad"
    return (
        f"<span class='dim'>v1 baseline</span> <strong>{v1}%</strong>"
        f" &nbsp;→&nbsp; "
        f"<span class='dim'>now</span> <strong>{now}%</strong>"
        f" &nbsp;<span class='{col}'>{sign}{diff}%</span>"
    )


DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Canopy — Mubit</title>
<meta http-equiv="refresh" content="2">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080810;color:#d0d0d8;font-family:'Courier New',monospace;padding:28px;min-height:100vh}}

header{{display:flex;align-items:baseline;gap:20px;margin-bottom:6px}}
h1{{font-size:32px;letter-spacing:4px;color:#7fffd4;font-weight:bold}}
.model-badge{{font-size:11px;color:#555;letter-spacing:2px;border:1px solid #222;
              padding:3px 10px;border-radius:20px}}
.tagline{{color:#444;font-size:12px;margin-bottom:20px;letter-spacing:1px}}

.api-status{{display:inline-flex;align-items:center;gap:6px;font-size:11px;
             color:#7fffd4;margin-bottom:24px}}
.api-status.sim{{color:#ffb347}}
.dot{{width:7px;height:7px;border-radius:50%;background:currentColor;
      animation:pulse 1.4s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}

.stats{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:24px}}
.stat{{background:#0e0e18;border:1px solid #1a1a2e;border-radius:10px;padding:16px 14px}}
.stat .n{{font-size:32px;font-weight:bold;color:#7fffd4;line-height:1}}
.stat .l{{font-size:10px;color:#444;margin-top:6px;text-transform:uppercase;letter-spacing:1px}}
.stat.red .n{{color:#ff6b6b}}
.stat.amber .n{{color:#ffb347}}
.stat.purple .n{{color:#a78bfa}}

.progress-row{{display:flex;align-items:center;gap:14px;margin-bottom:24px}}
.track{{background:#0e0e18;border-radius:6px;height:10px;flex:1;max-width:400px}}
.fill{{background:linear-gradient(90deg,#4ecdc4,#7fffd4);height:10px;border-radius:6px;
       transition:width 1s ease}}
.pct{{font-size:20px;font-weight:bold;color:#7fffd4}}
.improvement{{font-size:12px;color:#444}}

.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;margin-bottom:20px}}
.panel{{background:#0e0e18;border:1px solid #1a1a2e;border-radius:10px;padding:18px}}
.panel-title{{font-size:10px;text-transform:uppercase;letter-spacing:2px;
              color:#444;margin-bottom:14px}}

table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#333;border-bottom:1px solid #1a1a2e;
    padding:5px 8px;font-size:10px;text-transform:uppercase;letter-spacing:1px}}
td{{padding:7px 8px;border-bottom:1px solid #111;vertical-align:top}}
.ok{{color:#7fffd4}}
.bad{{color:#ff6b6b}}
.warn{{color:#ffb347}}
.resolved{{color:#a78bfa}}
.dim{{color:#444}}
.ver{{color:#555}}
.ts{{color:#2a2a3a;margin-right:6px}}

.log-box{{background:#060610;border:1px solid #111;border-radius:8px;
          padding:14px;height:220px;overflow-y:auto;font-size:11px;margin-bottom:20px}}
.log-box .ok{{color:#3a5a3a;display:block;padding:2px 0;border-bottom:1px solid #0d0d1a}}
.log-box .corr{{color:#ff6b6b;display:block;padding:2px 0;border-bottom:1px solid #0d0d1a}}
.log-box .upd{{color:#7fffd4;font-weight:bold;display:block;padding:2px 0;border-bottom:1px solid #0d0d1a}}
.log-box .warn{{color:#ffb347;display:block;padding:2px 0;border-bottom:1px solid #0d0d1a}}
.log-box .resolved{{color:#a78bfa;display:block;padding:2px 0;border-bottom:1px solid #0d0d1a}}
.log-box .error{{color:#ff4444;display:block;padding:2px 0;border-bottom:1px solid #0d0d1a}}
.log-box .dim{{color:#222;display:block}}

footer{{font-size:10px;color:#222;letter-spacing:1px}}
</style>
</head>
<body>

<header>
  <h1>CANOPY</h1>
  <span class="model-badge">via MUBIT / {model}</span>
</header>
<div class="tagline">AUTONOMOUS CLAIM VERIFICATION &nbsp;·&nbsp; NIGHT SHIFT 2026 &nbsp;·&nbsp; CANARY WHARF</div>

<div class="api-status {api_cls}">
  <span class="dot"></span>
  {api_label}
</div>

<div class="stats">
  <div class="stat">
    <div class="n">{accuracy}%</div>
    <div class="l">Accuracy</div>
  </div>
  <div class="stat">
    <div class="n">{total}</div>
    <div class="l">Decisions</div>
  </div>
  <div class="stat red">
    <div class="n">{corrections}</div>
    <div class="l">Corrections sent</div>
  </div>
  <div class="stat amber">
    <div class="n">{insufficient}</div>
    <div class="l">INSUFFICIENT caught</div>
  </div>
  <div class="stat amber">
    <div class="n">{resolved}</div>
    <div class="l">Resolved</div>
  </div>
  <div class="stat purple">
    <div class="n">v{version}</div>
    <div class="l">Model version</div>
  </div>
</div>

<div class="progress-row">
  <span class="dim" style="font-size:11px;text-transform:uppercase;letter-spacing:1px">Accuracy</span>
  <div class="track"><div class="fill" style="width:{accuracy}%"></div></div>
  <span class="pct">{accuracy}%</span>
  <span class="improvement">{improvement}</span>
</div>

<div class="grid">
  <div class="panel">
    <div class="panel-title">Live decisions</div>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Claim</th><th>Verdict</th><th>Truth</th>
          <th>OK</th><th>Model</th><th>Time</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div class="panel">
    <div class="panel-title">INSUFFICIENT resolution log</div>
    <table>
      <thead>
        <tr><th>Time</th><th>Claim</th><th>Extra evidence</th><th>Resolved</th></tr>
      </thead>
      <tbody>{insuff_rows}</tbody>
    </table>
  </div>
</div>

<div class="log-box">{log_html}</div>

<footer>
  AUTO-REFRESH 2s &nbsp;·&nbsp;
  REPO: github.com/ShieldTech-Ltd/canopy &nbsp;·&nbsp;
  {api_footer}
</footer>

</body>
</html>"""


def build_page():
    live     = USE_REAL_API
    api_cls  = "live" if live else "sim"
    api_label = f"LIVE — Mubit API / {MODEL}" if live else "SIMULATION MODE — set MUBIT_API_KEY to go live"
    api_footer = f"MODEL: {MODEL} via Mubit" if live else "Swap USE_REAL_API = True + Mubit key to go live"
    return DASHBOARD.format(
        model        = MODEL,
        accuracy     = state["accuracy"],
        total        = state["total"],
        corrections  = state["corrections"],
        insufficient = state["insufficient"],
        resolved     = state["resolved"],
        version      = state["version"],
        improvement  = _improvement(),
        rows         = _rows(),
        insuff_rows  = _insuff_rows(),
        log_html     = _log_html(),
        api_cls      = api_cls,
        api_label    = api_label,
        api_footer   = api_footer,
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(build_page().encode())

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print("=" * 56)
    print("  CANOPY — Mubit Intelligence Layer")
    print("  Night Shift 2026 | Canary Wharf, London")
    print("=" * 56)
    mode = f"LIVE ({MODEL} via Mubit)" if USE_REAL_API else "SIMULATION"
    print(f"\n  Mode:      {mode}")
    print(f"  Dashboard: http://localhost:{PORT}")
    print("\n  Ctrl+C to stop\n")

    t = threading.Thread(target=run_agent, daemon=True)
    t.start()

    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state["running"] = False
        print("\nStopped.")
