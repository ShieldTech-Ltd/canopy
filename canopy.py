"""
Canopy — Mubit Hackathon 2026
An agent that verifies claims through Banyan Sapling and handles all three
responses intelligently: SUPPORTED, VIOLATES, and INSUFFICIENT.

Run:  python canopy.py
Open: http://localhost:8080
"""

import json
import time
import random
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────
MUBIT_KEY      = "YOUR_MUBIT_KEY_HERE"
MUBIT_BASE_URL = "https://api.mubit.ai/openai/v1"
USE_REAL_API   = False   # flip to True once you have the key
PORT           = 8080
# ───────────────────────────────────────────────────────────────────────────

# Each claim has: policy (the rule), evidence (context), claim (what to verify),
# truth (ground truth for auto-correction), and extra_evidence (used when INSUFFICIENT)
CLAIMS = [
    {
        "policy":         "Scientific consensus on physical constants",
        "evidence":       "Standard atmospheric pressure is defined as 101.325 kPa",
        "claim":          "Water boils at 100 degrees Celsius at sea level",
        "truth":          "SUPPORTED",
        "extra_evidence": "NIST reference: water boiling point at 1 atm is 99.97C",
    },
    {
        "policy":         "Python language specification",
        "evidence":       "Python executes source code via an interpreter at runtime",
        "claim":          "Python is a compiled language like C++",
        "truth":          "VIOLATES",
        "extra_evidence": "CPython reference: Python compiles to bytecode then interprets it",
    },
    {
        "policy":         "LLM architecture fundamentals",
        "evidence":       "Transformer models process a fixed-size context window",
        "claim":          "LLMs have perfect long-term memory across all sessions",
        "truth":          "VIOLATES",
        "extra_evidence": "OpenAI docs: context window is the only memory; no cross-session state",
    },
    {
        "policy":         "Mubit platform documentation",
        "evidence":       "Mubit intercepts API calls and trains task-specific adapters",
        "claim":          "Using Mubit requires rewriting your entire AI stack",
        "truth":          "VIOLATES",
        "extra_evidence": "Mubit quickstart: one base URL change, everything else unchanged",
    },
    {
        "policy":         "Model fine-tuning architecture",
        "evidence":       "LoRA adapters modify attention weights without touching base weights",
        "claim":          "Fine-tuning permanently changes the base model weights",
        "truth":          "VIOLATES",
        "extra_evidence": "LoRA paper: adapters are additive; base model remains frozen",
    },
    {
        "policy":         "Banyan Sapling model specification",
        "evidence":       "Banyan Sapling returns SUPPORTED, VIOLATES, or INSUFFICIENT",
        "claim":          "Banyan Sapling can only return binary true or false verdicts",
        "truth":          "VIOLATES",
        "extra_evidence": "Mubit launch notes: three-way verdict breaks the turn-based loop",
    },
    {
        "policy":         "Coffee chemistry",
        "evidence":       "Coffea arabica beans contain caffeine as a natural pesticide",
        "claim":          "Coffee contains caffeine",
        "truth":          "SUPPORTED",
        "extra_evidence": "USDA: 8oz coffee contains 80-100mg caffeine on average",
    },
    {
        "policy":         "API rate limiting standards",
        "evidence":       "HTTP 429 status code indicates rate limit exceeded",
        "claim":          "Production APIs have no rate limits if you pay enough",
        "truth":          "VIOLATES",
        "extra_evidence": "OpenAI, Anthropic, Google all enforce rate limits at all tiers",
    },
    {
        "policy":         "Astronomical observations",
        "evidence":       "Heliocentric model confirmed by parallax and Kepler orbital mechanics",
        "claim":          "The Earth orbits the Sun",
        "truth":          "SUPPORTED",
        "extra_evidence": "NASA: Earth completes one orbit every 365.25 days at 149.6M km",
    },
    {
        "policy":         "Active learning theory",
        "evidence":       "Verified outcome labels improve model accuracy on the target task",
        "claim":          "Sending corrections to a model always makes it worse",
        "truth":          "VIOLATES",
        "extra_evidence": "RLHF paper: human feedback consistently improves model alignment",
    },
    {
        "policy":         "Edge computing constraints",
        "evidence":       "Raspberry Pi 4 has 8GB RAM and a 1.8GHz ARM Cortex-A72",
        "claim":          "A Raspberry Pi can run a 70B parameter LLM at full speed",
        "truth":          "VIOLATES",
        "extra_evidence": "LLaMA 70B requires ~140GB RAM minimum; Pi has 8GB max",
    },
    {
        "policy":         "Open source licensing",
        "evidence":       "MIT and Apache 2.0 licenses permit commercial use and modification",
        "claim":          "Open source software cannot be used in commercial products",
        "truth":          "VIOLATES",
        "extra_evidence": "OSI definition: open source explicitly allows commercial use",
    },
]

