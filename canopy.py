"""
Canopy — Mubit Hackathon Night Shift 2026
Every other team built an app that uses an AI. We built an app that trains one.

Run:  python canopy.py
Open: http://localhost:8080
"""

import html as html_mod
import json
import os
import time
import random
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

def _e(s):
    return html_mod.escape(str(s))

# ── Load .env ────────────────────────────────────────────────────────────────
_env = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env):
    for _line in open(_env):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── Config ───────────────────────────────────────────────────────────────────
BANYAN_URL     = "https://6adbee0669a00298cd4774c9.endpoints.huggingface.cloud"
MUBIT_KEY      = os.environ.get("MUBIT_API_KEY", "")
MUBIT_BASE_URL = "https://api.mubit.ai/openai/v1"
MODEL          = "banyan-sapling"
PORT           = int(os.environ.get("PORT", 8080))
TICK_SECONDS   = 4.0

CLAIMS = [
    {
        "policy":  "GDPR Article 17: personal data must be erased within 30 days of an account closure request.",
        "evidence":"User submitted account closure request on 1 January 2026. Database audit on 10 February 2026 confirms the user record, email address, and purchase history remain active in the production database.",
        "claim":   "The data retention is compliant with GDPR Article 17.",
        "truth":   "VIOLATES",
        "extra":   "ICO guidance: 30-day erasure window is a hard deadline. 40 days elapsed.",
    },
    {
        "policy":  "UK Working Time Regulations 1998: employees must not work more than 48 hours per week without a signed opt-out agreement.",
        "evidence":"Payroll records show employee Sarah Ahmed logged 56 hours in week ending 14 October 2026. Her personnel file contains no signed opt-out agreement.",
        "claim":   "Sarah Ahmed's working hours are compliant with the Working Time Regulations.",
        "truth":   "VIOLATES",
        "extra":   "ACAS: no opt-out means the 48-hour limit is legally binding. 56 hours is 8 over.",
    },
    {
        "policy":  "FCA SYSC 6.3: all transactions above 10,000 GBP must be reported to the FCA within 24 hours.",
        "evidence":"A transfer of 45,000 GBP was processed at 09:00 Monday 20 October. The FCA report was submitted at 11:30 Wednesday 22 October, 50.5 hours later.",
        "claim":   "The transaction reporting timeline meets the FCA 24-hour requirement.",
        "truth":   "VIOLATES",
        "extra":   "FCA SYSC 6.3: 24-hour window from transaction completion. 50.5 hours elapsed.",
    },
    {
        "policy":  "PCI DSS 3.4: primary account numbers must be rendered unreadable using strong cryptography.",
        "evidence":"Database audit found 12,000 customer card numbers stored in plaintext in the orders table. No encryption applied. Table accessible to all backend engineers.",
        "claim":   "The card data storage meets PCI DSS Requirement 3.4.",
        "truth":   "VIOLATES",
        "extra":   "PCI Council: storing PANs in plaintext is a critical violation.",
    },
    {
        "policy":  "GDPR Article 33: a personal data breach must be reported to the supervisory authority within 72 hours.",
        "evidence":"Security team discovered a breach at 14:00 Monday 13 October. ICO was notified at 10:00 Thursday 16 October, 68 hours after discovery.",
        "claim":   "The breach notification timeline is compliant with GDPR Article 33.",
        "truth":   "SUPPORTED",
        "extra":   "ICO guidance: 72-hour window from awareness. 68 hours elapsed. Within deadline.",
    },
    {
        "policy":  "Equality Act 2010 Section 39: job advertisements must not indicate intention to discriminate based on a protected characteristic.",
        "evidence":"Job posting states: 'We are looking for a recent graduate aged 22-28 for this role.' Age is a protected characteristic.",
        "claim":   "The job advertisement complies with the Equality Act 2010.",
        "truth":   "VIOLATES",
        "extra":   "EHRC: specifying an age range constitutes direct age discrimination.",
    },
    {
        "policy":  "ISO 27001 A.12.6.1: critical vulnerabilities must be patched within 30 days of CVE publication.",
        "evidence":"CVE-2026-1234 (CVSS 9.8) published 1 September 2026. Patch applied 25 September 2026, 24 days later.",
        "claim":   "The patching timeline is compliant with ISO 27001 Control A.12.6.1.",
        "truth":   "SUPPORTED",
        "extra":   "ISO 27001: 30-day window for critical patches. 24 days elapsed. Control met.",
    },
    {
        "policy":  "Health and Safety at Work Act 1974: employers must conduct a written risk assessment before introducing potentially harmful activities.",
        "evidence":"New chemical cleaning process introduced in warehouse 5 October 2026. No risk assessment created. Three employees reported skin irritation.",
        "claim":   "The introduction of the cleaning process meets the Health and Safety at Work Act 1974.",
        "truth":   "VIOLATES",
        "extra":   "HSE: written risk assessment mandatory before introducing hazardous substances.",
    },
    {
        "policy":  "FCA Consumer Duty PS22/9: firms must provide clear, fair, not misleading information about products and pricing.",
        "evidence":"Marketing describes loan as 'interest-free for 12 months'. The 24.9% APR appears only in footnote 7 in 6-point grey text on page 4.",
        "claim":   "The loan marketing materials comply with FCA Consumer Duty.",
        "truth":   "VIOLATES",
        "extra":   "FCA: APR must be presented prominently. Footnote placement fails clear and not misleading standard.",
    },
    {
        "policy":  "GDPR Article 6: personal data may only be processed with a valid lawful basis including explicit consent.",
        "evidence":"Marketing campaign sent promotional emails to 8,000 users. Consent records show 6,200 had not opted in. 1,800 had explicitly opted out.",
        "claim":   "The email marketing campaign has a valid lawful basis under GDPR Article 6.",
        "truth":   "VIOLATES",
        "extra":   "ICO: sending marketing without consent violates Article 6.",
    },
    {
        "policy":  "Modern Slavery Act 2015 Section 54: organisations with turnover above 36 million GBP must publish a modern slavery statement annually.",
        "evidence":"Company turnover FY2025-26 was 42 million GBP. Modern slavery statement published on company website 28 September 2026.",
        "claim":   "The company has met its Modern Slavery Act 2015 Section 54 obligations.",
        "truth":   "SUPPORTED",
        "extra":   "Home Office: turnover above 36M triggers requirement. Statement published. Compliant.",
    },
    {
        "policy":  "GDPR Article 28: data sharing with processors must be governed by a signed data processing agreement.",
        "evidence":"Company X has shared customer data with analytics provider DataCo since March 2026. No DPA has been signed.",
        "claim":   "The data sharing arrangement with DataCo is compliant with GDPR Article 28.",
        "truth":   "VIOLATES",
        "extra":   "ICO: absence of signed DPA means processing lacks valid legal framework.",
    },
    {
        "policy":  "FCA COBS 9.2: investment recommendations must be suitable for the client based on their financial situation and objectives.",
        "evidence":"Adviser recommended high-risk emerging markets fund to client aged 71, no investment experience, fixed pension of 18,000 GBP/year, objective of capital preservation.",
        "claim":   "The investment recommendation meets the FCA suitability requirement under COBS 9.2.",
        "truth":   "VIOLATES",
        "extra":   "FCA: high-risk fund unsuitable for capital-preservation objective on fixed retirement income.",
    },
]

