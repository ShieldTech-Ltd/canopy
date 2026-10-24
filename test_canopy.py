import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import canopy
from cases import HOLDOUT, TRAIN


class CanopyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old_path = canopy.DB_PATH
        canopy.DB_PATH = Path(self.directory.name) / "test.sqlite3"

    def tearDown(self):
        canopy.DB_PATH = self.old_path
        self.directory.cleanup()

    def test_dataset_is_distinct_and_separate(self):
        self.assertEqual(len(TRAIN), 40)
        self.assertEqual(len(HOLDOUT), 12)
        key = lambda c: (c["facts"], c["reply"])
        self.assertEqual(len({key(c) for c in TRAIN}), len(TRAIN))
        self.assertFalse({key(c) for c in TRAIN} & {key(c) for c in HOLDOUT})
        self.assertTrue({c["truth"] for c in HOLDOUT} == canopy.VERDICTS)

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


if __name__ == "__main__":
    unittest.main()
