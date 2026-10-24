# Canopy

Canopy checks drafted support replies against a small, versioned refund policy. A reviewer can correct a verdict and record the rule and reason. It is a focused **Recurring tasks** MVP for Night Shift 2026.

## Repository layout

`canopy_app/` holds the existing application, evaluation cases, and database maintenance code. `tests/` holds the regression tests. The three root entry points (`canopy.py`, `manage.py`, and `evaluate.py`) keep the existing run commands working. Deployment files are in `deploy/`, and operational smoke checks are in `scripts/`. This layout changes imports and file paths only; it does not add multi-instance support.

The bundled policy and cases are fictional demo material. The app has no customer integration. Its default network binding is localhost; a container deployment can bind internally to all interfaces only with operator authentication and a declared HTTPS public origin.

## What is real today

- Every live model check uses the OpenAI client with the Mubit base URL. The Mubit key stays on the server and comes from `MUBIT_API_KEY`. A call lacking Mubit's `mreq_` request ID is rejected.
- A successful check stores the verdict, policy version and SHA-256 fingerprint, latency, recording choice, and Mubit request ID in local SQLite.
- The system instruction stays fixed across policy revisions. The current policy and customer case are supplied as task data, so a policy update does not silently redefine the Mubit task instructions.
- Mubit recording is off by default. An operator explicitly checks the box for fictional or approved data to request a kept training example. Mubit decides whether it actually keeps the call.
- A reviewer can record one correction per decision. The correction is **local only** until the team confirms the hackathon's feedback API contract and access. There is no inferred adapter version and no synthetic accuracy improvement.
- Model failures do not create decisions. Missing keys show an unavailable state.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes --only-binary=:all: -r requirements.lock
export MUBIT_API_KEY="your-key"
export CANOPY_OPERATOR_TOKEN="a-random-secret-of-at-least-32-characters"
python canopy.py
```

Open http://127.0.0.1:8080 and enter user `operator` with `CANOPY_OPERATOR_TOKEN` as the password. Use only fictional or approved test data. Generate a token with `python -c 'import secrets; print(secrets.token_urlsafe(48))'` and keep it out of source and screenshots. The database is `canopy.sqlite3` unless `CANOPY_DB_PATH` is set. The optional `MUBIT_MODEL` selects a provider model available to the key; the default is `gpt-4.1-mini`. A key alone does not prove model access, feedback access, or training.

`python canopy.py` validates the configuration and starts Gunicorn with one worker and eight threads. This keeps the in-memory form token and call-concurrency limit consistent within the instance. Use one app instance per SQLite database; multiple replicas require shared auth/session state, a different database, and a global rate limit.

The root `Procfile` is retained for a platform that supplies `PORT`: Canopy reads that port and binds to all interfaces, while still requiring a 32+ character operator token and an HTTPS `CANOPY_PUBLIC_ORIGIN`. Set a persistent `CANOPY_DB_PATH` and secret values or file paths in that platform; an ephemeral filesystem will lose reviews on restart. The Compose deployment remains the tested single-host path.

`requirements.txt` lists direct dependencies. `requirements.lock` pins and hashes all runtime dependencies for Python 3.11. Update it deliberately with `pip-compile --generate-hashes --output-file requirements.lock requirements.txt` using pip-tools 7.6.2, then rerun tests, the dependency audit, and the image build.

`CANOPY_POLICY_PATH` can point to an operator-reviewed JSON policy with a nonempty `version` and 1–30 rules, each with a unique `id` and `text`. The app validates the file at startup and records its hash and full rule snapshot on each new decision. Restart to load a new version. Keep approved policy source revisions outside the app as well, so the approval history can be audited. The bundled evaluation labels apply only to the exact bundled sample policy.

For a disposable local UI check without credentials, run `CANOPY_DEMO_MODE=1 python canopy.py`. Demo mode refuses a non-local public origin. Live checks stay unavailable without a Mubit key.

## Single-operator deployment

The Gunicorn service is designed to run behind a TLS reverse proxy. Basic credentials are safe only over HTTPS outside localhost. Set a 32+ character operator token, `MUBIT_API_KEY`, and `CANOPY_PUBLIC_ORIGIN=https://your-host`. The proxy must pass the original `Host` header and should bind the app's published port to loopback or a private network. Never expose the container's plain HTTP port directly to the internet. The app rejects non-local public origins without HTTPS and rejects non-local binding in demo mode.