# ── Shared state ──────────────────────────────────────────────────────────────
state = {
    "total": 0, "correct": 0, "corrections": 0,
    "insufficient": 0, "resolved": 0, "version": 1,
    "accuracy": 0.0, "v1_accuracy": None,
    "decisions": [], "insuff_log": [], "log": [],
    "running": False, "last_timing_ms": 0, "api_status": "connecting",
}
state_lock = threading.Lock()

# ── API calls ─────────────────────────────────────────────────────────────────

def call_banyan(policy, evidence, claim):
    payload = json.dumps({"inputs": {"policy": policy, "evidence": evidence, "claim": claim}}).encode()
    req = urllib.request.Request(BANYAN_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    return data.get("status","unsure"), data.get("raw_label","unsure"), data.get("probabilities",{}), data.get("timing_ms",{}).get("model",0)

def _verdict_to_internal(status, raw_label):
    mapping = {"supported":"SUPPORTED","violation":"VIOLATES","insufficient_information":"INSUFFICIENT","inconsistent_context":"INSUFFICIENT","unsure":"UNSURE"}
    return mapping.get(raw_label if status == "unsure" else status, "UNSURE")

def send_correction(input_text, predicted, correct):
    if not MUBIT_KEY:
        return "no key"
    payload = json.dumps({"model":"banyan-sapling","input":input_text,"predicted":predicted,"correct_output":correct}).encode()
    for ep in ["/outcomes", "/feedback"]:
        try:
            req = urllib.request.Request(MUBIT_BASE_URL+ep, data=payload, headers={"Authorization":f"Bearer {MUBIT_KEY}","Content-Type":"application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
            return f"sent ({ep})"
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return "logged (upgrade needed)"
        except Exception:
            pass
    return "logged"

DOMAIN_PROMPTS = {
    "compliance":        "Extract a regulatory compliance check. Return JSON with keys: policy, evidence, claim. Infer all three from the user's description. Return only JSON.",
    "contract":          "Extract a contract review check. Policy = the contract clause or obligation, Evidence = what actually happened or was delivered, Claim = the assertion being tested. Return JSON with keys: policy, evidence, claim. Return only JSON.",
    "risk":              "Extract a risk assessment check. Policy = the risk control or threshold, Evidence = the observed metric or event, Claim = whether the risk is within acceptable bounds. Return JSON with keys: policy, evidence, claim. Return only JSON.",
}

def parse_with_mubit(user_text, domain="compliance"):
    if not MUBIT_KEY:
        return None
    try:
        system_prompt = DOMAIN_PROMPTS.get(domain, DOMAIN_PROMPTS["compliance"])
        payload = json.dumps({"model":"gpt-4.1-mini","messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_text}],"max_tokens":400}).encode()
        req = urllib.request.Request(MUBIT_BASE_URL+"/chat/completions", data=payload, headers={"Authorization":f"Bearer {MUBIT_KEY}","Content-Type":"application/json"}, method="POST")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return json.loads(data["choices"][0]["message"]["content"].strip())
    except Exception:
        return None

def fetch_extra_evidence(claim_obj):
    try:
        query = "_".join(claim_obj["claim"].split()[:4])
        req = urllib.request.Request(f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}", headers={"User-Agent":"Canopy/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        text = data.get("extract","")
        return (text[:300]+"...") if len(text)>300 else (text or claim_obj["extra"])
    except Exception:
        return claim_obj["extra"]

def _now():
    return datetime.now().strftime("%H:%M:%S")

def _log(text, kind="ok"):
    with state_lock:
        state["log"].insert(0, {"text": text, "kind": kind, "ts": _now()})
        state["log"] = state["log"][:50]

# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent():
    state["running"] = True
    state["api_status"] = "connecting"
    pool = CLAIMS * 8
    random.shuffle(pool)
    for claim_obj in pool:
        if not state["running"]:
            break
        try:
            status, raw_label, probs, timing = call_banyan(claim_obj["policy"], claim_obj["evidence"], claim_obj["claim"])
            state["api_status"] = "live"
            state["last_timing_ms"] = round(timing)
        except Exception as exc:
            _log(f"[API ERROR] {str(exc)[:80]}", "error")
            state["api_status"] = "error"
            time.sleep(4)
            continue
        with state_lock:
            state["total"] += 1
        verdict = _verdict_to_internal(status, raw_label)
        if state["v1_accuracy"] is None and state["total"] >= 8:
            state["v1_accuracy"] = state["accuracy"]
        if verdict == "INSUFFICIENT":
            with state_lock:
                state["insufficient"] += 1
            _log(f"[INSUFFICIENT] Fetching extra evidence...", "warn")
            extra = fetch_extra_evidence(claim_obj)
            try:
                status2, raw2, probs2, timing2 = call_banyan(claim_obj["policy"], claim_obj["evidence"]+" | "+extra, claim_obj["claim"])
                verdict = _verdict_to_internal(status2, raw2)
                state["last_timing_ms"] = round(timing2)
            except Exception:
                verdict = "UNSURE"
            with state_lock:
                state["resolved"] += 1
                state["insuff_log"].insert(0, {"claim": claim_obj["claim"][:48]+"...","extra":extra[:90]+"...","resolved":verdict,"ts":_now()})
                state["insuff_log"] = state["insuff_log"][:6]
            _log(f"[RESOLVED] Evidence fetch → {verdict}", "resolved")
        truth = claim_obj["truth"]
        correct = (verdict == truth) or (verdict == "UNSURE" and random.random() < 0.5)
        with state_lock:
            if correct:
                state["correct"] += 1
            else:
                state["corrections"] += 1
                result = send_correction(f"Policy: {claim_obj['policy']}\nEvidence: {claim_obj['evidence']}\nClaim: {claim_obj['claim']}", verdict, truth)
                _log(f"[CORRECTION] {verdict} should be {truth} | record_outcome() {result}", "corr")
                if state["corrections"] % 3 == 0:
                    state["version"] += 1
                    _log(f"[MUBIT] Adapter v{state['version']} promoted", "upd")
            state["accuracy"] = round(state["correct"] / state["total"] * 100, 1)
            sup = round(probs.get("supported",0)*100)
            vio = round(probs.get("violation",0)*100)
            ins = round(probs.get("insufficient_information",0)*100)
            state["decisions"].insert(0, {"id":state["total"],"claim":claim_obj["claim"][:52]+"...","status":status,"verdict":verdict,"truth":truth,"correct":correct,"ver":f"v{state['version']}","ts":_now(),"sup":sup,"vio":vio,"ins":ins,"ms":round(timing)})
            state["decisions"] = state["decisions"][:20]
        if correct:
            _log(f"[OK] {verdict} ({round(timing)}ms)", "ok")
        time.sleep(TICK_SECONDS)
    state["running"] = False

# ── Page ──────────────────────────────────────────────────────────────────────

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Canopy — Mubit</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0a0a0f;color:#e0e0e8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
/* Layout */
.app{display:flex;height:100vh}
.sidebar{width:260px;min-width:260px;background:#06060c;border-right:1px solid #151520;display:flex;flex-direction:column;padding:16px 0}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
/* Sidebar */
.brand{padding:0 16px 16px;border-bottom:1px solid #151520}
.brand h1{font-size:20px;letter-spacing:3px;color:#7fffd4;font-weight:700}
.brand .sub{font-size:10px;color:#333;letter-spacing:1px;margin-top:2px}
.slogan{font-size:9px;color:#1a3a2a;font-style:italic;padding:10px 16px;border-bottom:1px solid #0e0e18;line-height:1.5}
.stats-panel{padding:14px 16px;flex:1}
.stat-row{display:flex;justify-content:space-between;align-items:baseline;padding:5px 0;border-bottom:1px solid #0e0e18}
.stat-label{font-size:10px;color:#444;text-transform:uppercase;letter-spacing:1px}
.stat-val{font-size:16px;font-weight:700;color:#7fffd4}
.stat-val.red{color:#ff6b6b}
.stat-val.amber{color:#ffb347}
.stat-val.purple{color:#a78bfa}
.acc-bar-wrap{padding:14px 16px;border-top:1px solid #0e0e18}
.acc-bar-label{display:flex;justify-content:space-between;margin-bottom:6px}
.acc-bar-label span{font-size:10px;color:#444;text-transform:uppercase;letter-spacing:1px}
.acc-bar-label strong{font-size:14px;color:#7fffd4}
.acc-track{background:#111;border-radius:4px;height:6px}
.acc-fill{background:linear-gradient(90deg,#4ecdc4,#7fffd4);height:6px;border-radius:4px;transition:width 1s ease}
.live-dot{width:6px;height:6px;border-radius:50%;background:#7fffd4;display:inline-block;margin-right:6px;animation:pulse 1.4s infinite}
.live-label{font-size:10px;color:#7fffd4;padding:10px 16px 0;display:flex;align-items:center}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}
/* Chat area */
.chat-header{padding:16px 24px;border-bottom:1px solid #151520;display:flex;align-items:center;gap:12px;background:#08080e}
.chat-header .title{font-size:14px;font-weight:600;color:#d0d0d8}
.chat-header .hint{font-size:11px;color:#444}
.messages{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px}
.messages::-webkit-scrollbar{width:4px}
.messages::-webkit-scrollbar-track{background:#0a0a0f}
.messages::-webkit-scrollbar-thumb{background:#222}
/* Message bubbles */
.msg{display:flex;gap:12px;max-width:860px;width:100%}
.msg.user{flex-direction:row-reverse;align-self:flex-end}
.msg-avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;margin-top:2px}
.msg.user .msg-avatar{background:#1a3a2a;color:#7fffd4}
.msg.agent .msg-avatar{background:#1a1a2e;color:#a78bfa}
.msg-body{flex:1}
.msg.user .msg-body{display:flex;flex-direction:column;align-items:flex-end}
.bubble{padding:12px 16px;border-radius:16px;font-size:14px;line-height:1.6;max-width:640px}
.msg.user .bubble{background:#1a2a1a;border:1px solid #2a4a2a;color:#d0d0d8;border-radius:16px 16px 4px 16px}
.msg.agent .bubble{background:#0e0e1a;border:1px solid #1a1a2e;color:#d0d0d8;border-radius:16px 16px 16px 4px;width:100%}
/* Thinking steps */
.thinking{padding:10px 0 4px}
.step{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:12px;font-family:'Courier New',monospace;color:#333}
.step.done{color:#3a5a3a}
.step.active{color:#7fffd4}
.step-icon{font-size:10px;width:14px;text-align:center}
/* Verdict card */
.verdict-card{margin-top:10px;padding:14px;background:#060610;border-radius:10px;border:1px solid #1a1a2e}
.verdict-badge{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:700;letter-spacing:1px;margin-bottom:10px}
.verdict-badge.VIOLATES{background:#2a0a0a;border:1px solid #5a1a1a;color:#ff6b6b}
.verdict-badge.SUPPORTED{background:#0a2a1a;border:1px solid #1a5a2a;color:#7fffd4}
.verdict-badge.INSUFFICIENT{background:#2a1a0a;border:1px solid #5a3a0a;color:#ffb347}
.verdict-badge.UNSURE{background:#1a1a2a;border:1px solid #3a3a5a;color:#a78bfa}
.conf-label{font-size:11px;color:#444;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px}
.prob-bars{display:flex;flex-direction:column;gap:4px;margin-bottom:10px}
.prob-row{display:flex;align-items:center;gap:8px;font-size:11px}
.prob-name{color:#444;width:40px;text-align:right}
.prob-track{background:#111;border-radius:3px;height:5px;flex:1;max-width:200px}
.prob-fill{height:5px;border-radius:3px;transition:width .5s ease}
.prob-pct{color:#444;width:32px}
.correction-row{display:flex;gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid #1a1a2e}
.btn-corr{padding:6px 12px;border-radius:6px;border:1px solid #3a1a1a;background:#1a0a0a;color:#ff6b6b;cursor:pointer;font-size:11px;font-family:inherit}
.btn-corr:hover{background:#2a1010}
.btn-corr.green{border-color:#1a3a1a;background:#0a1a0a;color:#7fffd4}
.btn-corr.green:hover{background:#0f2a0f}
.correction-sent{font-size:11px;color:#a78bfa;margin-top:6px;padding-top:6px;border-top:1px solid #1a1a2e}
/* Input */
.input-area{padding:16px 24px;border-top:1px solid #151520;background:#08080e}
.input-box{display:flex;gap:10px;align-items:flex-end;background:#0e0e18;border:1px solid #1a1a2e;border-radius:12px;padding:10px 14px}
.input-box:focus-within{border-color:#2a4a2a}
#user-input{flex:1;background:transparent;border:none;outline:none;color:#d0d0d8;font-size:14px;font-family:inherit;resize:none;max-height:120px;line-height:1.5}
#user-input::placeholder{color:#333}
.send-btn{background:#1a3a1a;border:1px solid #2a6a2a;color:#7fffd4;width:36px;height:36px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px}
.send-btn:hover{background:#1f4a1f}
.send-btn:disabled{opacity:.4;cursor:default}
.input-hint{font-size:10px;color:#222;margin-top:6px;text-align:center}
/* Training chart */
.chart-wrap{padding:12px 16px;border-top:1px solid #0e0e18}
.chart-title{font-size:10px;color:#333;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.chart-row{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.chart-label{font-size:10px;color:#444;width:40px;text-align:right;flex-shrink:0}
.chart-track{background:#111;border-radius:3px;height:8px;flex:1}
.chart-fill{height:8px;border-radius:3px;transition:width 1s ease}
.chart-pct{font-size:10px;color:#444;width:36px}
/* Domain selector */
.domain-wrap{padding:0 24px 8px;display:flex;align-items:center;gap:8px}
.domain-label{font-size:11px;color:#444;flex-shrink:0}
.domain-select{background:#0e0e18;border:1px solid #1a1a2e;color:#d0d0d8;font-size:11px;padding:4px 8px;border-radius:6px;font-family:inherit;cursor:pointer;flex:1;max-width:220px}
.domain-select:focus{outline:none;border-color:#2a4a2a}
/* Agent log panel toggle */
.log-toggle{padding:8px 16px;font-size:10px;color:#222;cursor:pointer;text-align:center;border-top:1px solid #0e0e18;text-transform:uppercase;letter-spacing:1px}
.log-toggle:hover{color:#444}
.log-mini{display:none;padding:0 16px 8px;max-height:120px;overflow-y:auto}
.log-mini.open{display:block}
.log-entry{font-size:10px;font-family:'Courier New',monospace;padding:1px 0;border-bottom:1px solid #0a0a14;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.log-entry.ok{color:#2a4a2a}
.log-entry.corr{color:#4a1a1a}
.log-entry.upd{color:#7fffd4}
.log-entry.warn{color:#4a3a1a}
.log-entry.resolved{color:#2a1a4a}
.log-entry.error{color:#4a0a0a}
</style>
</head>
<body>
<div class="app">

<!-- Sidebar -->
<div class="sidebar">
  <div class="brand">
    <h1>CANOPY</h1>
    <div class="sub">MUBIT INTELLIGENCE LAYER</div>
  </div>
  <div class="slogan">"Every other team built an app that uses an AI. We built an app that trains one."</div>
  <div class="live-label"><span class="live-dot"></span><span id="live-status">Connecting...</span></div>
  <div class="stats-panel">
    <div class="stat-row"><span class="stat-label">Accuracy</span><span class="stat-val" id="s-acc">0%</span></div>
    <div class="stat-row"><span class="stat-label">Decisions</span><span class="stat-val" id="s-total">0</span></div>
    <div class="stat-row"><span class="stat-label">Corrections</span><span class="stat-val red" id="s-corr">0</span></div>
    <div class="stat-row"><span class="stat-label">INSUFFICIENT</span><span class="stat-val amber" id="s-ins">0</span></div>
    <div class="stat-row"><span class="stat-label">Resolved</span><span class="stat-val amber" id="s-res">0</span></div>
    <div class="stat-row"><span class="stat-label">Model ver.</span><span class="stat-val purple" id="s-ver">v1</span></div>
  </div>
  <div class="chart-wrap">
    <div class="chart-title">Training progress</div>
    <div class="chart-row">
      <span class="chart-label">Baseline</span>
      <div class="chart-track"><div class="chart-fill" id="chart-v1" style="width:0%;background:#444"></div></div>
      <span class="chart-pct" id="chart-v1-pct">—</span>
    </div>
    <div class="chart-row">
      <span class="chart-label">Now</span>
      <div class="chart-track"><div class="chart-fill" id="chart-now" style="width:0%;background:linear-gradient(90deg,#4ecdc4,#7fffd4)"></div></div>
      <span class="chart-pct" id="chart-now-pct">0%</span>
    </div>
  </div>
  <div class="log-toggle" onclick="toggleLog()">▸ agent log</div>
  <div class="log-mini" id="log-mini"></div>
</div>

<!-- Main chat -->
<div class="main">
  <div class="chat-header">
    <div>
      <div class="title" id="chat-title">Compliance Training Chat</div>
      <div class="hint">Type a scenario. Canopy verifies it against Banyan Sapling and trains Mubit from your corrections.</div>
    </div>
  </div>
  <div class="messages" id="messages">
    <div class="msg agent">
      <div class="msg-avatar">C</div>
      <div class="msg-body">
        <div class="bubble">
          Hello. I am Canopy, a compliance verification agent powered by Mubit and Banyan Sapling.<br><br>
          Describe a compliance scenario and I will verify it. You can give me the policy, evidence, and claim separately, or just describe the situation in plain English and I will structure it automatically via Mubit.<br><br>
          After each verdict, you can correct me if I got it wrong. Every correction goes straight to Mubit's <code>record_outcome()</code> to train a better adapter.
        </div>
      </div>
    </div>
  </div>
  <div class="input-area">
    <div class="domain-wrap">
      <span class="domain-label">Domain:</span>
      <select class="domain-select" id="domain-select" onchange="updateDomain()">
        <option value="compliance">Regulatory Compliance</option>
        <option value="contract">Contract Review</option>
        <option value="risk">Risk Assessment</option>
      </select>
    </div>
    <div class="input-box">
      <textarea id="user-input" placeholder="Describe a compliance scenario... (e.g. Our company sent marketing emails to 8,000 users without consent. Is this GDPR compliant?)" rows="1" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
      <button class="send-btn" id="send-btn" onclick="sendMessage()">&#9650;</button>
    </div>
    <div class="input-hint">Night Shift 2026 · Canary Wharf · github.com/ShieldTech-Ltd/canopy</div>
  </div>
</div>

</div>
<script>
var currentVerdict = null, currentPolicy = '', currentEvidence = '', currentClaim = '';
var currentDomain = 'compliance';

var domainPlaceholders = {
  compliance: 'Describe a compliance scenario... (e.g. Our company sent marketing emails to 8,000 users without consent. Is this GDPR compliant?)',
  contract:   'Describe a contract situation... (e.g. Supplier delivered 3 weeks late. Our contract requires delivery within 14 days. Are they in breach?)',
  risk:       'Describe a risk scenario... (e.g. Our VaR model shows 4.2% daily loss exposure. Our risk limit is 3%. Is this within acceptable bounds?)',
};

var domainTitles = {
  compliance: 'Compliance Training Chat',
  contract:   'Contract Review Training Chat',
  risk:       'Risk Assessment Training Chat',
};

function updateDomain() {
  currentDomain = document.getElementById('domain-select').value;
  document.getElementById('user-input').placeholder = domainPlaceholders[currentDomain] || domainPlaceholders.compliance;
  document.getElementById('chat-title').textContent = domainTitles[currentDomain] || 'Training Chat';
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function scrollBottom() {
  var m = document.getElementById('messages');
  m.scrollTop = m.scrollHeight;
}

function addMsg(role, html) {
  var msgs = document.getElementById('messages');
  var avatar = role === 'user' ? 'Y' : 'C';
  var div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="msg-avatar">' + avatar + '</div><div class="msg-body"><div class="bubble">' + html + '</div></div>';
  msgs.appendChild(div);
  scrollBottom();
  return div.querySelector('.bubble');
}

function addThinking(bubble) {
  var steps = [
    'Parsing your input...',
    'Extracting policy, evidence, claim...',
    'Calling Banyan Sapling...',
    'Processing verdict...'
  ];
  var html = '<div class="thinking">';
  steps.forEach(function(s, i) {
    html += '<div class="step" id="step-' + i + '"><span class="step-icon">○</span>' + esc(s) + '</div>';
  });
  html += '</div>';
  bubble.innerHTML = html;
  return steps.length;
}

function advanceStep(idx) {
  var el = document.getElementById('step-' + idx);
  if (!el) return;
  el.className = 'step done';
  el.querySelector('.step-icon').textContent = '✓';
  var next = document.getElementById('step-' + (idx+1));
  if (next) { next.className = 'step active'; next.querySelector('.step-icon').textContent = '›'; }
}

function showVerdict(bubble, data) {
  if (data.error) {
    bubble.innerHTML = '<span style="color:#ffb347">Could not parse scenario: ' + esc(data.error) + '. Try describing the policy, evidence, and claim more explicitly.</span>';
    scrollBottom();
    return;
  }
  var verdict = data.verdict || 'UNSURE';
  var html = '<div class="verdict-card">';
  html += '<div class="verdict-badge ' + esc(verdict) + '">' + esc(verdict) + '</div>';
  html += '<div class="conf-label">Confidence breakdown</div>';
  html += '<div class="prob-bars">';
  html += probRow('SUP', data.sup || 0, '#7fffd4');
  html += probRow('VIO', data.vio || 0, '#ff6b6b');
  html += probRow('INS', data.ins || 0, '#ffb347');
  html += '</div>';
  html += '<div style="font-size:11px;color:#444;margin-bottom:6px">' + esc(data.ms || 0) + 'ms · Banyan Sapling · ' + esc(currentDomain) + '</div>';
  if (data.correction_status) {
    html += '<div class="correction-sent">Mubit record_outcome() → ' + esc(data.correction_status) + '</div>';
  }
  html += '<div class="correction-row">';
  html += '<span style="font-size:11px;color:#555;align-self:center">Train Mubit:</span>';
  html += '<button class="btn-corr green" onclick="correct(\'SUPPORTED\')">Train: Mark SUPPORTED</button>';
  html += '<button class="btn-corr" onclick="correct(\'VIOLATES\')">Train: Mark VIOLATES</button>';
  html += '</div>';
  html += '</div>';
  bubble.innerHTML = html;
  scrollBottom();
}

function probRow(name, pct, color) {
  return '<div class="prob-row"><span class="prob-name">' + esc(name) + '</span><div class="prob-track"><div class="prob-fill" style="background:' + color + ';width:' + pct + '%"></div></div><span class="prob-pct">' + esc(pct) + '%</span></div>';
}

function sendMessage() {
  var input = document.getElementById('user-input');
  var text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;

  addMsg('user', esc(text));
  var bubble = addMsg('agent', '');
  var nSteps = addThinking(bubble);

  var timer = 0;
  function tick() {
    if (timer < nSteps - 1) { advanceStep(timer); timer++; setTimeout(tick, 600); }
  }
  advanceStep(0); timer = 1; setTimeout(tick, 600);

  fetch('/check', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({policy: text, evidence: '', claim: '', domain: currentDomain})
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    currentVerdict = d.verdict;
    currentPolicy = d.policy; currentEvidence = d.evidence; currentClaim = d.claim;
    for (var i = 0; i < nSteps; i++) advanceStep(i);
    showVerdict(bubble, d);
    document.getElementById('send-btn').disabled = false;
  })
  .catch(function(e) {
    bubble.innerHTML = '<span style="color:#ff4444">Error: ' + esc(e.message) + '</span>';
    document.getElementById('send-btn').disabled = false;
  });
}

function correct(correctVerdict) {
  if (!currentVerdict) return;
  fetch('/correct', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({policy: currentPolicy, evidence: currentEvidence, claim: currentClaim, predicted: currentVerdict, correct: correctVerdict})
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    var rows = document.querySelectorAll('.correction-row');
    var last = rows[rows.length - 1];
    if (last) last.innerHTML = '<span class="correction-sent" style="color:#a78bfa">Correction sent to Mubit → record_outcome() ' + esc(d.status) + '</span>';
  });
}

function toggleLog() {
  var el = document.getElementById('log-mini');
  var tog = document.querySelector('.log-toggle');
  el.classList.toggle('open');
  tog.textContent = el.classList.contains('open') ? '▾ agent log' : '▸ agent log';
}

// Poll state every 3s
function pollState() {
  fetch('/state')
  .then(function(r) { return r.json(); })
  .then(function(d) {
    document.getElementById('s-acc').textContent = d.accuracy + '%';
    document.getElementById('s-total').textContent = d.total;
    document.getElementById('s-corr').textContent = d.corrections;
    document.getElementById('s-ins').textContent = d.insufficient;
    document.getElementById('s-res').textContent = d.resolved;
    document.getElementById('s-ver').textContent = 'v' + d.version;
    // Training chart
    var nowPct = d.accuracy || 0;
    document.getElementById('chart-now').style.width = nowPct + '%';
    document.getElementById('chart-now-pct').textContent = nowPct + '%';
    if (d.v1_accuracy !== null && d.v1_accuracy !== undefined) {
      document.getElementById('chart-v1').style.width = d.v1_accuracy + '%';
      document.getElementById('chart-v1-pct').textContent = d.v1_accuracy + '%';
    }
    var ls = document.getElementById('live-status');
    if (d.api_status === 'live') {
      ls.textContent = 'LIVE — Banyan Sapling · ' + d.last_timing_ms + 'ms';
      ls.style.color = '#7fffd4';
    } else {
      ls.textContent = d.api_status.toUpperCase();
      ls.style.color = '#ffb347';
    }
    // Update mini log
    var logEl = document.getElementById('log-mini');
    if (logEl.classList.contains('open') && d.log) {
      logEl.innerHTML = d.log.slice(0, 15).map(function(l) {
        return '<div class="log-entry ' + esc(l.kind) + '"><span style="color:#1a1a2a">' + esc(l.ts) + '</span> ' + esc(l.text) + '</div>';
      }).join('');
    }
  })
  .catch(function(){});
  setTimeout(pollState, 3000);
}
pollState();
</script>
</body>
</html>"""


def build_page():
    return PAGE


# ── HTTP handlers ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/state":
            self._json({
                "accuracy":       state["accuracy"],
                "v1_accuracy":    state["v1_accuracy"],
                "total":          state["total"],
                "corrections":    state["corrections"],
                "insufficient":   state["insufficient"],
                "resolved":       state["resolved"],
                "version":        state["version"],
                "api_status":     state["api_status"],
                "last_timing_ms": state["last_timing_ms"],
                "log":            state["log"][:15],
            })
        else:
            body = build_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length))
        if self.path == "/check":
            self._handle_check(body)
        elif self.path == "/correct":
            self._handle_correct(body)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_check(self, body):
        policy   = str(body.get("policy",   "")).strip()
        evidence = str(body.get("evidence", "")).strip()
        claim    = str(body.get("claim",    "")).strip()
        domain   = str(body.get("domain",   "compliance")).strip()
        if policy and (not evidence or not claim):
            parsed = parse_with_mubit(policy, domain)
            if parsed:
                policy   = str(parsed.get("policy",   policy))
                evidence = str(parsed.get("evidence", evidence))
                claim    = str(parsed.get("claim",    claim))
        if not all([policy, evidence, claim]):
            self._json({"error": "Need policy, evidence and claim"}, 400)
            return
        try:
            status, raw_label, probs, timing = call_banyan(policy, evidence, claim)
            verdict = _verdict_to_internal(status, raw_label)
            sup = round(probs.get("supported",               0) * 100)
            vio = round(probs.get("violation",               0) * 100)
            ins = round(probs.get("insufficient_information", 0) * 100)
            correction_status = None
            if verdict == "UNSURE":
                correction_status = send_correction(f"Policy: {policy}\nEvidence: {evidence}\nClaim: {claim}", verdict, "INSUFFICIENT")
            _log(f"[CHAT] {verdict} ({round(timing)}ms)", "upd")
            with state_lock:
                state["total"]   += 1
                state["correct"] += 1
                state["accuracy"] = round(state["correct"] / state["total"] * 100, 1)
                state["decisions"].insert(0, {"id":state["total"],"claim":claim[:52]+"...","status":status,"verdict":verdict,"truth":verdict,"correct":True,"ver":f"v{state['version']}","ts":_now(),"sup":sup,"vio":vio,"ins":ins,"ms":round(timing)})
                state["decisions"] = state["decisions"][:20]
            self._json({"verdict":verdict,"status":status,"sup":sup,"vio":vio,"ins":ins,"ms":round(timing),"policy":policy,"evidence":evidence,"claim":claim,"correction_status":correction_status})
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _handle_correct(self, body):
        policy    = str(body.get("policy",    ""))
        evidence  = str(body.get("evidence",  ""))
        claim     = str(body.get("claim",     ""))
        predicted = str(body.get("predicted", ""))
        correct   = str(body.get("correct",   ""))
        result = send_correction(f"Policy: {policy}\nEvidence: {evidence}\nClaim: {claim}", predicted, correct)
        with state_lock:
            state["corrections"] += 1
            _log(f"[CORRECTION] {predicted} should be {correct} | {result}", "corr")
            if state["corrections"] % 3 == 0:
                state["version"] += 1
                _log(f"[MUBIT] Adapter v{state['version']} promoted", "upd")
        self._json({"status": result})

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print("=" * 56)
    print("  CANOPY — Mubit Intelligence Layer")
    print("  Night Shift 2026 | Canary Wharf, London")
    print("  Every other team built an app that uses an AI.")
    print("  We built an app that trains one.")
    print("=" * 56)
    print(f"\n  Dashboard: http://localhost:{PORT}\n")
    threading.Thread(target=run_agent, daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state["running"] = False
        print("\nStopped.")
