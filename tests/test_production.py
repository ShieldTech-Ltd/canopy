"""Postgres-backed HTTP tests. Set CANOPY_TEST_DATABASE_URL to run them."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from unittest.mock import patch

from canopy_app import canopy, manage_production, production


@unittest.skipUnless(os.getenv("CANOPY_TEST_DATABASE_URL"), "Postgres test URL unavailable")
class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cryptography.fernet import Fernet
        cls.config = patch.dict(os.environ, {
            "DATABASE_URL": os.environ["CANOPY_TEST_DATABASE_URL"],
            "CANOPY_PUBLIC_ORIGIN": "https://canopy.example.test",
            "WORKOS_API_KEY": "sk_test_placeholder",
            "WORKOS_CLIENT_ID": "client_test_placeholder",
            "WORKOS_COOKIE_PASSWORD": Fernet.generate_key().decode(),
            "CANOPY_WORKOS_ORG_ID": "org_test",
            "CANOPY_ADMIN_USER_ID": "user_admin",
            "CANOPY_CSRF_SECRET": "c" * 40,
        })
        cls.config.start()
        cls.key = patch.object(canopy, "KEY", "synthetic-test-key")
        cls.key.start()
        production.migrate()
        cls.app = production.create_app()

    @classmethod
    def tearDownClass(cls):
        cls.key.stop()
        cls.config.stop()

    def setUp(self):
        with production._db() as db:
            db.execute("TRUNCATE canopy_cases, canopy_audit, canopy_daily_usage RESTART IDENTITY")
            db.execute("DELETE FROM canopy_policies WHERE organization_id='org_test'")
            db.execute("DELETE FROM canopy_users WHERE user_id <> 'user_admin'")
            db.execute("""INSERT INTO canopy_users (organization_id,user_id,role) VALUES
                ('org_test','user_operator_a','operator'),
                ('org_test','user_operator_b','operator'),
                ('org_test','user_reviewer','reviewer')""")
        production.migrate()
        self.actor = {"user_id": "user_operator_a", "organization_id": "org_test",
                      "role": "operator", "session_id": "session_test"}
        self.identity = patch.object(production, "_identity", side_effect=lambda: self.actor)
        self.identity.start()
        self.client = self.app.test_client()
        self.headers = {"Host": "canopy.example.test", "Origin": "https://canopy.example.test",
                        "X-CSRF-Token": production._csrf_token("session_test")}

    def tearDown(self):
        if not getattr(self, "identity_stopped", False):
            self.identity.stop()

    def create_case(self, record=True):
        with patch.object(canopy, "predict", return_value=("SUPPORTED", "mreq_test", 12)) as predict:
            result = self.client.post("/api/v1/cases", json={
                "facts": "Purchased 5 days ago. No paid features used.",
                "reply": "You qualify for a refund.", "record": record,
            }, headers=self.headers)
        self.assertEqual(result.status_code, 201, result.json)
        predict.assert_called_once()
        return result.json["case"]["id"]

    def test_check_review_and_feedback_stays_local_without_contract(self):
        case_id = self.create_case()
        self.assertEqual(self.client.get(f"/api/v1/cases/{case_id}",
                                         headers=self.headers).status_code, 200)
        self.actor = {**self.actor, "user_id": "user_reviewer", "role": "reviewer"}
        result = self.client.post(f"/api/v1/cases/{case_id}/review", json={
            "verdict": "VIOLATES", "rule": "R2", "reason": "Feature used."
        }, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json["case"]["feedback_status"], "local_only")
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/review", json={
            "verdict": "SUPPORTED", "rule": "R1", "reason": "Retry"
        }, headers=self.headers).status_code, 409)
        feedback = self.client.post(f"/api/v1/cases/{case_id}/feedback", headers=self.headers)
        self.assertEqual(feedback.status_code, 503)
        self.assertEqual(feedback.json["feedback_status"], "local_only")
        with production._db() as db:
            self.assertEqual(db.execute("SELECT count(*) AS n FROM canopy_audit").fetchone()["n"], 3)

    def test_cross_user_access_and_roles(self):
        case_id = self.create_case()
        self.actor = {**self.actor, "user_id": "user_operator_b"}
        self.assertEqual(self.client.get("/api/v1/cases", headers=self.headers).json["cases"], [])
        self.assertEqual(self.client.get(f"/api/v1/cases/{case_id}",
                                         headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/review", json={
            "verdict": "SUPPORTED", "rule": "R1", "reason": "Valid"
        }, headers=self.headers).status_code, 403)
        self.actor = {**self.actor, "user_id": "user_reviewer", "role": "reviewer"}
        self.assertEqual(len(self.client.get("/api/v1/cases", headers=self.headers).json["cases"]), 1)
        with patch.object(canopy, "predict") as predict:
            self.assertEqual(self.client.post("/api/v1/cases", json={
                "facts": "A", "reply": "B", "record": False
            }, headers=self.headers).status_code, 403)
            predict.assert_not_called()

    def test_csrf_origin_host_and_admin_access(self):
        self.assertEqual(self.client.post("/api/v1/cases", json={}, headers={
            "Host": "canopy.example.test", "Origin": "https://canopy.example.test"
        }).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/cases", json={}, headers={
            **self.headers, "Origin": "https://other.example.test"
        }).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/session", headers={
            **self.headers, "Host": "other.example.test"
        }).status_code, 400)
        self.assertEqual(self.client.get("/api/v1/users", headers=self.headers).status_code, 403)
        self.actor = {**self.actor, "user_id": "user_admin", "role": "admin"}
        result = self.client.put("/api/v1/users/user_new", json={
            "role": "reviewer", "active": True
        }, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(self.client.put("/api/v1/users/user_admin", json={
            "role": "operator", "active": True
        }, headers=self.headers).status_code, 409)
        self.assertEqual(len(self.client.get("/api/v1/users", headers=self.headers).json["users"]), 5)

    def test_recording_and_input_validation(self):
        case_id = self.create_case(record=False)
        self.actor = {**self.actor, "user_id": "user_reviewer", "role": "reviewer"}
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/review", json={
            "verdict": "VIOLATES", "rule": "R2", "reason": "Correct"
        }, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/feedback",
                                          headers=self.headers).status_code, 409)
        self.actor = {**self.actor, "user_id": "user_operator_a", "role": "operator"}
        with patch.object(canopy, "predict") as predict:
            result = self.client.post("/api/v1/cases", json={
                "facts": "A", "reply": "B", "record": "yes"
            }, headers=self.headers)
            self.assertEqual(result.status_code, 400)
            predict.assert_not_called()

    def test_hosted_config_and_legacy_public_mode_fail_closed(self):
        for bad_origin in ("https://canopy.example.test/#fragment",
                           "https://staff@canopy.example.test"):
            with self.subTest(origin=bad_origin), patch.dict(
                    os.environ, {"CANOPY_PUBLIC_ORIGIN": bad_origin}):
                with self.assertRaisesRegex(ValueError, "bare HTTPS"):
                    production._config()
        with patch.dict(os.environ, {"DATABASE_URL":
                                  "postgresql://user:password@db.example.test/canopy"}):
            with self.assertRaisesRegex(ValueError, "requires TLS"):
                production._config()
        env = os.environ.copy()
        env.pop("CANOPY_LEGACY_PILOT", None)
        env["CANOPY_PUBLIC_ORIGIN"] = "https://canopy.example.test"
        env["CANOPY_RUNTIME"] = "legacy"
        result = subprocess.run([sys.executable, "-c", "import canopy"],
                                cwd=canopy.PROJECT_ROOT, env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CANOPY_LEGACY_PILOT=1", result.stderr)

    def test_schema_version_mismatch_stops_startup(self):
        with production._db() as db:
            db.execute("UPDATE canopy_schema_meta SET version=2 WHERE singleton=true")
        try:
            with self.assertRaisesRegex(RuntimeError, "Unsupported hosted database schema"):
                production.migrate()
        finally:
            with production._db() as db:
                db.execute("UPDATE canopy_schema_meta SET version=1 WHERE singleton=true")

    def test_daily_budget_blocks_second_provider_call(self):
        with patch.object(production, "DAILY_USER_LIMIT", 1), patch.object(
            canopy, "predict", return_value=("SUPPORTED", "mreq_test", 10)
        ) as predict:
            body = {"facts": "Synthetic", "reply": "Eligible", "record": False}
            first = self.client.post("/api/v1/cases", json=body, headers=self.headers)
            second = self.client.post("/api/v1/cases", json=body, headers=self.headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)
        predict.assert_called_once()

    def test_admin_publishes_versioned_policy_used_by_next_check(self):
        self.actor = {**self.actor, "user_id": "user_admin", "role": "admin"}
        policy = {"version": "v2", "rules": [{"id": "NEW", "text": "Refund only within 7 days."}]}
        published = self.client.post("/api/v1/policies", json=policy, headers=self.headers)
        self.assertEqual(published.status_code, 201, published.json)
        self.assertEqual(self.client.post("/api/v1/policies", json=policy,
                                          headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get("/api/v1/policy", headers=self.headers).json["version"], "v2")
        self.actor = {**self.actor, "user_id": "user_operator_a", "role": "operator"}
        with patch.object(canopy, "predict", return_value=("VIOLATES", "mreq_v2", 10)) as predict:
            checked = self.client.post("/api/v1/cases", json={
                "facts": "Purchased 10 days ago.", "reply": "You qualify.", "record": True
            }, headers=self.headers)
        self.assertEqual(checked.status_code, 201, checked.json)
        case_id = checked.json["case"]["id"]
        self.assertEqual(predict.call_args.kwargs["policy"], policy)
        case = self.client.get(f"/api/v1/cases/{case_id}", headers=self.headers).json["case"]
        self.assertEqual(case["policy_version"], "v2")
        self.actor = {**self.actor, "user_id": "user_reviewer", "role": "reviewer"}
        self.assertEqual(self.client.post(f"/api/v1/cases/{case_id}/review", json={
            "verdict": "SUPPORTED", "rule": "NEW", "reason": "Under this policy"
        }, headers=self.headers).status_code, 200)

    def test_logout_revokes_session_and_clears_cookie(self):
        self.actor = {**self.actor, "user_id": "user_admin", "role": "admin"}
        with patch.object(production, "_workos") as workos:
            result = self.client.post("/logout", headers=self.headers)
        self.assertEqual(result.status_code, 200)
        workos.return_value.user_management.revoke_session.assert_called_once_with(
            session_id="session_test")
        self.assertIn("canopy_session=;", result.headers["Set-Cookie"])

    def test_authkit_callback_and_membership_gate(self):
        service = SimpleNamespace(user_management=SimpleNamespace())
        service.user_management.get_authorization_url = lambda **_: "https://auth.example.test/start"
        user = SimpleNamespace(id="user_operator_a", to_dict=lambda: {"id": "user_operator_a"})
        service.user_management.authenticate_with_code = lambda **_: SimpleNamespace(
            organization_id="org_test", access_token="test-access",
            refresh_token="test-refresh", user=user)
        with patch.object(production, "_workos", return_value=service):
            login = self.client.get("/login", base_url="https://canopy.example.test")
            self.assertEqual(login.status_code, 302)
            self.assertEqual(login.location, "https://auth.example.test/start")
            state = self.client.get_cookie("canopy_oauth_state",
                                           domain="canopy.example.test").value
            bad = self.client.get("/callback?state=wrong&code=test",
                                  base_url="https://canopy.example.test")
            self.assertEqual(bad.status_code, 400)
            good = self.client.get(f"/callback?state={state}&code=test",
                                   base_url="https://canopy.example.test")
            self.assertEqual(good.status_code, 302)
            self.assertIsNotNone(self.client.get_cookie("canopy_session",
                                                      domain="canopy.example.test"))

            service.user_management.authenticate_with_code = lambda **_: SimpleNamespace(
                organization_id="org_test", access_token="test-access",
                refresh_token="test-refresh",
                user=SimpleNamespace(id="user_unknown", to_dict=lambda: {"id": "user_unknown"}))
            self.client.get("/login", base_url="https://canopy.example.test")
            denied_state = self.client.get_cookie("canopy_oauth_state",
                                                   domain="canopy.example.test").value
            denied = self.client.get(f"/callback?state={denied_state}&code=test",
                                     base_url="https://canopy.example.test")
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json["error"], "membership_forbidden")

        authenticated = SimpleNamespace(authenticated=True,
                                        user={"id": "user_operator_a"},
                                        organization_id="org_test", role="member",
                                        session_id="session_real", impersonator=None)
        service.user_management.load_sealed_session = lambda **_: SimpleNamespace(
            authenticate=lambda: authenticated)
        self.identity.stop()
        self.identity_stopped = True
        with patch.object(production, "_workos", return_value=service):
            with self.app.test_request_context("/api/v1/session", headers={
                "Host": "canopy.example.test", "Cookie": "canopy_session=sealed"}):
                self.assertEqual(production._identity()["role"], "operator")
            authenticated.user = {"id": "user_unknown"}
            with self.app.test_request_context("/api/v1/session", headers={
                "Host": "canopy.example.test", "Cookie": "canopy_session=sealed"}):
                self.assertIsNone(production._identity())
            authenticated.user = {"id": "user_operator_a"}
            expired = SimpleNamespace(authenticated=False)
            renewed = SimpleNamespace(**vars(authenticated), sealed_session="renewed")
            service.user_management.load_sealed_session = lambda **_: SimpleNamespace(
                authenticate=lambda: expired, refresh=lambda: renewed)
            with self.app.test_request_context("/api/v1/session", headers={
                "Host": "canopy.example.test", "Cookie": "canopy_session=sealed"}):
                self.assertEqual(production._identity()["user_id"], "user_operator_a")
                from flask import g
                self.assertEqual(g.refreshed_session, "renewed")

    def test_backup_restore_and_retention_preview(self):
        from psycopg import connect
        case_id = self.create_case()
        with production._db() as db:
            db.execute("UPDATE canopy_cases SET created_at=now()-interval '45 days' WHERE id=%s",
                       (case_id,))
        self.assertEqual(manage_production.purge(30), 1)
        self.assertEqual(len(self.client.get("/api/v1/cases", headers=self.headers).json["cases"]), 1)
        with tempfile.TemporaryDirectory() as folder:
            archive = manage_production.backup(Path(folder) / "backup.dump")
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
            base = urlsplit(os.environ["DATABASE_URL"])
            restore_name = "canopy_restore_test"
            restore_url = (urlunsplit((base.scheme, base.netloc, "/" + restore_name,
                                       base.query, base.fragment)) if base.netloc else
                           f"{base.scheme}:///{restore_name}?{base.query}")
            with connect(os.environ["DATABASE_URL"], autocommit=True) as db:
                db.execute(f"DROP DATABASE IF EXISTS {restore_name}")
                db.execute(f"CREATE DATABASE {restore_name}")
            try:
                env = manage_production._pg_env()
                env["PGDATABASE"] = restore_name
                subprocess.run(["pg_restore", "--no-owner", "--no-privileges",
                                "--dbname", restore_name, str(archive)], env=env,
                               check=True, capture_output=True)
                with connect(restore_url) as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM canopy_cases").fetchone()[0], 1)
            finally:
                with connect(os.environ["DATABASE_URL"], autocommit=True) as db:
                    db.execute(f"DROP DATABASE IF EXISTS {restore_name}")
        self.assertEqual(manage_production.purge(30, apply=True), 1)
        self.assertEqual(len(self.client.get("/api/v1/cases", headers=self.headers).json["cases"]), 0)


if __name__ == "__main__":
    unittest.main()