# Shared state for the dashboard
state = {
    "total":        0,
    "correct":      0,
    "corrections":  0,
    "insufficient": 0,
    "resolved":     0,
    "version":      1,
    "accuracy":     0.0,
    "decisions":    [],
    "log":          [],
    "running":      False,
}

# ── Mubit API calls ─────────────────────────────────────────────────────────

def call_banyan(policy, evidence, claim):
    if USE_REAL_API:
        from openai import OpenAI
        client = OpenAI(api_key=MUBIT_KEY, base_url=MUBIT_BASE_URL)
        resp = client.chat.completions.create(
            model="banyan-sapling",
            messages=[
                {"role": "system", "content": (
                    "You verify claims against evidence and policy. "
                    "Reply with exactly one word: SUPPORTED, VIOLATES, or INSUFFICIENT. "
                    "Use INSUFFICIENT only when the evidence does not contain enough "
                    "information to make a confident verdict."
                )},
                {"role": "user", "content": (
                    f"Policy: {policy}\n"
                    f"Evidence: {evidence}\n"
                    f"Claim: {claim}"
                )},
            ],
        )
        return resp.choices[0].message.content.strip().upper()
    else:
        time.sleep(0.3)
        return _simulate_banyan(claim)


def _simulate_banyan(claim):
    accuracy = min(0.40 + state["version"] * 0.07, 0.93)
    correct_truth = next(
        (c["truth"] for c in CLAIMS if c["claim"] == claim), "SUPPORTED"
    )
    # Occasionally return INSUFFICIENT to demonstrate the evidence-gathering loop
    if random.random() < 0.15:
        return "INSUFFICIENT"
    if random.random() < accuracy:
        return correct_truth
    options = ["SUPPORTED", "VIOLATES"]
    options = [o for o in options if o != correct_truth]
    return options[0]


