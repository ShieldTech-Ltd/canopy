import tempfile
import unittest
import sqlite3
import json
import shutil
import os
from contextlib import closing
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from canopy_app import canopy, manage
from canopy_app.cases import HOLDOUT, SAMPLE_POLICY_HASH, TRAIN


class CanopyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old_path = canopy.DB_PATH
        canopy.DB_PATH = Path(self.directory.name) / "test.sqlite3"

    def tearDown(self):
        canopy.DB_PATH = self.old_path
        self.directory.cleanup()

    def test_dataset_is_distinct_and_separate(self):
        self.assertEqual(canopy.POLICY_HASH, SAMPLE_POLICY_HASH)
        self.assertEqual(len(TRAIN), 40)
        self.assertEqual(len(HOLDOUT), 12)
        key = lambda c: (c["facts"], c["reply"])
        self.assertEqual(len({key(c) for c in TRAIN}), len(TRAIN))
        self.assertFalse({key(c) for c in TRAIN} & {key(c) for c in HOLDOUT})
        self.assertTrue({c["truth"] for c in HOLDOUT} == canopy.VERDICTS)

    def test_policy_is_validated_and_system_instruction_stays_stable(self):
        self.assertNotIn(canopy.POLICY["version"], canopy.prompt())
        custom = Path(self.directory.name) / "policy.json"
        custom.write_text(json.dumps({
            "version": "v2", "rules": [{"id": "NEW", "text": "A new approved rule."}]
        }))
        self.assertEqual(canopy.load_policy(custom)["version"], "v2")
        custom.write_text(json.dumps({
            "version": "v2", "rules": [
                {"id": "DUP", "text": "one"}, {"id": "DUP", "text": "two"}
            ]
        }))
        with self.assertRaisesRegex(ValueError, "unique"):
            canopy.load_policy(custom)

    def test_review_is_durable_single_use_and_not_submitted(self):
        number = canopy.create_decision("Purchase was 2 days ago.", "You qualify.",
                                        "VIOLATES", "mreq_test", 123)
        self.assertTrue(canopy.review(number, "SUPPORTED", "R1", "Within 14 days; no usage."))
        self.assertFalse(canopy.review(number, "VIOLATES", "R2", "second review"))
        row = canopy.recent()[0]
        self.assertEqual(row["review_verdict"], "SUPPORTED")
        self.assertEqual(row["feedback_status"], "local_only")
        self.assertEqual(row["request_id"], "mreq_test")

    def test_invalid_review_does_not_change_row(self):
        number = canopy.create_decision("facts", "reply", "SUPPORTED", None, 10)
        with self.assertRaises(ValueError):
            canopy.review(number, "APPROVED", "R1", "wrong")
        self.assertIsNone(canopy.recent()[0]["review_verdict"])

    def test_review_uses_policy_at_decision_time(self):
        number = canopy.create_decision("facts", "reply", "SUPPORTED", "mreq_test", 10)
        self.assertEqual(json.loads(canopy.recent()[0]["policy_json"]), canopy.POLICY)
        new_policy = {"version": "v2", "rules": [{"id": "NEW", "text": "New rule"}]}
        with patch.object(canopy, "POLICY", new_policy):
            self.assertIn('name="rule"><option>R1', canopy.page())
            self.assertNotIn('name="rule"><option>NEW', canopy.page())
            with self.assertRaisesRegex(ValueError, "this case"):
                canopy.review(number, "VIOLATES", "NEW", "New rule")
            self.assertTrue(canopy.review(number, "VIOLATES", "R1", "Original rule"))

    def test_legacy_case_without_policy_snapshot_cannot_be_reviewed(self):
        number = canopy.create_decision("facts", "reply", "SUPPORTED", "mreq_test", 10)
        with closing(sqlite3.connect(canopy.DB_PATH)) as db:
            db.execute("UPDATE decisions SET policy_json=NULL WHERE id=?", (number,))
            db.commit()
        with self.assertRaisesRegex(ValueError, "Legacy case"):
            canopy.review(number, "VIOLATES", "R1", "No snapshot")
        self.assertIn("Review unavailable: legacy case", canopy.page())

    def test_html_escapes_model_inputs(self):
        canopy.create_decision("<script>alert(1)</script>", "<img src=x>",
                               "SUPPORTED", None, 12)
        rendered = canopy.page()
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img src=x>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_no_key_never_calls_provider(self):
        with patch.object(canopy, "KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "MUBIT_API_KEY"):
                canopy.predict("facts", "reply")

    def test_file_secret_and_ambiguous_config(self):
        secret_file = Path(self.directory.name) / "secret"
        secret_file.write_text("test-secret\n")
        with patch.dict(os.environ, {"TEST_SECRET_FILE": str(secret_file)}, clear=True):
            self.assertEqual(canopy.secret("TEST_SECRET"), "test-secret")
        with patch.dict(os.environ, {"TEST_SECRET_FILE": str(secret_file),
                                     "TEST_SECRET": "other"}, clear=True):
            with self.assertRaisesRegex(ValueError, "only"):
                canopy.secret("TEST_SECRET")

    def test_provider_recording_opt_in_and_mubit_provenance(self):
        calls = []
        class Raw:
            headers = {"x-middleware-request-id": "mreq_verified"}
            def parse(self):
                return SimpleNamespace(choices=[
                    SimpleNamespace(message=SimpleNamespace(content="SUPPORTED"))
                ])
        class Client:
            def __init__(self, **kwargs):
                self.chat = SimpleNamespace(completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=self.create)))
            def create(self, **kwargs):
                calls.append(kwargs)
                return Raw()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
        with patch.object(canopy, "KEY", "test"), patch.dict(
            "sys.modules", {"openai": SimpleNamespace(OpenAI=Client)}
        ):
            self.assertEqual(canopy.predict("facts", "reply")[1], "mreq_verified")
            self.assertEqual(canopy.predict("facts", "reply", record=True)[1], "mreq_verified")
        self.assertEqual(calls[0]["extra_headers"]["x-middleware-record"], "off")
        self.assertEqual(calls[1]["extra_headers"]["x-middleware-record"], "full")
        self.assertEqual(calls[0]["messages"][0]["content"], canopy.prompt())
        data = json.loads(calls[0]["messages"][1]["content"])
        self.assertEqual(data["policy"]["version"], canopy.POLICY["version"])
        self.assertEqual(data["customer_facts"], "facts")

    def test_config_rejects_unprotected_public_binding(self):
        with patch.object(canopy, "HOST", "0.0.0.0"), patch.object(
            canopy, "PUBLIC_ORIGIN", "http://example.com"
        ), patch.object(canopy, "OPERATOR_TOKEN", ""), patch.object(canopy, "DEMO_MODE", False):
            with self.assertRaises(ValueError):
                canopy.validate_config()

    def test_backup_and_retention_are_explicit(self):
        old = canopy.create_decision("old", "reply", "SUPPORTED", "mreq_old", 12)
        recent = canopy.create_decision("new", "reply", "SUPPORTED", "mreq_new", 12)
        with closing(sqlite3.connect(canopy.DB_PATH)) as db:
            db.execute("UPDATE decisions SET created_at='2020-01-01T00:00:00+00:00' WHERE id=?", (old,))
            db.commit()
        target = Path(self.directory.name) / "backup.sqlite3"
        self.assertEqual(manage.backup(target), target)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(manage.purge(30), 1)
        self.assertEqual(len(canopy.recent()), 2)
        self.assertEqual(manage.purge(30, apply=True), 1)
        self.assertEqual([row["id"] for row in canopy.recent()], [recent])
        self.assertEqual(manage.delete_case(recent), 1)
        self.assertEqual(manage.delete_case(recent, apply=True), 1)
        self.assertEqual(canopy.recent(), [])
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM decisions").fetchone()[0], 2)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        restored = Path(self.directory.name) / "restored.sqlite3"
        shutil.copy2(target, restored)
        with patch.object(canopy, "DB_PATH", restored):
            self.assertEqual(len(canopy.recent()), 2)
            self.assertTrue(all(row["policy_json"] for row in canopy.recent()))

    def test_database_rejects_readable_existing_file(self):
        canopy.DB_PATH.touch(mode=0o644)
        canopy.DB_PATH.chmod(0o644)
        with self.assertRaisesRegex(PermissionError, "owner-only"):
            canopy.database()


if __name__ == "__main__":
    unittest.main()
