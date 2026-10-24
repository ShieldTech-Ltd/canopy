"""Authenticated, organisation-scoped API for the hosted Canopy service.

The legacy single-operator page remains available only through the separate
local entry point. Hosted mode fails closed unless identity and Postgres are
configured. No Mubit feedback endpoint is guessed here.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from urllib.parse import parse_qs, urlparse

from flask import Flask, Response, g, jsonify, make_response, redirect, request

from canopy_app import canopy

LOG = logging.getLogger("canopy.production")
ROLES = {"admin", "operator", "reviewer"}
REVIEW_ROLES = {"admin", "reviewer"}
MAX_JSON_BYTES = 8192
DAILY_USER_LIMIT = 40
DAILY_ORG_LIMIT = 120


def _config():
    origin = os.environ.get("CANOPY_PUBLIC_ORIGIN", "").rstrip("/")
    parsed = urlparse(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.path or
            parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("Hosted mode requires a bare HTTPS CANOPY_PUBLIC_ORIGIN")
    required = (
        "DATABASE_URL", "WORKOS_API_KEY", "WORKOS_CLIENT_ID",
        "WORKOS_COOKIE_PASSWORD", "CANOPY_WORKOS_ORG_ID", "CANOPY_CSRF_SECRET",
        "CANOPY_ADMIN_USER_ID",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError("Hosted configuration incomplete: " + ", ".join(missing))
    from cryptography.fernet import Fernet
    try:
        Fernet(os.environ["WORKOS_COOKIE_PASSWORD"].encode())
    except (ValueError, TypeError) as exc:
        raise ValueError("WORKOS_COOKIE_PASSWORD must be a Fernet key") from exc
    if len(os.environ["CANOPY_CSRF_SECRET"]) < 32:
        raise ValueError("CANOPY_CSRF_SECRET must be at least 32 characters")
    database_url = urlparse(os.environ["DATABASE_URL"])
    if database_url.scheme not in {"postgres", "postgresql"}:
        raise ValueError("Hosted mode requires PostgreSQL")
    if database_url.hostname not in {None, "localhost", "127.0.0.1"}:
        sslmode = parse_qs(database_url.query).get("sslmode", [""])[0]
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Remote PostgreSQL requires TLS")
    if not canopy.KEY:
        raise ValueError("Hosted mode requires MUBIT_API_KEY")
    return origin


def _db():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row,
                           connect_timeout=5, autocommit=False)


def migrate():
    """Install and validate schema v1 before serving traffic."""
    with _db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS canopy_schema_meta (
            singleton BOOLEAN PRIMARY KEY DEFAULT true CHECK (singleton),
            version INTEGER NOT NULL
        )""")
        existing = db.execute("SELECT version FROM canopy_schema_meta WHERE singleton=true").fetchone()
        if existing is not None and existing["version"] != 1:
            raise RuntimeError("Unsupported hosted database schema version")
        db.execute("""CREATE TABLE IF NOT EXISTS canopy_users (
            organization_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin','operator','reviewer')),
            active BOOLEAN NOT NULL DEFAULT true,
            added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,user_id)
        )""")
        db.execute("""INSERT INTO canopy_users (organization_id,user_id,role)
            VALUES (%s,%s,'admin') ON CONFLICT (organization_id,user_id) DO NOTHING""",
            (os.environ["CANOPY_WORKOS_ORG_ID"], os.environ["CANOPY_ADMIN_USER_ID"]))
        db.execute("""CREATE TABLE IF NOT EXISTS canopy_policies (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            organization_id TEXT NOT NULL,
            version TEXT NOT NULL,
            policy_hash TEXT NOT NULL,
            policy_json JSONB NOT NULL,
            active BOOLEAN NOT NULL DEFAULT false,
            published_by TEXT NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (organization_id,version)
        )""")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS canopy_one_active_policy
            ON canopy_policies (organization_id) WHERE active=true""")
        db.execute("""INSERT INTO canopy_policies
            (organization_id,version,policy_hash,policy_json,active,published_by)
            SELECT %s,%s,%s,%s::jsonb,true,%s WHERE NOT EXISTS
            (SELECT 1 FROM canopy_policies WHERE organization_id=%s)""",
            (os.environ["CANOPY_WORKOS_ORG_ID"], canopy.POLICY["version"],
             canopy.POLICY_HASH, json.dumps(canopy.POLICY, sort_keys=True),
             os.environ["CANOPY_ADMIN_USER_ID"], os.environ["CANOPY_WORKOS_ORG_ID"]))
        db.execute("""CREATE TABLE IF NOT EXISTS canopy_cases (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            organization_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            policy_version TEXT NOT NULL,
            policy_hash TEXT NOT NULL,
            policy_json JSONB NOT NULL,
            recording_requested BOOLEAN NOT NULL,
            facts TEXT NOT NULL,
            reply TEXT NOT NULL,
            prediction TEXT NOT NULL,
            mubit_request_id TEXT NOT NULL,
            latency_ms INTEGER NOT NULL,
            review_verdict TEXT,
            review_rule TEXT,
            review_reason TEXT,
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            feedback_status TEXT NOT NULL DEFAULT 'not_submitted',
            feedback_id TEXT,
            feedback_attempted_at TIMESTAMPTZ,
            feedback_error_code TEXT,
            CONSTRAINT canopy_verdict CHECK (prediction IN ('SUPPORTED','VIOLATES','INSUFFICIENT')),
            CONSTRAINT canopy_review_verdict CHECK (review_verdict IS NULL OR
                review_verdict IN ('SUPPORTED','VIOLATES','INSUFFICIENT')),
            CONSTRAINT canopy_feedback_status CHECK (feedback_status IN
                ('not_submitted','local_only','pending','accepted','rejected','retryable')),
            CONSTRAINT canopy_recorded_request CHECK (mubit_request_id LIKE 'mreq_%')
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS canopy_cases_org_created
            ON canopy_cases (organization_id, created_at DESC)""")
        db.execute("""CREATE TABLE IF NOT EXISTS canopy_audit (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            organization_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            case_id BIGINT,
            action TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            details JSONB NOT NULL DEFAULT '{}'::jsonb
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS canopy_audit_org_time
            ON canopy_audit (organization_id, occurred_at DESC)""")
        db.execute("""CREATE TABLE IF NOT EXISTS canopy_daily_usage (
            organization_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            day DATE NOT NULL,
            used INTEGER NOT NULL CHECK (used >= 0),
            PRIMARY KEY (organization_id,actor_id,day)
        )""")
        db.execute("""INSERT INTO canopy_schema_meta (singleton,version) VALUES (true,1)
            ON CONFLICT (singleton) DO NOTHING""")


def _workos():
    from workos import WorkOSClient
    return WorkOSClient(api_key=os.environ["WORKOS_API_KEY"],
                        client_id=os.environ["WORKOS_CLIENT_ID"])


def _identity():
    sealed = request.cookies.get("canopy_session")
    if not sealed:
        return None
    try:
        session = _workos().user_management.load_sealed_session(
            session_data=sealed,
            cookie_password=os.environ["WORKOS_COOKIE_PASSWORD"])
        result = session.authenticate()
        if not result.authenticated:
            result = session.refresh()
            if result.authenticated:
                g.refreshed_session = result.sealed_session
        if not result.authenticated or not result.user:
            return None
        org = getattr(result, "organization_id", None)
        if org != os.environ["CANOPY_WORKOS_ORG_ID"]:
            return None
        if getattr(result, "impersonator", None):
            return None
        user_id = result.user.get("id")
        if not user_id:
            return None
        with _db() as db:
            member = db.execute("""SELECT role FROM canopy_users WHERE organization_id=%s
                AND user_id=%s AND active=true""", (org, user_id)).fetchone()
        if member is None:
            return None
        return {"user_id": user_id, "organization_id": org,
                "role": member["role"],
                "session_id": result.session_id}
    except Exception:
        LOG.warning("session_validation_failed", exc_info=False)
        return None


def _csrf_token(session_id):
    return hmac.new(os.environ["CANOPY_CSRF_SECRET"].encode(),
                    session_id.encode(), hashlib.sha256).hexdigest()


def _json_fields(*names):
    if request.mimetype != "application/json" or not request.content_length or request.content_length > MAX_JSON_BYTES:
        raise ValueError("Expected bounded JSON body")
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != set(names):
        raise ValueError("Invalid request fields")
    return data


def _text(value, label, maximum=canopy.MAX_FIELD):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"Invalid {label}")
    return value.strip()


def _audit(db, action, case_id=None, details=None):
    db.execute("""INSERT INTO canopy_audit
        (organization_id,actor_id,case_id,action,details) VALUES (%s,%s,%s,%s,%s::jsonb)""",
        (g.identity["organization_id"], g.identity["user_id"], case_id,
         action, json.dumps(details or {})))


def _reserve_model_call():
    """Reserve a bounded call before contacting the billable provider."""
    with _db() as db:
        for actor, limit in (("*", DAILY_ORG_LIMIT),
                             (g.identity["user_id"], DAILY_USER_LIMIT)):
            row = db.execute("""INSERT INTO canopy_daily_usage
                (organization_id,actor_id,day,used) VALUES (%s,%s,CURRENT_DATE,1)
                ON CONFLICT (organization_id,actor_id,day)
                DO UPDATE SET used=canopy_daily_usage.used+1
                WHERE canopy_daily_usage.used < %s RETURNING used""",
                (g.identity["organization_id"], actor, limit)).fetchone()
            if row is None:
                db.rollback()
                return False
        _audit(db, "model_call_reserved")
    return True


def _case_public(row):
    keys = ("id", "created_at", "created_by", "policy_version", "policy_hash",
            "recording_requested", "facts", "reply", "prediction", "mubit_request_id",
            "latency_ms", "review_verdict", "review_rule", "review_reason", "reviewed_by",
            "reviewed_at", "feedback_status", "feedback_id", "feedback_attempted_at",
            "feedback_error_code")
    return {key: row[key] for key in keys}


def create_app():
    origin = _config()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_JSON_BYTES

    @app.before_request
    def protect():
        if request.path == "/livez":
            return None
        if request.host != urlparse(origin).netloc:
            return jsonify(error="invalid_host"), 400
        if request.path in {"/login", "/callback"}:
            return None
        g.identity = _identity()
        if g.identity is None:
            return jsonify(error="unauthenticated"), 401
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("Origin") != origin:
                return jsonify(error="invalid_origin"), 403
            supplied = request.headers.get("X-CSRF-Token", "")
            expected = _csrf_token(g.identity["session_id"])
            if not secrets.compare_digest(supplied, expected):
                return jsonify(error="invalid_csrf"), 403

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if getattr(g, "refreshed_session", None):
            response.set_cookie("canopy_session", g.refreshed_session, secure=True,
                                httponly=True, samesite="Lax", max_age=604800)
        return response

    @app.get("/livez")
    def live():
        return Response("live", mimetype="text/plain")

    @app.get("/readyz")
    def ready():
        try:
            with _db() as db:
                db.execute("SELECT 1")
            return Response("ready", mimetype="text/plain")
        except Exception:
            return Response("unavailable", status=503, mimetype="text/plain")

    @app.get("/login")
    def login():
        state = secrets.token_urlsafe(32)
        url = _workos().user_management.get_authorization_url(
            provider="authkit", redirect_uri=origin + "/callback", state=state,
            organization_id=os.environ["CANOPY_WORKOS_ORG_ID"])
        response = make_response(redirect(url))
        response.set_cookie("canopy_oauth_state", state, secure=True, httponly=True,
                            samesite="Lax", max_age=600)
        return response

    @app.get("/callback")
    def callback():
        state = request.cookies.get("canopy_oauth_state", "")
        code = request.args.get("code", "")
        if not state or not code or not secrets.compare_digest(state, request.args.get("state", "")):
            return jsonify(error="invalid_callback"), 400
        try:
            result = _workos().user_management.authenticate_with_code(code=code)
        except Exception:
            LOG.warning("auth_callback_failed", exc_info=False)
            return jsonify(error="authentication_failed"), 401
        if result.organization_id != os.environ["CANOPY_WORKOS_ORG_ID"]:
            return jsonify(error="organization_forbidden"), 403
        user_id = result.user.id
        with _db() as db:
            member = db.execute("""SELECT 1 FROM canopy_users WHERE organization_id=%s
                AND user_id=%s AND active=true""",
                (result.organization_id, user_id)).fetchone()
        if member is None:
            return jsonify(error="membership_forbidden"), 403
        from workos.session import seal_session_from_auth_response
        sealed = seal_session_from_auth_response(
            access_token=result.access_token, refresh_token=result.refresh_token,
            user=result.user.to_dict(), cookie_password=os.environ["WORKOS_COOKIE_PASSWORD"])
        response = make_response(redirect(origin + "/api/v1/session"))
        response.set_cookie("canopy_session", sealed, secure=True,
                            httponly=True, samesite="Lax", max_age=604800)
        response.delete_cookie("canopy_oauth_state")
        return response

    @app.get("/api/v1/session")
    def session_info():
        return jsonify(user_id=g.identity["user_id"], role=g.identity["role"],
                       csrf_token=_csrf_token(g.identity["session_id"]))

    @app.post("/logout")
    def logout():
        try:
            _workos().user_management.revoke_session(session_id=g.identity["session_id"])
        except Exception:
            LOG.warning("session_revoke_failed", exc_info=False)
            return jsonify(error="logout_unavailable"), 503
        response = jsonify(signed_out=True)
        response.delete_cookie("canopy_session")
        return response

    @app.get("/api/v1/cases")
    def list_cases():
        with _db() as db:
            if g.identity["role"] == "operator":
                rows = db.execute("""SELECT * FROM canopy_cases WHERE organization_id=%s
                    AND created_by=%s ORDER BY id DESC LIMIT 100""",
                    (g.identity["organization_id"], g.identity["user_id"])).fetchall()
            else:
                rows = db.execute("""SELECT * FROM canopy_cases WHERE organization_id=%s
                    ORDER BY id DESC LIMIT 100""",
                    (g.identity["organization_id"],)).fetchall()
        return jsonify(cases=[_case_public(row) for row in rows])

    @app.get("/api/v1/cases/<int:case_id>")
    def get_case(case_id):
        with _db() as db:
            row = db.execute("""SELECT * FROM canopy_cases WHERE id=%s
                AND organization_id=%s""", (case_id, g.identity["organization_id"])).fetchone()
        if row is None or (g.identity["role"] == "operator" and
                           row["created_by"] != g.identity["user_id"]):
            return jsonify(error="not_found"), 404
        return jsonify(case=_case_public(row))

    @app.get("/api/v1/users")
    def list_users():
        if g.identity["role"] != "admin":
            return jsonify(error="forbidden"), 403
        with _db() as db:
            rows = db.execute("""SELECT user_id,role,active,added_at FROM canopy_users
                WHERE organization_id=%s ORDER BY added_at""",
                (g.identity["organization_id"],)).fetchall()
        return jsonify(users=rows)

    @app.get("/api/v1/policy")
    def active_policy():
        with _db() as db:
            row = db.execute("""SELECT version,policy_hash,policy_json FROM canopy_policies
                WHERE organization_id=%s AND active=true""",
                (g.identity["organization_id"],)).fetchone()
        if row is None:
            return jsonify(error="policy_unavailable"), 503
        return jsonify(version=row["version"], policy_hash=row["policy_hash"],
                       rules=row["policy_json"]["rules"])

    @app.get("/api/v1/policies")
    def policy_history():
        if g.identity["role"] != "admin":
            return jsonify(error="forbidden"), 403
        with _db() as db:
            rows = db.execute("""SELECT version,policy_hash,active,published_by,published_at
                FROM canopy_policies WHERE organization_id=%s ORDER BY id DESC""",
                (g.identity["organization_id"],)).fetchall()
        return jsonify(policies=rows)

    @app.post("/api/v1/policies")
    def publish_policy():
        if g.identity["role"] != "admin":
            return jsonify(error="forbidden"), 403
        try:
            policy = canopy.validate_policy(_json_fields("version", "rules"))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        fingerprint = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()
        with _db() as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                       (g.identity["organization_id"],))
            current = db.execute("""SELECT role,active FROM canopy_users
                WHERE organization_id=%s AND user_id=%s""",
                (g.identity["organization_id"], g.identity["user_id"])).fetchone()
            if current is None or current["role"] != "admin" or not current["active"]:
                return jsonify(error="forbidden"), 403
            if db.execute("""SELECT 1 FROM canopy_policies WHERE organization_id=%s
                AND version=%s""", (g.identity["organization_id"],
                                     policy["version"])).fetchone():
                return jsonify(error="policy_version_exists"), 409
            db.execute("""UPDATE canopy_policies SET active=false
                WHERE organization_id=%s AND active=true""",
                (g.identity["organization_id"],))
            db.execute("""INSERT INTO canopy_policies
                (organization_id,version,policy_hash,policy_json,active,published_by)
                VALUES (%s,%s,%s,%s::jsonb,true,%s)""",
                (g.identity["organization_id"], policy["version"], fingerprint,
                 json.dumps(policy, sort_keys=True), g.identity["user_id"]))
            _audit(db, "policy_published", details={"version": policy["version"],
                                                    "policy_hash": fingerprint})
        return jsonify(version=policy["version"], policy_hash=fingerprint), 201

    @app.put("/api/v1/users/<user_id>")
    def set_user(user_id):
        if g.identity["role"] != "admin":
            return jsonify(error="forbidden"), 403
        try:
            data = _json_fields("role", "active")
            role = _text(data["role"], "role", 32)
            if role not in ROLES or type(data["active"]) is not bool:
                raise ValueError("Invalid user role or state")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if not user_id.startswith("user_") or len(user_id) > 128:
            return jsonify(error="invalid_user_id"), 400
        if user_id == g.identity["user_id"] and (role != "admin" or not data["active"]):
            return jsonify(error="cannot_demote_self"), 409
        with _db() as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                       (g.identity["organization_id"],))
            current = db.execute("""SELECT role,active FROM canopy_users
                WHERE organization_id=%s AND user_id=%s""",
                (g.identity["organization_id"], g.identity["user_id"])).fetchone()
            if current is None or current["role"] != "admin" or not current["active"]:
                return jsonify(error="forbidden"), 403
            db.execute("""INSERT INTO canopy_users (organization_id,user_id,role,active)
                VALUES (%s,%s,%s,%s) ON CONFLICT (organization_id,user_id)
                DO UPDATE SET role=EXCLUDED.role,active=EXCLUDED.active""",
                (g.identity["organization_id"], user_id, role, data["active"]))
            _audit(db, "user_access_changed", details={"target_user_id": user_id,
                                                        "role": role, "active": data["active"]})
        return jsonify(user_id=user_id, role=role, active=data["active"])

    @app.post("/api/v1/cases")
    def check():
        if g.identity["role"] not in {"admin", "operator"}:
            return jsonify(error="forbidden"), 403
        try:
            data = _json_fields("facts", "reply", "record")
            facts = _text(data["facts"], "facts")
            reply = _text(data["reply"], "reply")
            if type(data["record"]) is not bool:
                raise ValueError("Invalid recording choice")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        with _db() as db:
            active = db.execute("""SELECT version,policy_hash,policy_json
                FROM canopy_policies WHERE organization_id=%s AND active=true""",
                (g.identity["organization_id"],)).fetchone()
        if active is None:
            return jsonify(error="policy_unavailable"), 503
        if not canopy.PREDICT_LIMIT.acquire(blocking=False):
            return jsonify(error="busy"), 429
        try:
            if not _reserve_model_call():
                return jsonify(error="daily_call_limit"), 429
            verdict, request_id, latency = canopy.predict(
                facts, reply, record=data["record"], policy=active["policy_json"])
        except Exception as exc:
            LOG.warning("mubit_check_failed type=%s", type(exc).__name__)
            return jsonify(error="mubit_unavailable"), 502
        finally:
            canopy.PREDICT_LIMIT.release()
        try:
            with _db() as db:
                row = db.execute("""INSERT INTO canopy_cases
                    (organization_id,created_by,policy_version,policy_hash,policy_json,
                     recording_requested,facts,reply,prediction,mubit_request_id,latency_ms)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (g.identity["organization_id"], g.identity["user_id"],
                     active["version"], active["policy_hash"],
                     json.dumps(active["policy_json"], sort_keys=True),
                     data["record"], facts, reply,
                     verdict, request_id, latency)).fetchone()
                _audit(db, "case_created", row["id"], {"recording_requested": data["record"]})
        except Exception as exc:
            LOG.error("decision_store_failed type=%s request_id=%s", type(exc).__name__,
                      request_id)
            return jsonify(error="decision_store_unavailable", mubit_request_id=request_id), 503
        return jsonify(case=_case_public(row)), 201

    @app.post("/api/v1/cases/<int:case_id>/review")
    def review(case_id):
        if g.identity["role"] not in REVIEW_ROLES:
            return jsonify(error="forbidden"), 403
        try:
            data = _json_fields("verdict", "rule", "reason")
            verdict = _text(data["verdict"], "verdict", 32)
            rule = _text(data["rule"], "rule", 32)
            reason = _text(data["reason"], "reason")
            if verdict not in canopy.VERDICTS:
                raise ValueError("Invalid verdict")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        with _db() as db:
            row = db.execute("""SELECT * FROM canopy_cases WHERE id=%s AND organization_id=%s
                FOR UPDATE""", (case_id, g.identity["organization_id"])).fetchone()
            if row is None:
                return jsonify(error="not_found"), 404
            if row["review_verdict"] is not None:
                return jsonify(error="already_reviewed"), 409
            if rule not in {item["id"] for item in row["policy_json"]["rules"]}:
                return jsonify(error="invalid_rule"), 400
            updated = db.execute("""UPDATE canopy_cases SET review_verdict=%s,
                review_rule=%s,review_reason=%s,reviewed_by=%s,reviewed_at=now(),
                feedback_status='local_only' WHERE id=%s RETURNING *""",
                (verdict, rule, reason, g.identity["user_id"], case_id)).fetchone()
            _audit(db, "case_reviewed", case_id, {"review_verdict": verdict,
                                                   "review_rule": rule})
        return jsonify(case=_case_public(updated))

    @app.post("/api/v1/cases/<int:case_id>/feedback")
    def feedback(case_id):
        if g.identity["role"] not in REVIEW_ROLES:
            return jsonify(error="forbidden"), 403
        with _db() as db:
            row = db.execute("""SELECT recording_requested,review_verdict,feedback_status
                FROM canopy_cases WHERE id=%s AND organization_id=%s""",
                (case_id, g.identity["organization_id"])).fetchone()
        if row is None:
            return jsonify(error="not_found"), 404
        if not row["recording_requested"] or row["review_verdict"] is None:
            return jsonify(error="not_eligible"), 409
        if row["feedback_status"] == "accepted":
            return jsonify(error="already_accepted"), 409
        # Do not convert a local review into a false submission claim.
        return jsonify(error="mubit_feedback_contract_unconfirmed",
                       feedback_status=row["feedback_status"]), 503

    return app


def main():
    _config()
    migrate()
    host = canopy.HOST
    port = canopy.PORT
    os.execvp("gunicorn", ["gunicorn", "--bind", f"{host}:{port}",
                          "--workers", "2", "--threads", "4", "--timeout", "45",
                          "canopy_app.production:create_app()"])
