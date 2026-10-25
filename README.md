![Canopy: Policy checks you can inspect](docs/brand/canopy-readme-banner.png)

# Canopy

**Policy checks you can inspect.** Canopy is a Night Shift prototype for support and operations teams who need to check a claim against a supplied policy and case evidence. It returns **SUPPORTED**, **VIOLATES**, or **INSUFFICIENT**, with a reason and an inspectable execution trace.

[Open the deployed app](https://canopy-sbs0.onrender.com/) · [Submitted demo walkthrough](docs/submission/RECORDING-SCRIPT.md)

Give Canopy the policy, what happened, and the claim to test. It requests missing facts instead of filling them in. The app routes model calls through Mubit and shows the returned `mreq_` request IDs. A person can confirm or correct a verdict with a written reason; that review is currently stored in Canopy only.

The landing page opens in **Chat with Canopy** for ordinary multi-turn text conversation. Select **Verify a case** for the policy workflow. New chat starts a separate thread; earlier chats can be reopened from the sidebar. The built-in refund and access cases are fictional demo examples, not measured customer results.

![Canopy's verification workspace with example cases, session history, and an empty execution trace](docs/demo/terminal.jpg)

## Architecture

```mermaid
flowchart LR
    B[Browser: chat or verification] --> F[Flask / Gunicorn]
    F -->|Chat, extraction, verification| M[Mubit OpenAI gateway]
    M --> P[Configured provider model]
    M -->|Response and mreq_ ID| F
    F <--> D[(Session-scoped SQLite cases and chats)]
    B -->|Human verdict and reason| F
    F -->|Local review linked to mreq_ ID| D
    D -. No confirmed feedback submission .-> M
```

## What runs today

1. Natural-language cases are extracted through the Mubit gateway. Missing policy or facts are requested rather than invented.
2. The recurring verification task also runs through Mubit, using the configured provider model.
3. The execution panel shows actual request IDs, model responses, token counts and timings. It is a read-only tool trace, not a shell or model chain of thought.
4. Cases and human reviews are stored in SQLite and scoped to the browser session.
5. A reviewer can supply SUPPORTED, VIOLATES or INSUFFICIENT with a reason. The review is linked to the original verification request.
6. Customer chats keep their message history in session-scoped SQLite and show real Mubit request IDs and timings. Chat is text only; it does not access unseen case history or perform a policy verdict.

**Current limitation:** human corrections are saved locally. The event team's supported correction-to-adapter integration is not connected. Canopy does not report that a model was trained, invent adapter versions, or claim measured accuracy improvement. A recorded call is not necessarily a *kept* training example.

The verification instruction was refined on 25 October to distinguish a missing record from evidence that a required step did not happen. Mubit may group calls with the revised instruction into a new task; use the current task's kept-example count rather than adding counts from earlier versions.

All inference in this entrypoint goes through `https://api.mubit.ai/openai/v1`.

## Run locally

Use Python 3.11 or later. Install the existing dependencies:

```powershell
python -m pip install -r requirements.txt
$env:MUBIT_API_KEY = "your-key"
$env:MUBIT_MODEL = "gpt-4.1-mini"
python canopy.py
```

Open http://localhost:8080. An existing `.env` file is loaded; it stays gitignored. You can use `CANOPY_ENV_FILE` to point at a separate local file. Do not commit credentials.

- `PORT`: HTTP port, default 8080.
- `MUBIT_MODEL`: provider model supported by your workspace.
- `CANOPY_AGENT_DB`: SQLite path, default `canopy-agent.sqlite3` locally.
- `CANOPY_OPERATOR_TOKEN`: optional operator Basic Auth password (username `operator`). Configure it for a protected public demo; this is not multi-user identity.
- `CANOPY_PUBLIC_ORIGIN`: exact public origin for browser POST checks, for example `https://canopy-sbs0.onrender.com`.
- `MUBIT_API_KEY_FILE` and `CANOPY_OPERATOR_TOKEN_FILE`: alternative mounted-secret paths. Set a value or its file path, never both.

The browser's training-retention checkbox requests full recording for the verification or chat call. It is off by default. Extraction is not retained. Requesting recording does not guarantee that Mubit accepts a training example. Do not select retention for sensitive customer conversations without authorization.

## What the submitted demo shows

The submitted 1:43 video uses edited captures of a real run on the deployed app. It opens with the Canopy introduction, then follows one fictional refund case:

1. The supplied policy has a normal 14-day refund window and a 30-day exception for damaged items, even after use. The customer returned a damaged item on day 21 with photos. The claim says the refund must be refused.
2. Training retention is requested for this fictional case. Canopy calls Mubit for extraction and verification, then returns **VIOLATES** with the relevant policy quote, supplied facts, and fresh `mreq_` request IDs.
3. A reviewer confirms that verdict with a written reason. The video reopens the case in the same browser session to show the review saved in Canopy and linked to the verification request. This is a confirmation, not a correction to the model.
4. The Mubit console shows 35 total requests in the prior 24 hours, zero errors, and the matching refund request with the same policy, evidence, claim, and `VIOLATES` reply. These are counts captured for the video, not live totals.
5. The newer verification task shows three calls and zero of 25 kept examples. No adapter is serving. The console's 0% routed metric refers to adapter or base routing under task rules; the request is separately visible in Mubit Requests as a Middleware call.

The video does **not** show a submitted correction entering Mubit training, a model update, or measured quality improvement. Human reviews remain `local_only`. It also does not exercise Chat with Canopy, the access example, or the other verdict types described above. See the [walkthrough and evidence notes](docs/submission/RECORDING-SCRIPT.md) for the exact sequence and limits.

## Deployment

`Procfile` starts `python canopy.py`. On Linux, this entrypoint launches Gunicorn with one worker and eight threads. The Docker image includes the UI and runtime, runs as a non-root user, and sets `CANOPY_AGENT_DB=/data/canopy-agent.sqlite3`. A Render native `Procfile` deployment does **not** inherit the Docker setting: set `CANOPY_AGENT_DB` to a mounted persistent disk path. Without a persistent disk, cases can disappear on restart or redeploy.

Health endpoints: `/livez` checks the process; `/readyz` checks key presence and local storage. Neither spends a model call. `/api/status` exposes the build identifier and reports `configured=true` when a key exists. That value does **not** prove a live Mubit request succeeded.

The previous support-policy application remains in `canopy_app/`. Set `CANOPY_APP=policy` to run it. The existing Caddy Compose deployment explicitly selects this legacy application, preserving its separate security and persistence workflow.

## Checks

```powershell
python -m unittest discover -s tests -p test_terminal.py -v
node --check canopy_ui/app.js
```

The terminal tests cover gateway request construction, provenance validation, missing evidence, recording choice, provider failure and recovery, case ownership, durable local reviews, duplicate review rejection, limits and authentication. Provider responses are mocked in unit tests. These tests do not prove the deployed service or Mubit adapter status.
They also cover multi-turn chat context, session isolation, recording choice and refusal to save replies without Mubit provenance.

Before recording, verify the deployed build, a fresh request in Mubit Requests, a review reopened in the same session, and the task's actual adapter status. The [recording guide](docs/submission/RECORDING-SCRIPT.md) lists those checks.

## Files

- `canopy.py`: application entrypoint.
- `canopy_runtime.py`: Mubit calls, run events, HTTP endpoints and storage.
- `canopy_ui/`: terminal interface, styles and browser behaviour.
- `tests/test_terminal.py`: tests for this runtime.
- `canopy_app/`: separate original support-policy implementation.
