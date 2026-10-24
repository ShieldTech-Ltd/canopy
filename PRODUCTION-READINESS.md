# Deployment readiness

This document covers the active terminal workspace (`canopy_runtime.py`) and its public demo. It is a **single-operator pilot**, not a customer-facing multi-user service. The separate `canopy_app/` policy application has different controls and storage; its checks must not be attributed to this app.

| Gate | Current implementation | Live acceptance required |
|---|---|---|
| Access | Optional HTTP Basic Auth via `CANOPY_OPERATOR_TOKEN`; session-scoped cases and chats; browser POSTs with a mismatched `Origin` are rejected. | Set the operator secret and exact HTTPS `CANOPY_PUBLIC_ORIGIN` on Render. Verify unauthenticated requests fail and authorised browser requests work. Arrange judge access through the approved event channel. |
| Storage | The active app uses SQLite at `CANOPY_AGENT_DB`, locally `canopy-agent.sqlite3` by default. | Point `CANOPY_AGENT_DB` at a Render persistent disk and verify a reviewed case survives restart. Without a disk, disclose that persistence is limited to the current deployment. |
| Mubit routing | Chat, extraction, and verification use the Mubit gateway; model responses without an `mreq_` ID are rejected. | Make a live fictional verification, match its ID and payload in Mubit Requests, and confirm the provider model works. Key presence in `/readyz` or `/api/status` is insufficient. |
| Feedback and learning | One reviewer verdict and reason are saved with the verification request ID as `local_only`. | Obtain a documented supported correction workflow, observe acceptance and kept-example status, then trace any adapter result. Until then, do not claim learning or improvement. |
| Data | Recording is opt-in for verification and chat; extraction is not retained. Cases and chats are stored under a browser session ID. | Use fictional or explicitly approved non-sensitive cases. Agree data retention and provider terms before customer data. |
| Quality | Unit tests cover routing, provenance, missing evidence, review, isolation, and failure paths with mocked Mubit responses. | Evaluate independently labelled unseen cases if a passing adapter becomes available; report provider, adapter, and human labels separately. |
| Operations | The image runs as non-root; Gunicorn serves one worker with eight threads. CI builds and smoke-tests the image and legacy Compose deployment. | Check the deployed build, authenticated readiness, restart persistence, provider failures, logs, and a real browser walkthrough. |

Run and record the steps in [Demo acceptance](docs/DEMO-ACCEPTANCE.md). Green CI, a deployed URL, and 25 successful calls do not establish 25 kept examples or a trained adapter.
