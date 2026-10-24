# Production readiness gates

Canopy is a **single-operator pilot**, not a customer-facing multi-tenant service. Passing source tests does not prove live Mubit access, adapter learning, or a safe public deployment.

| Gate | Current evidence | Required before claiming completion |
|---|---|---|
| Auth and transport | 32+ character operator token is required outside local demo mode; non-local public origin must be HTTPS; service binds to loopback by default. | Deploy behind a TLS reverse proxy, keep the app port private, test authenticated access through the actual public URL, and rotate a test token. |
| Data handling | Recording is off by default; explicit operator choice requests full recording. SQLite and backups are owner-only from creation; backup, retention, and case deletion commands exist. | Approve the actual data classification, retention schedule, backup location, and Mubit/provider data terms. Do not send private customer records until those decisions are made. |
| Policy integrity | Policy JSON is validated at startup; each new decision stores its policy version, hash, and full rule snapshot. Reviews use that snapshot after policy changes; legacy cases without a snapshot cannot be reviewed. System instructions stay stable. | Replace the fictional sample with an approved real policy, retain every published policy revision, and have domain owners validate evaluation labels. |
| Model routing | Source fixes the Mubit base URL and rejects responses without an `mreq_` ID. | Run an authenticated live call and match its request ID and payload to Mubit Requests. Confirm the selected provider model is available. |
| Learning loop | Human review is durably stored as `local_only`. Guessed feedback endpoints were removed. | Obtain and implement the hackathon's documented correction contract; verify accepted feedback, kept examples, training status, and an actual adapter result. A local review does not satisfy this gate. |
| Quality | Fixed sample-policy collection and holdout sets, per-case outputs, latency, and errors. Holdout requests recording off. | Run a live baseline, then evaluate a confirmed passing adapter on unseen cases. Report provider, Mubit test, and human labels separately; do not infer improvement from cumulative accuracy. |
| Operations | Gunicorn serves the Flask app; `/livez`, authenticated `/readyz`, bounded requests and concurrent calls, safe structured logs, non-root image, 19 local tests, a hash-locked Python 3.11 dependency set, and CI dependency audit. | Build and run the container in the target environment; verify persistence, restart, backup/restore, log collection, error alerts, and resource limits. |

## Deployment acceptance run

1. Set secrets through the target platform; do not place them in the repo, image, command history, screenshots, or recordings.
2. Start with a persistent private volume and verify `/readyz` through the proxy using operator auth.
3. Check cross-origin rejection, invalid token rejection, and direct-port isolation from outside the host.
4. Send one approved synthetic check, review it, restart, and confirm the case and policy hash persist.
5. Take a backup, restore it in a separate stopped test instance, and verify the case count.
6. Run the live Mubit and correction-to-adapter gates above. Keep these as separate evidence from CI and container build results.
