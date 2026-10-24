import base64
import http.client
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import canopy


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = canopy.ThreadingHTTPServer(("127.0.0.1", 0), canopy.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old = (canopy.DB_PATH, canopy.PORT, canopy.OPERATOR_TOKEN, canopy.KEY,
                    canopy.DEMO_MODE, canopy.PUBLIC_ORIGIN)
        canopy.DB_PATH = Path(self.directory.name) / "test.sqlite3"
        canopy.PORT = self.server.server_port
        canopy.OPERATOR_TOKEN = "t" * 40
        canopy.KEY = "test-key"
        canopy.DEMO_MODE = False
        canopy.PUBLIC_ORIGIN = f"http://127.0.0.1:{canopy.PORT}"

    def tearDown(self):
        (canopy.DB_PATH, canopy.PORT, canopy.OPERATOR_TOKEN, canopy.KEY,
         canopy.DEMO_MODE, canopy.PUBLIC_ORIGIN) = self.old
        self.directory.cleanup()

    def request(self, method, path, fields=None, auth=True, origin=True, headers=None):
        headers = dict(headers or {})
        headers["Host"] = f"127.0.0.1:{canopy.PORT}"
        if auth:
            encoded = base64.b64encode(f"operator:{canopy.OPERATOR_TOKEN}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        if origin and method == "POST":
            headers["Origin"] = canopy.PUBLIC_ORIGIN
        body = urlencode(fields).encode() if fields is not None else None
        if body is not None:
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read().decode(), dict(response.getheaders())
        finally:
            connection.close()

    def test_auth_and_health(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.request("GET", "/", auth=False)[0], 401)
        self.assertEqual(self.request("GET", "/livez", auth=False)[0], 200)
        self.assertEqual(self.request("GET", "/readyz")[0], 200)
        with patch.object(canopy, "KEY", ""):
            self.assertEqual(self.request("GET", "/readyz")[0], 503)

    def test_rejects_cross_origin_and_bad_csrf(self):
        fields = {"csrf": canopy.TOKEN, "facts": "A", "reply": "B"}
        self.assertEqual(self.request("POST", "/check", fields, origin=False)[0], 403)
        self.assertEqual(self.request("POST", "/check", {**fields, "csrf": "wrong"})[0], 403)
        self.assertEqual(len(canopy.recent()), 0)

    def test_live_check_review_and_single_use(self):
        with patch.object(canopy, "predict", return_value=("SUPPORTED", "mreq_test", 42)):
            status, body, headers = self.request(
                "POST", "/check", {"csrf": canopy.TOKEN, "facts": "Purchased 2 days ago",
                                   "reply": "You qualify"})
        self.assertEqual(status, 200)
        self.assertIn("mreq_test", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        case_id = canopy.recent()[0]["id"]
        review = {"csrf": canopy.TOKEN, "id": case_id, "verdict": "VIOLATES",
                  "rule": "R2", "reason": "Paid feature was used"}
        self.assertEqual(self.request("POST", "/review", review)[0], 200)
        self.assertEqual(self.request("POST", "/review", review)[0], 400)
        self.assertEqual(canopy.recent()[0]["feedback_status"], "local_only")
        self.assertEqual(canopy.recent()[0]["recording_requested"], 0)

    def test_training_recording_requires_explicit_choice(self):
        with patch.object(canopy, "predict", return_value=("SUPPORTED", "mreq_test", 42)) as predict:
            status, _, _ = self.request(
                "POST", "/check", {"csrf": canopy.TOKEN, "facts": "Synthetic facts",
                                   "reply": "Synthetic reply", "record": "yes"})
        self.assertEqual(status, 200)
        predict.assert_called_once_with("Synthetic facts", "Synthetic reply", record=True)
        self.assertEqual(canopy.recent()[0]["recording_requested"], 1)

    def test_no_key_does_not_spend_a_model_call(self):
        with patch.object(canopy, "KEY", ""), patch.object(canopy, "predict") as predict:
            status, _, _ = self.request(
                "POST", "/check", {"csrf": canopy.TOKEN, "facts": "A", "reply": "B"})
        self.assertEqual(status, 503)
        predict.assert_not_called()
        self.assertEqual(canopy.recent(), [])

    def test_check_is_bounded_and_requires_origin(self):
        fields = {"csrf": canopy.TOKEN, "facts": "A", "reply": "B"}
        with patch.object(canopy, "predict") as predict:
            self.assertEqual(self.request("POST", "/check", fields, origin=False)[0], 403)
            for _ in range(4):
                canopy.PREDICT_LIMIT.acquire()
            try:
                self.assertEqual(self.request("POST", "/check", fields)[0], 429)
            finally:
                for _ in range(4):
                    canopy.PREDICT_LIMIT.release()
            predict.assert_not_called()

    def test_database_migrates_existing_pr_schema(self):
        import sqlite3
        with sqlite3.connect(canopy.DB_PATH) as db:
            db.execute("""CREATE TABLE decisions (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, policy_version TEXT NOT NULL,
                facts TEXT NOT NULL, reply TEXT NOT NULL, prediction TEXT NOT NULL,
                request_id TEXT, latency_ms INTEGER, review_verdict TEXT, review_rule TEXT,
                rationale TEXT, reviewed_at TEXT, feedback_status TEXT NOT NULL DEFAULT 'not_submitted'
            )""")
        number = canopy.create_decision("facts", "reply", "SUPPORTED", "mreq_test", 12)
        self.assertEqual(canopy.recent()[0]["id"], number)
        self.assertEqual(canopy.recent()[0]["policy_hash"], canopy.POLICY_HASH)
        self.assertEqual(canopy.recent()[0]["recording_requested"], 0)
