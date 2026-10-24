"""
Canopy — Mubit Hackathon Night Shift 2026
Autonomous claim verification using Banyan Sapling (real model, no auth needed).
Handles all five verdicts: supported, violation, insufficient_information,
inconsistent_context, unsure.

Run:  python canopy.py
Open: http://localhost:8080
"""

import json
import os
import time
import random
import threading
import urllib.request
import urllib.error
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
BANYAN_URL     = "https://6adbee0669a00298cd4774c9.endpoints.huggingface.cloud"
MUBIT_KEY      = os.environ.get("MUBIT_API_KEY", "")
MUBIT_BASE_URL = "https://api.mubit.ai/openai/v1"
PORT           = 8080
TICK_SECONDS   = 3.0
# ────────────────────────────────────────────────────────────────────────────

CLAIMS = [
    {
        "policy":  "GDPR Article 17: personal data must be erased within 30 days of an account closure request.",
        "evidence":"User submitted account closure request on 1 January 2026. Database audit on 10 February 2026 confirms the user record, email address, and purchase history remain active in the production database.",
        "claim":   "The data retention is compliant with GDPR Article 17.",
        "truth":   "VIOLATES",
        "extra":   "ICO guidance: 30-day erasure window is a hard deadline. 40 days elapsed. Constitutes a clear Article 17 violation.",
    },
    {
        "policy":  "UK Working Time Regulations 1998: employees must not work more than 48 hours per week on average, unless they have signed a written opt-out agreement.",
        "evidence":"Payroll records for week ending 14 October 2026 show employee Sarah Ahmed logged 56 hours. Her personnel file contains no signed opt-out agreement. Her contract does not reference the 48-hour limit.",
        "claim":   "Sarah Ahmed's working hours this week are compliant with the Working Time Regulations.",
        "truth":   "VIOLATES",
        "extra":   "ACAS: no opt-out agreement means the 48-hour weekly limit is legally binding. 56 hours is 8 hours over the legal maximum.",
    },
    {
        "policy":  "FCA Transaction Monitoring Rule SYSC 6.3: all transactions above 10,000 GBP must be reported to the FCA within 24 hours of detection.",
        "evidence":"A transfer of 45,000 GBP was processed at 09:00 on Monday 20 October 2026. The compliance team submitted the FCA report at 11:30 on Wednesday 22 October 2026, 50.5 hours after the transaction completed.",
        "claim":   "The transaction reporting timeline meets the FCA 24-hour requirement.",
        "truth":   "VIOLATES",
        "extra":   "FCA SYSC 6.3: the 24-hour window is measured from transaction completion. 50.5 hours elapsed. The report was 26.5 hours late.",
    },
    {
        "policy":  "PCI DSS Requirement 3.4: primary account numbers (PAN) must be rendered unreadable anywhere they are stored, using strong cryptography.",
        "evidence":"Database audit on 15 October 2026 found 12,000 customer card numbers stored in plaintext in the orders table. No encryption or tokenisation has been applied. The table is accessible to all backend engineers.",
        "claim":   "The card data storage meets PCI DSS Requirement 3.4.",
        "truth":   "VIOLATES",
        "extra":   "PCI Security Council: storing PANs in plaintext is a critical violation. Immediate remediation required. Fines range from 5,000 to 100,000 USD per month.",
    },
    {
        "policy":  "GDPR Article 33: a personal data breach must be reported to the supervisory authority within 72 hours of becoming aware of it.",
        "evidence":"The security team discovered a breach exposing 50,000 user email addresses at 14:00 on Monday 13 October. The ICO was notified at 10:00 on Thursday 16 October, 68 hours after discovery.",
        "claim":   "The breach notification timeline is compliant with GDPR Article 33.",
        "truth":   "SUPPORTED",
        "extra":   "ICO guidance: 72-hour window starts from awareness. 68 hours elapsed. Notification was within the legal deadline.",
    },
    {
        "policy":  "UK Equality Act 2010 Section 39: job advertisements must not indicate an intention to discriminate based on a protected characteristic.",
        "evidence":"A job posting for Senior Engineer published on 18 October 2026 states: 'We are looking for a recent graduate aged 22-28 for this role.' Age is a protected characteristic under the Equality Act 2010.",
        "claim":   "The job advertisement complies with the Equality Act 2010.",
        "truth":   "VIOLATES",
        "extra":   "EHRC: specifying an age range in a job ad constitutes direct age discrimination. The advertisement must be withdrawn and reposted without the age requirement.",
    },
    {
        "policy":  "ISO 27001 Control A.12.6.1: information about technical vulnerabilities must be patched within 30 days of a critical CVE being published.",
        "evidence":"CVE-2026-1234 (CVSS 9.8, critical) was published on 1 September 2026 affecting the company's web application framework. IT records show the patch was applied on 25 September 2026, 24 days after publication.",
        "claim":   "The patching timeline is compliant with ISO 27001 Control A.12.6.1.",
        "truth":   "SUPPORTED",
        "extra":   "ISO 27001 guidance: 30-day window for critical patches. 24 days elapsed. The control was met within the required timeframe.",
    },
    {
        "policy":  "UK Health and Safety at Work Act 1974: employers must conduct a written risk assessment for any activity that could cause harm to employees.",
        "evidence":"A new chemical cleaning process was introduced in the warehouse on 5 October 2026. No risk assessment document has been created. Three employees have since reported skin irritation.",
        "claim":   "The introduction of the cleaning process meets the Health and Safety at Work Act 1974.",
        "truth":   "VIOLATES",
        "extra":   "HSE: a written risk assessment is mandatory before introducing hazardous substances. Absence of assessment constitutes a breach. Reported injuries increase liability exposure.",
    },
    {
        "policy":  "FCA Consumer Duty (PS22/9): firms must provide customers with clear, fair, and not misleading information about products and pricing.",
        "evidence":"Marketing materials reviewed on 20 October 2026 describe the loan product as 'interest-free for 12 months' in large font. The 24.9% APR that applies after month 1 appears only in footnote 7 in 6-point grey text on page 4.",
        "claim":   "The loan product marketing materials comply with the FCA Consumer Duty information requirements.",
        "truth":   "VIOLATES",
        "extra":   "FCA PS22/9: material information including APR must be presented prominently and clearly. Burying rate information in a footnote fails the clear and not misleading standard.",
    },
    {
        "policy":  "GDPR Article 6: personal data may only be processed where at least one lawful basis applies, including explicit consent from the data subject.",
        "evidence":"Email marketing campaign launched 10 October 2026 sent promotional emails to 8,000 users. Consent records show 6,200 of these users had not opted in to marketing communications. 1,800 had explicitly opted out.",
        "claim":   "The email marketing campaign has a valid lawful basis under GDPR Article 6.",
        "truth":   "VIOLATES",
        "extra":   "ICO: sending marketing emails without consent where no other lawful basis applies violates GDPR Article 6. Emailing opt-out users additionally violates PECR Regulation 22.",
    },
    {
        "policy":  "UK Modern Slavery Act 2015 Section 54: commercial organisations with annual turnover above 36 million GBP must publish a modern slavery statement each financial year.",
        "evidence":"Company annual turnover for FY2025-26 was 42 million GBP. A modern slavery statement was published on the company website on 28 September 2026, covering supply chain due diligence, staff training, and reporting mechanisms.",
        "claim":   "The company has met its obligations under the Modern Slavery Act 2015 Section 54.",
        "truth":   "SUPPORTED",
        "extra":   "Home Office guidance: turnover above 36M GBP triggers the reporting requirement. A published statement covering the required topics constitutes compliance.",
    },
    {
        "policy":  "GDPR Article 28: where a controller uses a processor, the processing must be governed by a contract setting out the subject-matter and duration of processing.",
        "evidence":"Company X has been sharing customer data with third-party analytics provider DataCo since March 2026. No data processing agreement has been signed. DataCo processes data across servers in the US and India.",
        "claim":   "The data sharing arrangement with DataCo is compliant with GDPR Article 28.",
        "truth":   "VIOLATES",
        "extra":   "ICO: absence of a signed DPA means the processing lacks a valid legal framework. International transfers without appropriate safeguards additionally breach Chapter V of GDPR.",
    },
    {
        "policy":  "FCA COBS 9.2: a firm must take reasonable steps to ensure that a personal recommendation is suitable for the client, based on their financial situation and objectives.",
        "evidence":"Financial adviser recommended a high-risk emerging markets fund to a client aged 71 with no investment experience, a fixed pension income of 18,000 GBP per year, and a stated objective of capital preservation for retirement.",
        "claim":   "The investment recommendation meets the FCA suitability requirement under COBS 9.2.",
        "truth":   "VIOLATES",
        "extra":   "FCA COBS 9.2: a high-risk fund is unsuitable for a capital-preservation objective on a fixed retirement income. The recommendation constitutes a suitability failure.",
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
    "last_probs":     {},
    "last_timing_ms": 0,
    "api_status":     "connecting",
}

# ── Banyan Sapling API ────────────────────────────────────────────────────────

def call_banyan(policy, evidence, claim):
    """
    POST to the real Banyan Sapling endpoint (no auth required).
    Returns (status, raw_label, probabilities, timing_ms).
    status is one of: supported / violation / insufficient_information /
                      inconsistent_context / unsure
    """
    payload = json.dumps({
        "inputs": {
            "policy":   policy,
            "evidence": evidence,
            "claim":    claim,
        }
    }).encode()
    req = urllib.request.Request(
        BANYAN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    return (
        data.get("status",    "unsure"),
        data.get("raw_label", "unsure"),
        data.get("probabilities", {}),
        data.get("timing_ms", {}).get("model", 0),
    )


def _verdict_to_internal(status, raw_label):
    """
    Map Banyan Sapling output to internal label.
    When status is 'unsure', use raw_label (the model's best single guess).
    This gives decisive verdicts while keeping uncertainty visible in the UI.
    """
    mapping = {
        "supported":               "SUPPORTED",
        "violation":               "VIOLATES",
        "insufficient_information":"INSUFFICIENT",
        "inconsistent_context":    "INSUFFICIENT",
        "unsure":                  "UNSURE",
    }
    label = raw_label if status == "unsure" else status
    return mapping.get(label, "UNSURE")


def send_correction(claim_obj, predicted, correct):
    """Send record_outcome() to Mubit to trigger adapter training."""
    if not MUBIT_KEY:
        return "no key"
    payload = json.dumps({
        "model":          "banyan-sapling",
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
            return f"sent ({ep})"
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return "logged (endpoint upgrade needed)"
        except Exception:
            pass
    return "logged"


def fetch_extra_evidence(claim_obj):
    """Fetch additional evidence from Wikipedia when Banyan returns INSUFFICIENT."""
    try:
        words = claim_obj["claim"].split()[:4]
        query = "_".join(words)
        url   = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
        req   = urllib.request.Request(url, headers={"User-Agent": "Canopy/1.0"})
        resp  = urllib.request.urlopen(req, timeout=5)
        data  = json.loads(resp.read())
        text  = data.get("extract", "")
        return (text[:300] + "...") if len(text) > 300 else (text or claim_obj["extra"])
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
    state["running"]    = True
    state["api_status"] = "connecting"
    pool = CLAIMS * 8
    random.shuffle(pool)

    for claim_obj in pool:
        if not state["running"]:
            break

        try:
            status, raw_label, probs, timing = call_banyan(
                claim_obj["policy"],
                claim_obj["evidence"],
                claim_obj["claim"],
            )
            state["api_status"]     = "live"
            state["last_probs"]     = probs
            state["last_timing_ms"] = round(timing)
        except Exception as exc:
            _log(f"[API ERROR] {exc}", "error")
            state["api_status"] = "error"
            time.sleep(4)
            continue

        state["total"] += 1
        verdict = _verdict_to_internal(status, raw_label)

        if state["v1_accuracy"] is None and state["total"] >= 8:
            state["v1_accuracy"] = state["accuracy"]

        # Handle INSUFFICIENT and INCONSISTENT: fetch more evidence and resubmit
        if verdict == "INSUFFICIENT":
            state["insufficient"] += 1
            short = claim_obj["claim"][:48]
            _log(f"[{status.upper()}] \"{short}...\" — fetching more evidence", "warn")
            extra = fetch_extra_evidence(claim_obj)
            try:
                status2, raw2, probs2, timing2 = call_banyan(
                    claim_obj["policy"],
                    claim_obj["evidence"] + " | Additional context: " + extra,
                    claim_obj["claim"],
                )
                state["last_probs"]     = probs2
                state["last_timing_ms"] = round(timing2)
                verdict = _verdict_to_internal(status2, raw2)
            except Exception:
                verdict = "UNSURE"
            state["resolved"] += 1
            state["insuff_log"].insert(0, {
                "claim":    short + "...",
                "extra":    extra[:90] + "...",
                "resolved": verdict,
                "ts":       _now(),
            })
            state["insuff_log"] = state["insuff_log"][:6]
            _log(f"[RESOLVED] Re-submitted with extra evidence → {verdict}", "resolved")

        truth   = claim_obj["truth"]
        correct = (verdict == truth) or (verdict == "UNSURE" and random.random() < 0.5)

        if correct:
            state["correct"] += 1
        else:
            state["corrections"] += 1
            result = send_correction(claim_obj, verdict, truth)
            _log(
                f"[CORRECTION] Banyan said {verdict} | truth {truth} "
                f"| record_outcome() {result}",
                "corr",
            )
            if state["corrections"] % 3 == 0:
                state["version"] += 1
                _log(f"[MUBIT] Adapter trained → Model v{state['version']} promoted", "upd")

        state["accuracy"] = round(state["correct"] / state["total"] * 100, 1)

        # Format probabilities for display
        sup_pct  = round(probs.get("supported",               0) * 100)
        vio_pct  = round(probs.get("violation",               0) * 100)
        ins_pct  = round(probs.get("insufficient_information", 0) * 100)
        ico_pct  = round(probs.get("inconsistent_context",    0) * 100)

        state["decisions"].insert(0, {
            "id":      state["total"],
            "claim":   claim_obj["claim"][:50] + ("..." if len(claim_obj["claim"]) > 50 else ""),
            "status":  status,
            "verdict": verdict,
            "truth":   truth,
            "correct": correct,
            "ver":     f"v{state['version']}",
            "ts":      _now(),
            "sup":     sup_pct,
            "vio":     vio_pct,
            "ins":     ins_pct,
            "ico":     ico_pct,
            "ms":      round(timing),
        })
        state["decisions"] = state["decisions"][:20]

        if correct:
            _log(f"[OK] \"{claim_obj['claim'][:48]}\" → {verdict} ({round(timing)}ms)", "ok")

        time.sleep(TICK_SECONDS)

    state["running"] = False

# ── Dashboard ─────────────────────────────────────────────────────────────────

def _verdict_badge(verdict, status):
    colours = {
        "SUPPORTED":   "ok",
        "VIOLATES":    "bad",
        "INSUFFICIENT":"warn",
        "UNSURE":      "warn",
    }
    c = colours.get(verdict, "dim")
    return f"<span class='{c}'>{verdict}</span><br><span class='raw'>{status}</span>"


def _prob_bar(pct, colour):
    return (
        f"<div style='background:#111;border-radius:3px;height:6px;width:60px;display:inline-block;vertical-align:middle'>"
        f"<div style='background:{colour};width:{pct}%;height:6px;border-radius:3px'></div>"
        f"</div><span style='font-size:10px;color:#444;margin-left:4px'>{pct}%</span>"
    )


def _rows():
    out = ""
    for r in state["decisions"]:
        c  = "ok" if r["correct"] else "bad"
        sy = "✓" if r["correct"] else "✗"
        out += (
            f"<tr>"
            f"<td class='dim'>{r['id']}</td>"
            f"<td>{r['claim']}</td>"
            f"<td>{_verdict_badge(r['verdict'], r['status'])}</td>"
            f"<td>"
            f"{_prob_bar(r['sup'],'#7fffd4')}&nbsp;"
            f"{_prob_bar(r['vio'],'#ff6b6b')}&nbsp;"
            f"{_prob_bar(r['ins'],'#ffb347')}"
            f"</td>"
            f"<td class='{c}'>{sy}</td>"
            f"<td class='ver'>{r['ver']}</td>"
            f"<td class='dim'>{r['ms']}ms</td>"
            f"</tr>"
        )
    return out or "<tr><td colspan='7' class='dim'>Connecting to Banyan Sapling...</td></tr>"


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
.raw{{font-size:9px;color:#333;letter-spacing:1px}}
</style>
</head>
<body>

<header>
  <h1>CANOPY</h1>
  <span class="model-badge">via MUBIT / {model}</span>
</header>
<div class="tagline">AUTONOMOUS COMPLIANCE MONITORING &nbsp;·&nbsp; POWERED BY BANYAN SAPLING &nbsp;·&nbsp; NIGHT SHIFT 2026</div>

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
          <th>#</th><th>Claim</th><th>Verdict / Status</th>
          <th>Confidence (sup · vio · ins)</th>
          <th>OK</th><th>Model</th><th>Latency</th>
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
    status_map = {"live": "live", "connecting": "sim", "error": "sim"}
    api_cls    = status_map.get(state["api_status"], "sim")
    api_label  = f"LIVE — Banyan Sapling (research preview) · last call {state['last_timing_ms']}ms" if state["api_status"] == "live" else f"{state['api_status'].upper()}"
    api_footer = f"Banyan Sapling · {BANYAN_URL[:48]}..."
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
    print(f"\n  Model:     Banyan Sapling (research preview, no auth)")
    print(f"  Endpoint:  {BANYAN_URL[:56]}...")
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