For a single-host deployment, `deploy/compose.yaml` provides Caddy for public HTTPS and keeps Canopy on an internal network. Copy `deploy/env.example` to a private environment file outside the repository and set a real DNS name, the matching HTTPS public origin, an absolute path to an approved policy, and absolute paths to two secret files. Put the operator token and Mubit key in separate files within a host directory accessible only to the deployer (`0700`). The file mounts must be readable by the non-root container user; for Compose file secrets, read-only `0444` files inside that private host directory work. Do not put the secret contents in the environment file. The app reads them through `CANOPY_OPERATOR_TOKEN_FILE` and `MUBIT_API_KEY_FILE` and rejects a secret supplied both directly and by file. Start with `docker compose --env-file /private/path/canopy.env -f deploy/compose.yaml up -d --build`. DNS, inbound 80/443, persistent Docker volumes, backup storage, and certificate issuance must be verified on the actual host. CI exercises the same stack with synthetic secrets and a localhost certificate; that is separate from live deployment acceptance.

```bash
docker build -t canopy:local .
docker volume create canopy-data
docker run --rm -p 127.0.0.1:8080:8080 \
  --mount type=volume,src=canopy-data,dst=/data \
  -e CANOPY_PUBLIC_ORIGIN=https://your-host \
  -e CANOPY_OPERATOR_TOKEN="$CANOPY_OPERATOR_TOKEN" \
  -e MUBIT_API_KEY="$MUBIT_API_KEY" canopy:local
```

`/livez` reports process liveness; authenticated `/readyz` requires the key and writable database. The container runs as a non-root user. SQLite is suitable here for one operator and one app instance with a persistent volume. Multiple replicas, tenant accounts, role-based access, and encrypted customer data require a different deployment and data design.

Back up the SQLite database with `python manage.py backup --output /safe/location/canopy-backup.sqlite3`. The backup is a consistent snapshot with owner-only permissions from creation. The app rejects an existing decision database readable by other users; set its permissions to `0600` before restarting if needed. Each new case stores the policy rules used for its decision, so a later policy change does not alter review options. Legacy cases without a policy snapshot cannot be reviewed. `python manage.py purge --older-than-days 30` previews retention deletion; add `--apply` to perform it. `python manage.py delete-case --id N` likewise previews a case deletion. Schedule retention according to your approved data policy. Deleted data may remain in earlier backups; manage backup retention separately. Restore from a verified backup only while the app is stopped.

## Evaluation

`canopy_app/cases.py` has 40 distinct training examples and a separate 12-case holdout. Labels follow `canopy_app/sample_policy.json`, not a model self-assessment. Run only when the team wants to spend real model credits:

```bash
python evaluate.py --set holdout --stage baseline --output reports/baseline.json
python evaluate.py --set train --stage collection --output reports/train.json
```

The training run requests full recording for its synthetic cases; the holdout run requests recording off to avoid training leakage. The output records every prediction, label, request ID, and latency and reports call errors separately. **The script always calls the configured provider model through Mubit; a `--stage` label does not select or prove an adapter.** For an adapter comparison, use Mubit's *Compare with your provider* tool only after its adapter history shows a passing version. Record that result separately from this local benchmark. Public Mubit guidance says first training normally starts after 25 *kept* examples, training access must be enabled, and a passing version is not guaranteed.

## Demo evidence gate

1. Check one support reply live; show its Mubit request ID in Canopy and the corresponding call in Mubit Requests.
2. Correct an erroneous verdict in Canopy and show its local audit record.
3. Ask Mubit staff for the hackathon correction mechanism. Implement and verify their actual contract before claiming the correction reached Mubit. The old guessed `/outcomes` and `/feedback` calls were removed.
4. In Mubit Tasks and Adapters, show the kept-example count, training state, and actual adapter test outcome. A recorded call or local review is not proof of a model update.
5. Compare a passing adapter with the provider on unseen cases. Report observed outputs and failures. If training is pending or below target, say so.

Mubit references: [Connect with OpenAI](https://docs.mubit.ai/guides/connect-openai), [Create your first adapter](https://docs.mubit.ai/guides/first-adapter).

## Safety and limitations

The UI requires one operator credential, limits field and request sizes and concurrent model calls, checks origin and a per-process form token, escapes user content, and sends no Mubit key to the browser. SQLite stores case text in plaintext with owner-only file permissions; do not enter private customer records without an approved privacy and security design. Reviews cannot yet be transmitted to Mubit, and no real adapter update has been verified from this checkout.

Run checks with `python -m unittest -v`.
