"""Canopy: a reviewable support-policy checker routed through Mubit."""

import html
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / "sample_policy.json").read_text())
DB_PATH = Path(os.getenv("CANOPY_DB_PATH", ROOT / "canopy.sqlite3"))
HOST, PORT = "127.0.0.1", int(os.getenv("CANOPY_PORT", "8080"))
MODEL, KEY = os.getenv("MUBIT_MODEL", "gpt-4.1-mini"), os.getenv("MUBIT_API_KEY", "")
TOKEN, LOCK = secrets.token_urlsafe(32), Lock()
VERDICTS = {"SUPPORTED", "VIOLATES", "INSUFFICIENT"}
MAX_FIELD = 2000


def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, policy_version TEXT NOT NULL,
        facts TEXT NOT NULL, reply TEXT NOT NULL, prediction TEXT NOT NULL,
        request_id TEXT, latency_ms INTEGER, review_verdict TEXT, review_rule TEXT,
        rationale TEXT, reviewed_at TEXT, feedback_status TEXT NOT NULL DEFAULT 'not_submitted'
    )""")
    db.commit()
    return db


def prompt():
    rules = "\n".join(f"{r['id']}: {r['text']}" for r in POLICY["rules"])
    return (
        "Check a drafted customer support reply using ONLY the policy and customer facts. "
        "Return exactly one token: SUPPORTED, VIOLATES, or INSUFFICIENT. "
        "SUPPORTED: all factual policy claims follow from rules and known facts. "
        "VIOLATES: a claim contradicts a rule or known fact. "
        "INSUFFICIENT: a required fact is missing and neither other verdict is justified. "
        "Do not invent facts.\n"
        f"Policy version: {POLICY['version']}\n{rules}"
    )


def predict(facts, reply):
    if not KEY:
        raise RuntimeError("MUBIT_API_KEY missing")
    from openai import OpenAI
    client = OpenAI(api_key=KEY, base_url="https://api.mubit.ai/openai/v1",
                    timeout=15, max_retries=1)
    start = time.monotonic()
    raw = client.chat.completions.with_raw_response.create(
        model=MODEL, temperature=0, max_tokens=12,
        messages=[{"role": "system", "content": prompt()},
                  {"role": "user", "content": f"Customer facts: {facts}\nDraft reply: {reply}"}])
    result = (raw.parse().choices[0].message.content or "").strip().upper()
    if result not in VERDICTS:
        raise ValueError("Invalid model verdict")
    return result, raw.headers.get("x-middleware-request-id"), round((time.monotonic()-start)*1000)


def create_decision(facts, reply, prediction, request_id, latency_ms):
    with LOCK:
        with closing(database()) as db:
            row = db.execute(
                """INSERT INTO decisions(created_at,policy_version,facts,reply,prediction,request_id,latency_ms)
                   VALUES(?,?,?,?,?,?,?)""",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), POLICY["version"],
                 facts, reply, prediction, request_id, latency_ms))
            db.commit()
            return row.lastrowid


def review(decision_id, verdict, rule_id, rationale):
    if verdict not in VERDICTS or rule_id not in {r["id"] for r in POLICY["rules"]}:
        raise ValueError("Invalid verdict or policy rule")
    if not rationale.strip() or len(rationale) > MAX_FIELD:
        raise ValueError("A short rationale is required")
    with LOCK:
        with closing(database()) as db:
            row = db.execute(
                """UPDATE decisions SET review_verdict=?, review_rule=?, rationale=?,
                   reviewed_at=?, feedback_status='local_only'
                   WHERE id=? AND review_verdict IS NULL""",
                (verdict, rule_id, rationale.strip(),
                 datetime.now(timezone.utc).isoformat(timespec="seconds"), decision_id))
            db.commit()
            return row.rowcount == 1


def recent():
    with LOCK:
        with closing(database()) as db:
            return db.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT 20").fetchall()


def e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def page(message="", error=False):
    rules = "".join(f"<li><b>{e(r['id'])}</b> {e(r['text'])}</li>" for r in POLICY["rules"])
    verdicts = "".join(f"<option>{v}</option>" for v in sorted(VERDICTS))
    ids = "".join(f"<option>{e(r['id'])}</option>" for r in POLICY["rules"])
    cases = []
    for row in recent():
        if row["review_verdict"]:
            action = (f"<p class='good'>Reviewed as <b>{e(row['review_verdict'])}</b> "
                      f"under {e(row['review_rule'])}: {e(row['rationale'])}</p>")
        else:
            action = f"""<form method="post" action="/review">
                <input type="hidden" name="csrf" value="{TOKEN}">
                <input type="hidden" name="id" value="{row['id']}">
                <label>Correct verdict<select name="verdict">{verdicts}</select></label>
                <label>Policy rule<select name="rule">{ids}</select></label>
                <label>Reason<input name="reason" maxlength="2000" required></label>
                <button>Save reviewer correction</button></form>"""
        cases.append(f"""<article><h3>Case #{row['id']}</h3>
            <p><b>Facts:</b> {e(row['facts'])}</p><p><b>Draft:</b> {e(row['reply'])}</p>
            <p><b>Mubit verdict:</b> {e(row['prediction'])} · {e(row['latency_ms'])} ms</p>
            <p class="muted">Request {e(row['request_id'] or 'not returned')} · {e(row['policy_version'])}</p>
            {action}<p class="warning">Feedback: {e(row['feedback_status'])}.
            A local correction is not a Mubit model update.</p></article>""")
    banner = f"<p class='banner'>{e(message)}</p>" if message else ""
    status = f"LIVE via Mubit · {e(MODEL)}" if KEY else "MUBIT KEY MISSING · live calls unavailable"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Canopy · Support policy review</title><style>
    :root{{font:16px/1.5 system-ui;color:#e7f5e9;background:#0c1915}}
    body{{max-width:960px;margin:auto;padding:24px}}h1{{font-size:2.6rem;margin:0}}
    section,article{{background:#142820;border:1px solid #3b644c;border-radius:12px;padding:20px;margin:20px 0}}
    .muted{{color:#acc4b2}}.warning{{color:#ffd084}}.good{{color:#9bf0b3}}
    .banner{{padding:12px;background:{'#58332d' if error else '#285439'};border-radius:8px}}
    label{{display:block;margin:12px 0}}textarea,input,select{{box-sizing:border-box;width:100%;padding:10px;
    background:#0c1915;color:white;border:1px solid #779581;border-radius:6px}}
    textarea{{min-height:90px}}button{{background:#8cf1ad;border:0;border-radius:6px;padding:12px 16px;
    color:#092015;font-weight:700;cursor:pointer}}
    </style></head><body><header><h1>Canopy</h1><p class="muted">{status}</p></header>{banner}
    <section><h2>Sample refund policy · {e(POLICY['version'])}</h2>
    <p>This is a fictional demo policy. No customer account is connected.</p><ol>{rules}</ol></section>
    <section><h2>Check a drafted reply</h2><form method="post" action="/check">
    <input type="hidden" name="csrf" value="{TOKEN}">
    <label>Customer facts<textarea name="facts" maxlength="2000" required
      placeholder="Purchase: 5 days ago. Paid feature usage: none."></textarea></label>
    <label>Draft support reply<textarea name="reply" maxlength="2000" required
      placeholder="You qualify for a refund."></textarea></label>
    <button>Check through Mubit</button></form></section>
    <section><h2>Decision and correction trail</h2><p class="muted">Reviews are stored locally.
    Mubit feedback submission awaits a confirmed event API contract.</p>
    {''.join(cases) or '<p>No live decisions yet.</p>'}</section></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, body):
        data = body.encode()
        self.send_response(code)
        for name, value in {
            "Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(data)),
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'",
        }.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.respond(200 if self.path == "/" else 404,
                     page() if self.path == "/" else page("Not found", True))

    def do_POST(self):
        if self.path not in {"/check", "/review"}:
            return self.respond(404, page("Not found", True))
        if self.headers.get("Origin") not in {None, f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}:
            return self.respond(403, page("Origin rejected", True))
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError("Invalid request size")
            form = parse_qs(self.rfile.read(size).decode(), strict_parsing=True)
            if not secrets.compare_digest(form.get("csrf", [""])[0], TOKEN):
                return self.respond(403, page("Review token rejected", True))
            field = lambda name: form.get(name, [""])[0].strip()
            if self.path == "/check":
                facts, reply = field("facts"), field("reply")
                if not facts or not reply or len(facts) > MAX_FIELD or len(reply) > MAX_FIELD:
                    raise ValueError("Facts and reply must each be 1–2000 characters")
                verdict, req_id, latency = predict(facts, reply)
                number = create_decision(facts, reply, verdict, req_id, latency)
                message = f"Saved live Mubit case #{number}: {verdict}"
            else:
                number = int(field("id"))
                if not review(number, field("verdict"), field("rule"), field("reason")):
                    raise ValueError("Case missing or already reviewed")
                message = f"Saved local reviewer correction for case #{number}"
            self.respond(200, page(message))
        except (ValueError, UnicodeError) as exc:
            self.respond(400, page(str(exc), True))
        except Exception as exc:
            # Provider errors can contain request content or URLs; do not display them.
            print(f"Request failed: {type(exc).__name__}")
            self.respond(502, page("Live Mubit call failed. No decision saved.", True))

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    database().close()
    print(f"Canopy: http://{HOST}:{PORT} · {'Mubit key set' if KEY else 'Mubit key missing'}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