def send_correction(claim_obj, predicted, correct):
    if USE_REAL_API:
        payload = json.dumps({
            "model":          "banyan-sapling",
            "input":          f"Policy: {claim_obj['policy']}\nEvidence: {claim_obj['evidence']}\nClaim: {claim_obj['claim']}",
            "predicted":      predicted,
            "correct_output": correct,
        }).encode()
        req = urllib.request.Request(
            f"{MUBIT_BASE_URL}/outcomes",
            data=payload,
            headers={
                "Authorization": f"Bearer {MUBIT_KEY}",
                "Content-Type":  "application/json",
            },
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    else:
        time.sleep(0.15)


def fetch_extra_evidence(claim_obj):
    """When Banyan Sapling returns INSUFFICIENT, fetch more evidence."""
    if USE_REAL_API:
        # Real implementation: query Wikipedia or another source
        try:
            query   = claim_obj["claim"].replace(" ", "+")
            url     = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
            req     = urllib.request.Request(url, headers={"User-Agent": "Canopy/1.0"})
            resp    = urllib.request.urlopen(req, timeout=4)
            data    = json.loads(resp.read())
            extract = data.get("extract", "")
            return extract[:300] if extract else claim_obj["extra_evidence"]
        except Exception:
            return claim_obj["extra_evidence"]
    else:
        time.sleep(0.4)
        return claim_obj["extra_evidence"]


# ── Agent loop ──────────────────────────────────────────────────────────────

def _log(msg, kind="info"):
    state["log"].insert(0, {"text": msg, "kind": kind, "time": _now()})
    state["log"] = state["log"][:40]


def _now():
    return datetime.now().strftime("%H:%M:%S")


def run_agent():
    state["running"] = True
    pool = CLAIMS * 6
    random.shuffle(pool)

    for claim_obj in pool:
        if not state["running"]:
            break

        verdict = call_banyan(
            claim_obj["policy"],
            claim_obj["evidence"],
            claim_obj["claim"],
        )
        state["total"] += 1

        if verdict == "INSUFFICIENT":
            state["insufficient"] += 1
            _log(f"[INSUFFICIENT] \"{claim_obj['claim'][:45]}...\" — fetching more evidence", "warn")
            extra = fetch_extra_evidence(claim_obj)
            # Re-submit with enriched evidence
            verdict = call_banyan(
                claim_obj["policy"],
                claim_obj["evidence"] + " | Additional: " + extra,
                claim_obj["claim"],
            )
            state["resolved"] += 1
            _log(f"[RESOLVED] Re-submitted with extra evidence → {verdict}", "resolved")

        truth   = claim_obj["truth"]
        correct = verdict == truth

        if correct:
            state["correct"] += 1
        else:
            state["corrections"] += 1
            send_correction(claim_obj, verdict, truth)
            _log(f"[CORRECTION] Predicted {verdict}, truth {truth} — record_outcome() sent", "corr")
            if state["corrections"] % 3 == 0:
                state["version"] += 1
                _log(f"[MUBIT] Adapter trained → Model v{state['version']} promoted", "upd")

        state["accuracy"] = round(state["correct"] / state["total"] * 100, 1)

        entry = {
            "id":      state["total"],
            "claim":   claim_obj["claim"][:52] + ("..." if len(claim_obj["claim"]) > 52 else ""),
            "verdict": verdict,
            "truth":   truth,
            "correct": correct,
            "ver":     f"v{state['version']}",
            "time":    _now(),
        }
        state["decisions"].insert(0, entry)
        state["decisions"] = state["decisions"][:20]

        if correct and "[CORRECTION]" not in (state["log"][0]["text"] if state["log"] else ""):
            _log(f"[OK] \"{claim_obj['claim'][:45]}\" → {verdict}", "ok")

        time.sleep(1.4)

    state["running"] = False


# ── Dashboard HTML ──────────────────────────────────────────────────────────

DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Canopy — Mubit Intelligence Layer</title>
<meta http-equiv="refresh" content="2">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0b0b0f;color:#e0e0e0;font-family:monospace;padding:24px}}

  header{{margin-bottom:24px}}
  h1{{color:#7fffd4;font-size:28px;letter-spacing:2px}}
  .tagline{{color:#555;font-size:13px;margin-top:4px}}
  .badge{{display:inline-block;background:#0a2a1a;border:1px solid #2a6a4a;
          color:#7fffd4;font-size:11px;padding:3px 10px;border-radius:12px;
          margin-top:8px;letter-spacing:1px}}

  .stats{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
  .stat{{background:#111;border:1px solid #222;border-radius:10px;
         padding:16px 22px;min-width:130px}}
  .stat .n{{font-size:34px;font-weight:bold;color:#7fffd4}}
  .stat .l{{font-size:11px;color:#555;margin-top:4px;text-transform:uppercase;letter-spacing:1px}}
  .stat.warn .n{{color:#ffb347}}
  .stat.bad  .n{{color:#ff6b6b}}
  .stat.ver  .n{{color:#a78bfa}}

  .bar-row{{display:flex;align-items:center;gap:12px;margin-bottom:24px}}
  .bar-track{{background:#111;border-radius:4px;height:12px;width:240px}}
  .bar-fill{{background:#7fffd4;height:12px;border-radius:4px;transition:width 0.8s ease}}
  .bar-pct{{color:#7fffd4;font-size:14px}}
  .bar-note{{color:#444;font-size:11px}}

  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}

  .panel{{background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:16px}}
  .panel h3{{font-size:12px;text-transform:uppercase;letter-spacing:1px;
             color:#555;margin-bottom:12px}}

  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{text-align:left;color:#444;border-bottom:1px solid #1e1e1e;
      padding:5px 8px;font-size:10px;text-transform:uppercase;letter-spacing:1px}}
  td{{padding:6px 8px;border-bottom:1px solid #161616}}
  .ok  {{color:#7fffd4}}
  .bad {{color:#ff6b6b}}
  .ins {{color:#ffb347}}

  .log-panel{{background:#0c0c0c;border:1px solid #1a1a1a;border-radius:10px;
              padding:14px;height:200px;overflow-y:auto;font-size:12px;margin-bottom:24px}}
  .log-panel .ok  {{color:#444;padding:3px 0;border-bottom:1px solid #111;display:block}}
  .log-panel .corr{{color:#ff6b6b;padding:3px 0;border-bottom:1px solid #111;display:block}}
  .log-panel .upd {{color:#7fffd4;font-weight:bold;padding:3px 0;
                    border-bottom:1px solid #111;display:block}}
  .log-panel .warn{{color:#ffb347;padding:3px 0;border-bottom:1px solid #111;display:block}}
  .log-panel .resolved{{color:#a78bfa;padding:3px 0;border-bottom:1px solid #111;display:block}}

  .pulse{{display:inline-block;width:7px;height:7px;background:#7fffd4;
          border-radius:50%;margin-right:6px;animation:p 1.2s infinite}}
  @keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
  footer{{color:#2a2a2a;font-size:11px;margin-top:8px}}

  .insight{{background:#0a1a0a;border:1px solid #1a3a1a;border-radius:8px;
            padding:12px 16px;margin-bottom:24px;font-size:12px;color:#666;line-height:1.7}}
  .insight strong{{color:#7fffd4}}
</style>
</head>
<body>

<header>
  <h1>CANOPY</h1>
  <div class="tagline">Mubit intelligence layer — autonomous claim verification</div>
  <span class="badge">NIGHT SHIFT 2026</span>
</header>

<div class="insight">
  <strong>How it works:</strong>
  Claims route through <strong>Banyan Sapling</strong> via Mubit.
  VIOLATES triggers <strong>record_outcome()</strong> automatically — no human needed.
  INSUFFICIENT triggers <strong>evidence gathering</strong>, then re-submits.
  Every 3 corrections, Mubit promotes a new adapter version.
  <strong>The model improves itself.</strong>
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
  <div class="stat bad">
    <div class="n">{corrections}</div>
    <div class="l">Corrections sent</div>
  </div>
  <div class="stat warn">
    <div class="n">{insufficient}</div>
    <div class="l">INSUFFICIENT caught</div>
  </div>
  <div class="stat warn">
    <div class="n">{resolved}</div>
    <div class="l">Resolved w/ evidence</div>
  </div>
  <div class="stat ver">
    <div class="n">v{version}</div>
    <div class="l">Model version</div>
  </div>
</div>

<div class="bar-row">
  <span style="color:#555;font-size:12px">Accuracy</span>
  <div class="bar-track">
    <div class="bar-fill" style="width:{accuracy}%"></div>
  </div>
  <span class="bar-pct">{accuracy}%</span>
  <span class="bar-note">Mubit promotes a new adapter every 3 corrections</span>
</div>

<div class="grid">
  <div class="panel">
    <h3>Live decisions</h3>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Claim</th><th>Verdict</th><th>Truth</th><th>OK</th><th>Ver</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="panel">
    <h3>INSUFFICIENT resolution log</h3>
    <table>
      <thead>
        <tr><th>Caught</th><th>Resolved</th><th>Final verdict</th></tr>
      </thead>
      <tbody>{insuff_rows}</tbody>
    </table>
  </div>
</div>

<div class="log-panel">{log_html}</div>

<footer>
  <span class="pulse"></span>
  Agent running autonomously &nbsp;|&nbsp;
  Swap USE_REAL_API = True + Mubit key to go live &nbsp;|&nbsp;
  Canopy — Night Shift 2026
</footer>

</body>
</html>"""


def build_dashboard():
    rows = ""
    for r in state["decisions"]:
        cls    = "ok" if r["correct"] else "bad"
        symbol = "✓" if r["correct"] else "✗"
        rows += (
            f"<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{r['claim']}</td>"
            f"<td class='{cls}'>{r['verdict']}</td>"
            f"<td>{r['truth']}</td>"
            f"<td class='{cls}'>{symbol}</td>"
            f"<td style='color:#555'>{r['ver']}</td>"
            f"</tr>"
        )

    insuff_rows = ""
    insuff_entries = [l for l in state["log"] if "INSUFFICIENT" in l["text"] or "RESOLVED" in l["text"]]
    for entry in insuff_entries[:8]:
        kind_cls = "ins" if "INSUFFICIENT" in entry["text"] else "ok"
        insuff_rows += f"<tr><td class='{kind_cls}'>{entry['time']}</td><td colspan='2'>{entry['text'][:60]}</td></tr>"

    log_html = ""
    for l in state["log"]:
        log_html += f"<span class='{l['kind']}'>[{l['time']}] {l['text']}</span>"

    return DASHBOARD.format(
        accuracy     = state["accuracy"],
        total        = state["total"],
        corrections  = state["corrections"],
        insufficient = state["insufficient"],
        resolved     = state["resolved"],
        version      = state["version"],
        rows         = rows or "<tr><td colspan='6' style='color:#333'>Starting...</td></tr>",
        insuff_rows  = insuff_rows or "<tr><td colspan='3' style='color:#333'>Waiting for INSUFFICIENT cases...</td></tr>",
        log_html     = log_html or "<span class='ok'>Initialising agent...</span>",
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(build_dashboard().encode())

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print("=" * 52)
    print("  CANOPY — Mubit Intelligence Layer")
    print("  Night Shift 2026")
    print("=" * 52)
    print(f"\n  Dashboard: http://localhost:{PORT}")
    print(f"  Mode:      {'LIVE (Mubit API)' if USE_REAL_API else 'SIMULATION (swap USE_REAL_API = True)'}")
    print("\n  Press Ctrl+C to stop\n")

    t = threading.Thread(target=run_agent, daemon=True)
    t.start()

    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state["running"] = False
        print("\nStopped.")
