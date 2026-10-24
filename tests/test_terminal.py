import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import canopy_runtime as runtime


class Response:
    def __init__(self, output, request_id="mreq_test_verified"):
        self.headers = {"x-middleware-request-id": request_id}
        self.data = json.dumps(
            {
                "model": "gpt-4.1-mini",
                "choices": [{"message": {"content": json.dumps(output)}}],
                "usage": {"total_tokens": 100},
            }
        ).encode()

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ChatResponse(Response):
    def __init__(self, answer, request_id="mreq_chat_verified"):
        self.headers = {"x-middleware-request-id": request_id}
        self.data = json.dumps(
            {
                "model": "gpt-4.1-mini",
                "choices": [{"message": {"content": answer}}],
                "usage": {"total_tokens": 42},
            }
        ).encode()


class TerminalTests(unittest.TestCase):
    fields = {
        "policy": "Damaged items qualify for a refund within 30 days.",
        "evidence": "The item arrived damaged 21 days ago.",
        "claim": "The item must be refused a refund.",
    }
    verdict = {
        "verdict": "VIOLATES",
        "reason": "The damaged-item exception applies.",
        "policy_excerpt": "Damaged items qualify for a refund within 30 days.",
        "missing": [],
    }

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(
                runtime, "DB_PATH", Path(self.directory.name) / "cases.sqlite3"
            ),
            patch.object(runtime, "KEY", "test-key"),
            patch.dict(
                os.environ,
                {
                    "CANOPY_OPERATOR_TOKEN": "",
                    "CANOPY_PUBLIC_ORIGIN": "http://localhost",
                },
            ),
        ]
        for item in self.patches:
            item.start()
        runtime.RUNS.clear()
        runtime.CHAT_BUSY.clear()
        self.client = runtime.app.test_client()
        self.client.get("/").close()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def run_case(self, payload=None, replies=None):
        replies = replies or [Response(self.verdict)]
        with patch.object(
            runtime.urllib.request, "urlopen", side_effect=replies
        ) as provider:
            response = self.client.post("/api/runs", json=payload or self.fields)
            self.assertEqual(response.status_code, 202)
            ident = response.json["id"]
            for _ in range(150):
                data = self.client.get("/api/runs/" + ident).json
                if data["status"] != "running":
                    for worker in threading.enumerate():
                        if worker.name == "canopy-run-" + ident:
                            worker.join(timeout=3)
                            self.assertFalse(
                                worker.is_alive(), "Run did not finish persisting"
                            )
                    return self.client.get("/api/runs/" + ident).json, provider
                time.sleep(0.01)
        self.fail("Run failed to finish")

    def test_real_task_uses_gateway_and_captures_provenance(self):
        data, provider = self.run_case()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["result"]["request_id"], "mreq_test_verified")
        req = provider.call_args.args[0]
        self.assertEqual(
            req.full_url, "https://api.mubit.ai/openai/v1/chat/completions"
        )
        self.assertEqual(req.get_header("X-middleware-record"), "off")
        self.assertEqual(
            json.loads(req.data)["messages"][1]["content"], json.dumps(self.fields)
        )
        self.assertNotIn("accuracy", data)
        self.assertNotIn("version", data)

    def test_chat_is_multi_turn_and_all_calls_use_mubit(self):
        with patch.object(
            runtime.urllib.request,
            "urlopen",
            side_effect=[
                ChatResponse("Hello."),
                ChatResponse("You asked me to say hello."),
            ],
        ) as provider:
            first = self.client.post("/api/chats", json={"input": "Say hello"})
            self.assertEqual(first.status_code, 200)
            ident = first.json["id"]
            self.assertEqual(first.json["messages"][1]["content"], "Hello.")
            second = self.client.post(
                f"/api/chats/{ident}/messages",
                json={"input": "What did I ask?", "record": True},
            )
            self.assertEqual(second.status_code, 200)
            self.assertEqual(len(second.json["messages"]), 4)
            self.assertEqual(provider.call_count, 2)
            calls = [call.args[0] for call in provider.call_args_list]
            self.assertTrue(
                all(
                    req.full_url == "https://api.mubit.ai/openai/v1/chat/completions"
                    for req in calls
                )
            )
            self.assertEqual(calls[0].get_header("X-middleware-record"), "off")
            self.assertEqual(calls[1].get_header("X-middleware-record"), "full")
            sent = json.loads(calls[1].data)["messages"]
            self.assertEqual(
                [item["role"] for item in sent], ["system", "user", "assistant", "user"]
            )
            self.assertEqual(sent[1]["content"], "Say hello")
            self.assertEqual(sent[2]["content"], "Hello.")
        self.assertEqual(self.client.get("/api/chats").json[0]["id"], ident)
        self.assertEqual(
            self.client.get(f"/api/chats/{ident}").json["messages"][3]["request_id"],
            "mreq_chat_verified",
        )

    def test_chat_is_private_to_browser_session(self):
        with patch.object(
            runtime.urllib.request, "urlopen", return_value=ChatResponse("Hi")
        ):
            first = self.client.post("/api/chats", json={"input": "Hi"})
        ident = first.json["id"]
        other = runtime.app.test_client()
        other.get("/").close()
        self.assertEqual(other.get("/api/chats").json, [])
        self.assertEqual(other.get(f"/api/chats/{ident}").status_code, 404)
        self.assertEqual(
            other.post(
                f"/api/chats/{ident}/messages", json={"input": "Hi"}
            ).status_code,
            404,
        )

    def test_chat_rejects_unverified_reply_without_saving(self):
        with patch.object(
            runtime.urllib.request, "urlopen", return_value=ChatResponse("Hi", "")
        ):
            response = self.client.post("/api/chats", json={"input": "Hi"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("provenance", response.json["error"])
        self.assertEqual(self.client.get("/api/chats").json, [])

    def test_recording_is_opt_in(self):
        _, provider = self.run_case({**self.fields, "record": True})
        self.assertEqual(
            provider.call_args.args[0].get_header("X-middleware-record"), "full"
        )

    def test_missing_input_does_not_invent_evidence_or_verify(self):
        data, provider = self.run_case(
            {"input": "Is it compliant?"},
            [Response({"policy": "", "evidence": "", "claim": "It is compliant."})],
        )
        self.assertEqual(data["status"], "needs_input")
        self.assertEqual(data["missing"], ["policy", "evidence"])
        self.assertEqual(provider.call_count, 1)

    def test_parser_and_verifier_are_separate_observable_calls(self):
        data, provider = self.run_case(
            {"input": "Supplied fictional case"},
            [
                Response(self.fields, "mreq_parse"),
                Response(self.verdict, "mreq_verify"),
            ],
        )
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(data["parse_request_id"], "mreq_parse")
        self.assertEqual(data["result"]["request_id"], "mreq_verify")
        self.assertEqual(
            [e["tool"] for e in data["events"] if e["state"] == "running"],
            ["mubit.extract", "mubit.verify"],
        )

    def test_unverified_provider_response_is_a_failed_run(self):
        data, _ = self.run_case(replies=[Response(self.verdict, "")])
        self.assertEqual(data["status"], "failed")
        self.assertIn("provenance", data["error"])

    def test_feedback_is_durable_bound_to_case_and_single_use(self):
        data, _ = self.run_case()
        path = "/api/runs/" + data["id"] + "/review"
        review = {
            "verdict": "INSUFFICIENT",
            "reason": "The damage has not been independently established.",
        }
        response = self.client.post(path, json=review)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "local_only")
        self.assertEqual(response.json["request_id"], data["result"]["request_id"])
        self.assertEqual(self.client.post(path, json=review).status_code, 409)
        runtime.RUNS.clear()
        stored = self.client.get("/api/runs/" + data["id"]).json
        self.assertEqual(stored["review"]["reason"], review["reason"])

    def test_cases_are_scoped_to_browser_session(self):
        data, _ = self.run_case()
        other = runtime.app.test_client()
        other.get("/").close()
        self.assertEqual(other.get("/api/cases").json, [])
        self.assertEqual(other.get("/api/runs/" + data["id"]).status_code, 404)
        self.assertEqual(
            other.post(
                "/api/runs/" + data["id"] + "/review",
                json={"verdict": "SUPPORTED", "reason": "wrong owner"},
            ).status_code,
            404,
        )

    def test_no_key_or_invalid_body_never_spends_a_call(self):
        with (
            patch.object(runtime, "KEY", ""),
            patch.object(runtime.urllib.request, "urlopen") as provider,
        ):
            self.assertEqual(
                self.client.post("/api/runs", json=self.fields).status_code, 503
            )
            provider.assert_not_called()
        self.assertEqual(self.client.post("/api/runs", json=[]).status_code, 400)
        self.assertEqual(
            self.client.post("/api/runs", json={"input": "x" * 33000}).status_code, 400
        )
        self.assertEqual(
            self.client.post(
                "/api/runs", json=self.fields, headers={"Origin": "https://other.test"}
            ).status_code,
            403,
        )

    def test_capacity_and_provider_failure_are_visible_and_recoverable(self):
        for _ in range(3):
            runtime.CAPACITY.acquire()
        try:
            self.assertEqual(
                self.client.post("/api/runs", json=self.fields).status_code, 429
            )
        finally:
            for _ in range(3):
                runtime.CAPACITY.release()
        error = runtime.urllib.error.HTTPError(
            "https://api.mubit.ai",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"error":{"code":"starter_credit_route"}}'),
        )
        data, _ = self.run_case(replies=[error])
        self.assertEqual(data["status"], "failed")
        self.assertIn("403", data["error"])
        self.assertNotIn("test-key", data["error"])
        recovered, _ = self.run_case()
        self.assertEqual(recovered["status"], "completed")

    def test_invented_policy_quote_is_not_displayed_as_evidence(self):
        data, _ = self.run_case(
            replies=[Response({**self.verdict, "policy_excerpt": "An invented rule"})]
        )
        self.assertEqual(data["result"]["policy_excerpt"], "")

    def test_configured_operator_gate_and_health(self):
        with patch.dict(os.environ, {"CANOPY_OPERATOR_TOKEN": "operator-token"}):
            self.assertEqual(self.client.get("/").status_code, 401)
            self.assertEqual(self.client.get("/livez").status_code, 200)
            self.assertEqual(
                self.client.get(
                    "/readyz", auth=("operator", "operator-token")
                ).status_code,
                200,
            )


if __name__ == "__main__":
    unittest.main()
