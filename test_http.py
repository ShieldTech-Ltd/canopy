import base64
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import canopy


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old = (canopy.DB_PATH, canopy.OPERATOR_TOKEN, canopy.KEY,
                    canopy.DEMO_MODE, canopy.PUBLIC_ORIGIN)
        canopy.DB_PATH = Path(self.directory.name) / "test.sqlite3"
        canopy.OPERATOR_TOKEN = "t" * 40
        canopy.KEY = "test-key"
        canopy.DEMO_MODE = False
        canopy.PUBLIC_ORIGIN = f"http://127.0.0.1:{canopy.PORT}"
        self.client = canopy.app.test_client()

    def tearDown(self):
        (canopy.DB_PATH, canopy.OPERATOR_TOKEN, canopy.KEY,
         canopy.DEMO_MODE, canopy.PUBLIC_ORIGIN) = self.old
        self.directory.cleanup()

    def headers(self, auth=True, origin=True):
        headers = {"Host": f"127.0.0.1:{canopy.PORT}"}
        if auth:
            encoded = base64.b64encode(f"operator:{canopy.OPERATOR_TOKEN}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        if origin:
            headers["Origin"] = canopy.PUBLIC_ORIGIN
        return headers

    def test_auth_and_health(self):
        self.assertEqual(self.client.get("/", headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.get("/", headers=self.headers(auth=False)).status_code, 401)
        self.assertEqual(self.client.get("/livez").status_code, 200)
        self.assertEqual(self.client.get("/readyz", headers=self.headers()).status_code, 200)
        with patch.object(canopy, "KEY", ""):
            self.assertEqual(self.client.get("/readyz", headers=self.headers()).status_code, 503)

    def test_rejects_cross_origin_and_bad_csrf(self):
        fields = {"csrf": canopy.TOKEN, "facts": "A", "reply": "B"}
        self.assertEqual(self.client.post("/check", data=fields,
                                          headers=self.headers(origin=False)).status_code, 403)
        self.assertEqual(self.client.post("/check", data={**fields, "csrf": "wrong"},
                                          headers=self.headers()).status_code, 403)
        self.assertEqual(canopy.recent(), [])

    def test_live_check_review_and_single_use(self):
        with patch.object(canopy, "predict", return_value=("SUPPORTED", "mreq_test", 42)):
            response = self.client.post(
                "/check", data={"csrf": canopy.TOKEN, "facts": "Purchased 2 days ago",
                                "reply": "You qualify"}, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"mreq_test", response.data)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        case_id = canopy.recent()[0]["id"]
        review = {"csrf": canopy.TOKEN, "id": case_id, "verdict": "VIOLATES",
                  "rule": "R2", "reason": "Paid feature was used"}
        self.assertEqual(self.client.post("/review", data=review,
                                          headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.post("/review", data=review,
                                          headers=self.headers()).status_code, 400)
        self.assertEqual(canopy.recent()[0]["feedback_status"], "local_only")
        self.assertEqual(canopy.recent()[0]["recording_requested"], 0)

    def test_training_recording_requires_explicit_choice(self):
        with patch.object(canopy, "predict", return_value=("SUPPORTED", "mreq_test", 42)) as predict:
            response = self.client.post(
                "/check", data={"csrf": canopy.TOKEN, "facts": "Synthetic facts",
                                "reply": "Synthetic reply", "record": "yes"},
                headers=self.headers())
        self.assertEqual(response.status_code, 200)
        predict.assert_called_once_with("Synthetic facts", "Synthetic reply", record=True)
        self.assertEqual(canopy.recent()[0]["recording_requested"], 1)

    def test_no_key_does_not_spend_a_model_call(self):
        with patch.object(canopy, "KEY", ""), patch.object(canopy, "predict") as predict:
            response = self.client.post(
                "/check", data={"csrf": canopy.TOKEN, "facts": "A", "reply": "B"},
                headers=self.headers())
        self.assertEqual(response.status_code, 503)
        predict.assert_not_called()

    def test_check_is_bounded(self):
        fields = {"csrf": canopy.TOKEN, "facts": "A", "reply": "B"}
        with patch.object(canopy, "predict") as predict:
            for _ in range(4):
                canopy.PREDICT_LIMIT.acquire()
            try:
                response = self.client.post("/check", data=fields, headers=self.headers())
            finally:
                for _ in range(4):
                    canopy.PREDICT_LIMIT.release()
        self.assertEqual(response.status_code, 429)
        predict.assert_not_called()

    def test_database_migrates_existing_pr_schema(self):
        with closing(sqlite3.connect(canopy.DB_PATH)) as db:
            db.execute("""CREATE TABLE decisions (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, policy_version TEXT NOT NULL,
                facts TEXT NOT NULL, reply TEXT NOT NULL, prediction TEXT NOT NULL,
                request_id TEXT, latency_ms INTEGER, review_verdict TEXT, review_rule TEXT,
                rationale TEXT, reviewed_at TEXT, feedback_status TEXT NOT NULL DEFAULT 'not_submitted'
            )""")
            db.commit()
        canopy.DB_PATH.chmod(0o600)
        number = canopy.create_decision("facts", "reply", "SUPPORTED", "mreq_test", 12)
        self.assertEqual(canopy.recent()[0]["id"], number)
        self.assertEqual(canopy.recent()[0]["policy_hash"], canopy.POLICY_HASH)
        self.assertEqual(canopy.recent()[0]["recording_requested"], 0)
