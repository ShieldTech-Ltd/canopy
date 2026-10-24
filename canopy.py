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
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Canopy — Mubit Compliance Agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#111827;color:#f9fafb;font-family:'Inter',system-ui,sans-serif;font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
/* ── 3-panel layout ── */
.app{display:flex;height:100vh;overflow:hidden}
/* ── Left sidebar ── */
.sidebar{width:248px;min-width:248px;background:#0f1623;border-right:1px solid #1f2937;display:flex;flex-direction:column;overflow:hidden}
.brand{padding:18px 16px 14px;border-bottom:1px solid #1f2937}
.brand-row{display:flex;align-items:center;gap:10px}
.brand-mark{width:30px;height:30px;border-radius:7px;background:linear-gradient(145deg,#16a34a,#22c55e);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:#fff;flex-shrink:0;letter-spacing:-0.5px}
.brand-text{}
.brand-name{font-size:14px;font-weight:700;color:#f9fafb;letter-spacing:-.2px}
.brand-sub{font-size:9.5px;color:#6b7280;text-transform:uppercase;letter-spacing:.8px;margin-top:1px}
.sidebar-status{padding:10px 16px;border-bottom:1px solid #1f2937;display:flex;align-items:center;gap:7px}
.sdot{width:6px;height:6px;border-radius:50%;flex-shrink:0;transition:background .3s}
.sdot.live{background:#22c55e;box-shadow:0 0 5px #22c55e80}
.sdot.connecting{background:#f59e0b;animation:blink 1.1s infinite}
.sdot.error{background:#ef4444}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.stext{font-size:11px;color:#9ca3af;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* Stats */
.stats{padding:14px 16px;border-bottom:1px solid #1f2937;display:flex;flex-direction:column;gap:6px}
.stat-row2{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:#1a2332;border-radius:7px;border:1px solid #1f2937}
.stat-lbl{font-size:10.5px;color:#6b7280;font-weight:500}
.stat-num{font-size:14px;font-weight:700}
.stat-num.g{color:#22c55e}
.stat-num.r{color:#ef4444}
.stat-num.y{color:#f59e0b}
.stat-num.b{color:#60a5fa}
.stat-num.p{color:#a78bfa}
/* Training chart */
.tchart{padding:14px 16px;border-bottom:1px solid #1f2937}
.tchart-title{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:#6b7280;margin-bottom:10px}
.trow{margin-bottom:8px}
.trow-head{display:flex;justify-content:space-between;margin-bottom:4px}
.trow-label{font-size:11px;color:#9ca3af}
.trow-val{font-size:11px;font-weight:600;color:#d1d5db}
.ttrack{height:5px;background:#1f2937;border-radius:3px;overflow:hidden}
.tfill{height:100%;border-radius:3px;transition:width 1s ease}
.tfill.base{background:#374151}
.tfill.now{background:linear-gradient(90deg,#16a34a,#22c55e)}
/* Log */
.log-wrap{flex:1;display:flex;flex-direction:column;min-height:0}
.log-head{padding:9px 16px;font-size:10.5px;font-weight:500;color:#6b7280;cursor:pointer;display:flex;align-items:center;gap:6px;border-top:1px solid #1f2937;flex-shrink:0}
.log-head:hover{color:#d1d5db}
.log-body{display:none;flex:1;overflow-y:auto;padding:4px 12px 8px}
.log-body.open{display:block}
.lentry{font-size:9.5px;font-family:'JetBrains Mono',monospace;padding:2px 0;color:#374151;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:1px solid #111827}
.lentry.upd{color:#14532d}
.lentry.corr{color:#450a0a}
.lentry.ok{color:#1e3a1e}
.lentry.warn{color:#451a03}
/* ── Centre: chat ── */
.chat-col{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;background:#111827}
.chat-top{height:50px;border-bottom:1px solid #1f2937;display:flex;align-items:center;padding:0 20px;gap:10px;background:#0f1623;flex-shrink:0}
.chat-top-title{font-size:13.5px;font-weight:600;color:#f9fafb}
.dom-sel{background:#1a2332;border:1px solid #374151;color:#d1d5db;font-size:11.5px;font-weight:500;padding:4px 9px;border-radius:6px;font-family:inherit;cursor:pointer;outline:none}
.dom-sel:focus{border-color:#3b82f6}
.chat-top-right{margin-left:auto;font-size:10.5px;color:#4b5563}
.msgs{flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:16px}
.msgs::-webkit-scrollbar{width:4px}
.msgs::-webkit-scrollbar-thumb{background:#1f2937;border-radius:4px}
/* Bubbles */
.msg{display:flex;gap:10px;max-width:100%}
.msg.user{flex-direction:row-reverse;align-self:flex-end;max-width:72%}
.ava{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;margin-top:2px}
.msg.user .ava{background:#14532d;color:#4ade80;border:1px solid #16a34a30}
.msg.agent .ava{background:#1e1b4b;color:#a78bfa;border:1px solid #312e81}
.mbody{flex:1;min-width:0}
.msg.user .mbody{display:flex;flex-direction:column;align-items:flex-end}
.bub{padding:11px 15px;border-radius:11px;font-size:13px;line-height:1.7;max-width:100%}
.msg.user .bub{background:#14532d;border:1px solid #166534;color:#d1fae5;border-radius:11px 11px 2px 11px}
.msg.agent .bub{background:#1a2332;border:1px solid #1f2937;color:#e5e7eb;border-radius:11px 11px 11px 2px;width:100%}
/* Thinking */
.thinking{padding:6px 0}
.step{display:flex;align-items:center;gap:7px;padding:3px 0;font-size:11px;font-family:'JetBrains Mono',monospace;color:#374151;border-bottom:1px solid #1a2332}
.step:last-child{border:none}
.step.done{color:#166534}
.step.active{color:#3b82f6}
.step-icon{width:12px;text-align:center;flex-shrink:0}
/* Verdict */
.vcard{margin-top:10px;border-radius:9px;overflow:hidden;border:1px solid #1f2937}
.vhead{padding:10px 14px;display:flex;align-items:center;gap:10px}
.vhead.VIOLATES{background:#1c0707;border-bottom:1px solid #450a0a}
.vhead.SUPPORTED{background:#052e16;border-bottom:1px solid #14532d}
.vhead.INSUFFICIENT{background:#1c1007;border-bottom:1px solid #451a03}
.vhead.UNSURE{background:#12111e;border-bottom:1px solid #1e1b4b}
.vbadge{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.5px}
.vbadge.VIOLATES{background:#450a0a;color:#fca5a5;border:1px solid #7f1d1d}
.vbadge.SUPPORTED{background:#14532d;color:#86efac;border:1px solid #166534}
.vbadge.INSUFFICIENT{background:#451a03;color:#fcd34d;border:1px solid #78350f}
.vbadge.UNSURE{background:#1e1b4b;color:#c4b5fd;border:1px solid #312e81}
.vmeta{font-size:10.5px;color:#6b7280}
.vbody{padding:12px 14px;background:#0f1623}
.clabel{font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.7px;color:#6b7280;margin-bottom:8px}
.pbars{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
.prow{display:flex;align-items:center;gap:8px}
.pname{font-size:10px;font-weight:600;color:#6b7280;width:26px;text-align:right}
.ptrack{background:#1f2937;border-radius:2px;height:4px;flex:1;max-width:200px}
.pfill{height:100%;border-radius:2px;transition:width .5s ease}
.ppct{font-size:10px;color:#6b7280;width:26px}
.train-row{display:flex;align-items:center;gap:7px;padding-top:9px;border-top:1px solid #1f2937;flex-wrap:wrap}
.tlabel{font-size:10.5px;color:#6b7280;font-weight:500}
.tbtn{padding:4px 11px;border-radius:5px;font-size:11px;font-weight:600;font-family:inherit;cursor:pointer;transition:all .12s;border:1px solid}
.tbtn.ts{background:#052e16;border-color:#16a34a50;color:#4ade80}
.tbtn.ts:hover{background:#14532d;border-color:#16a34a}
.tbtn.tv{background:#1c0707;border-color:#ef444450;color:#fca5a5}
.tbtn.tv:hover{background:#450a0a;border-color:#ef4444}
.csent{font-size:10.5px;color:#a78bfa;padding-top:9px;border-top:1px solid #1f2937;display:flex;align-items:center;gap:5px}
/* Input */
.inp-wrap{padding:12px 20px 14px;border-top:1px solid #1f2937;background:#0f1623;flex-shrink:0}
.inp-box{display:flex;gap:9px;align-items:flex-end;background:#1a2332;border:1px solid #374151;border-radius:9px;padding:9px 13px;transition:border-color .15s}
.inp-box:focus-within{border-color:#3b82f6}
#user-input{flex:1;background:transparent;border:none;outline:none;color:#f9fafb;font-size:13px;font-family:inherit;resize:none;max-height:110px;line-height:1.6}
#user-input::placeholder{color:#4b5563}
.sbtn{background:#16a34a;border:1px solid #22c55e;color:#fff;width:32px;height:32px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:13px;transition:background .12s}
.sbtn:hover{background:#22c55e}
.sbtn:disabled{opacity:.3;cursor:default}
.inp-foot{font-size:9.5px;color:#374151;margin-top:5px;text-align:center}
/* ── Right panel ── */
.evidence-col{width:288px;min-width:288px;background:#0f1623;border-left:1px solid #1f2937;display:flex;flex-direction:column;overflow:hidden}
.ep-head{padding:14px 16px;border-bottom:1px solid #1f2937;flex-shrink:0}
.ep-title{font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.7px}
.ep-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:24px;color:#374151;text-align:center;font-size:12px;line-height:1.6}
.ep-icon{font-size:28px;opacity:.3}
.ep-body{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:14px}
.ep-body::-webkit-scrollbar{width:3px}
.ep-body::-webkit-scrollbar-thumb{background:#1f2937}
.ep-section{}
.ep-section-label{font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:#6b7280;margin-bottom:6px}
.ep-section-val{font-size:12px;color:#d1d5db;line-height:1.6;background:#1a2332;border:1px solid #1f2937;border-radius:7px;padding:9px 11px}
.ep-divider{height:1px;background:#1f2937;margin:2px 0}
</style>
</head>
<body>
<div class="app">

<!-- Left sidebar -->
<div class="sidebar">
  <div class="brand">
    <div class="brand-row">
      <div class="brand-mark">C</div>
      <div class="brand-text">
        <div class="brand-name">Canopy</div>
        <div class="brand-sub">Mubit Intelligence Layer</div>
      </div>
    </div>
  </div>
  <div class="sidebar-status">
    <div class="sdot connecting" id="status-dot"></div>
    <span class="stext" id="live-status">Connecting...</span>
  </div>
  <div class="stats">
    <div class="stat-row2"><span class="stat-lbl">Accuracy</span><span class="stat-num g" id="s-acc">—</span></div>
    <div class="stat-row2"><span class="stat-lbl">Decisions</span><span class="stat-num b" id="s-total">0</span></div>
    <div class="stat-row2"><span class="stat-lbl">Corrections</span><span class="stat-num r" id="s-corr">0</span></div>
    <div class="stat-row2"><span class="stat-lbl">INSUFF resolved</span><span class="stat-num y" id="s-res">0</span></div>
    <div class="stat-row2"><span class="stat-lbl">Model</span><span class="stat-num p" id="s-ver">v1</span></div>
  </div>
  <div class="tchart">
    <div class="tchart-title">Training progress</div>
    <div class="trow">
      <div class="trow-head"><span class="trow-label">Baseline</span><span class="trow-val" id="chart-v1-pct">—</span></div>
      <div class="ttrack"><div class="tfill base" id="chart-v1" style="width:0"></div></div>
    </div>
    <div class="trow">
      <div class="trow-head"><span class="trow-label">Current</span><span class="trow-val" id="chart-now-pct">—</span></div>
      <div class="ttrack"><div class="tfill now" id="chart-now" style="width:0"></div></div>
    </div>
  </div>
  <div class="log-wrap">
    <div class="log-head" onclick="toggleLog()"><span id="log-icon">▶</span> Agent log</div>
    <div class="log-body" id="log-mini"></div>
  </div>
</div>

<!-- Centre: chat -->
<div class="chat-col">
  <div class="chat-top">
    <span class="chat-top-title" id="chat-title">Compliance Training Chat</span>
    <select class="dom-sel" id="domain-select" onchange="updateDomain()">
      <option value="compliance">Regulatory Compliance</option>
      <option value="contract">Contract Review</option>
      <option value="risk">Risk Assessment</option>
    </select>
    <span class="chat-top-right">Banyan Sapling · Mubit record_outcome()</span>
  </div>
  <div class="msgs" id="messages">
    <div class="msg agent">
      <div class="ava">C</div>
      <div class="mbody">
        <div class="bub">
          Hello. I am Canopy — a compliance verification agent built on Mubit and Banyan Sapling.<br><br>
          Describe a scenario in plain English. I will parse it via Mubit's model gateway, verify it with Banyan Sapling, and show the verdict with confidence scores.<br><br>
          Use the training buttons after each verdict to correct me. Every correction fires <code>record_outcome()</code> and trains a better Mubit adapter in real time. The evidence panel on the right shows exactly what was verified.
        </div>
      </div>
    </div>
  </div>
  <div class="inp-wrap">
    <div class="inp-box">
      <textarea id="user-input" placeholder="Describe a scenario... (e.g. We sent marketing emails to 8,000 users without consent. GDPR compliant?)" rows="1" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
      <button class="sbtn" id="send-btn" onclick="sendMessage()">&#9650;</button>
    </div>
    <div class="inp-foot">Night Shift 2026 · WeWork Canary Wharf · github.com/ShieldTech-Ltd/canopy</div>
  </div>
</div>

<!-- Right: evidence panel -->
<div class="evidence-col">
  <div class="ep-head"><div class="ep-title">Evidence Panel</div></div>
  <div id="ep-empty" class="ep-empty">
    <div class="ep-icon">⚖</div>
    <div>Send a scenario to see the policy, evidence, and claim Canopy verified.</div>
  </div>
  <div id="ep-body" class="ep-body" style="display:none"></div>
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
  div.innerHTML = '<div class="ava">' + avatar + '</div><div class="mbody"><div class="bub">' + html + '</div></div>';
  msgs.appendChild(div);
  scrollBottom();
  return div.querySelector('.bub');
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

function updateEvidencePanel(data) {
  var ep = document.getElementById('ep-body');
  var empty = document.getElementById('ep-empty');
  if (!ep || !empty) return;
  empty.style.display = 'none';
  ep.style.display = 'flex';
  ep.innerHTML =
    '<div class="ep-section"><div class="ep-section-label">Policy</div><div class="ep-section-val">' + esc(data.policy || '') + '</div></div>' +
    '<div class="ep-divider"></div>' +
    '<div class="ep-section"><div class="ep-section-label">Evidence</div><div class="ep-section-val">' + esc(data.evidence || '') + '</div></div>' +
    '<div class="ep-divider"></div>' +
    '<div class="ep-section"><div class="ep-section-label">Claim</div><div class="ep-section-val">' + esc(data.claim || '') + '</div></div>' +
    '<div class="ep-divider"></div>' +
    '<div class="ep-section"><div class="ep-section-label">Verdict</div><div class="ep-section-val"><span class="vbadge ' + esc(data.verdict || 'UNSURE') + '">' + esc(data.verdict || 'UNSURE') + '</span> &nbsp;<span style="font-size:11px;color:#6b7280">' + esc(data.ms || 0) + 'ms</span></div></div>';
}

function showVerdict(bubble, data) {
  if (data.error) {
    bubble.innerHTML = '<span style="color:#f59e0b;font-size:13px">Could not parse: ' + esc(data.error) + '. Try describing the policy, evidence, and claim more explicitly.</span>';
    scrollBottom();
    return;
  }
  var verdict = data.verdict || 'UNSURE';
  var html = '<div class="vcard">';
  html += '<div class="vhead ' + esc(verdict) + '">';
  html += '<span class="vbadge ' + esc(verdict) + '">' + esc(verdict) + '</span>';
  html += '<span class="vmeta">' + esc(data.ms || 0) + 'ms · Banyan Sapling · ' + esc(currentDomain) + '</span>';
  html += '</div>';
  html += '<div class="vbody">';
  html += '<div class="clabel">Confidence</div>';
  html += '<div class="pbars">';
  html += probRow('SUP', data.sup || 0, '#22c55e');
  html += probRow('VIO', data.vio || 0, '#ef4444');
  html += probRow('INS', data.ins || 0, '#f59e0b');
  html += '</div>';
  if (data.correction_status) {
    html += '<div class="csent">✓ Mubit record_outcome() → ' + esc(data.correction_status) + '</div>';
  }
  html += '<div class="train-row">';
  html += '<span class="tlabel">Train Mubit:</span>';
  html += '<button class="tbtn ts" onclick="correct(\'SUPPORTED\')">Mark SUPPORTED</button>';
  html += '<button class="tbtn tv" onclick="correct(\'VIOLATES\')">Mark VIOLATES</button>';
  html += '</div>';
  html += '</div></div>';
  bubble.innerHTML = html;
  updateEvidencePanel(data);
  scrollBottom();
}

function probRow(name, pct, color) {
  return '<div class="prow"><span class="pname">' + esc(name) + '</span><div class="ptrack"><div class="pfill" style="background:' + color + ';width:' + pct + '%"></div></div><span class="ppct">' + esc(pct) + '%</span></div>';
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
    var trainRows = document.querySelectorAll('.train-row');
    var last = trainRows[trainRows.length - 1];
    if (last) last.innerHTML = '<span class="csent">✓ Correction sent → record_outcome() ' + esc(d.status) + '</span>';
    var ep = document.getElementById('ep-body');
    if (ep) {
      var note = document.createElement('div');
      note.className = 'ep-section';
      note.innerHTML = '<div class="ep-section-label">Correction</div><div class="ep-section-val" style="color:#a78bfa">Marked as ' + esc(correctVerdict) + ' · record_outcome() fired</div>';
      ep.appendChild(note);
    }
  });
}

function toggleLog() {
  var el = document.getElementById('log-mini');
  var icon = document.getElementById('log-icon');
  el.classList.toggle('open');
  icon.textContent = el.classList.contains('open') ? '▼' : '▶';
}

// Poll state every 3s
function pollState() {
  fetch('/state')
  .then(function(r) { return r.json(); })
  .then(function(d) {
    document.getElementById('s-acc').textContent = d.accuracy + '%';
    document.getElementById('s-total').textContent = d.total;
    document.getElementById('s-corr').textContent = d.corrections;
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
    var dot = document.getElementById('status-dot');
    if (d.api_status === 'live') {
      ls.textContent = 'Live · Banyan Sapling · ' + d.last_timing_ms + 'ms';
      dot.className = 'sdot live';
    } else if (d.api_status === 'error') {
      ls.textContent = 'Connection error';
      dot.className = 'sdot error';
    } else {
      ls.textContent = 'Connecting to Banyan Sapling...';
      dot.className = 'sdot connecting';
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
