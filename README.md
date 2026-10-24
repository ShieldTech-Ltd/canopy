# Canopy

Canopy checks drafted support replies against a small, versioned refund policy. A reviewer can correct a verdict and record the rule and reason. It is a focused **Recurring tasks** MVP for Night Shift 2026.

The policy and cases in this repository are fictional demo material. The app has no customer integration and runs only on localhost.

## What is real today

- Every live model check uses the OpenAI client with the Mubit base URL. The Mubit key stays on the server and comes from `MUBIT_API_KEY`.
- A successful check stores the verdict, policy version, latency, and Mubit request ID in local SQLite.
- A reviewer can record one correction per decision. The correction is **local only** until the team confirms the hackathon's feedback API contract and access. There is no inferred adapter version and no synthetic accuracy improvement.
- Model failures do not create decisions. Missing keys show an unavailable state.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MUBIT_API_KEY="your-key"
python canopy.py
```

Open http://127.0.0.1:8080. Use only fictional or approved test data. The database is `canopy.sqlite3` unless `CANOPY_DB_PATH` is set. The optional `MUBIT_MODEL` selects a provider model available to the key; the default is `gpt-4.1-mini`. A key alone does not prove model access, feedback access, or training.

For a local UI check without a key, run `python canopy.py`; the page opens but live model checks remain unavailable.

## Evaluation

`cases.py` has 40 distinct training examples and a separate 12-case holdout. Labels follow `sample_policy.json`, not a model self-assessment. Run only when the team wants to spend real model credits:

```bash
python evaluate.py --set holdout --stage baseline --output reports/baseline.json
python evaluate.py --set train --stage collection --output reports/train.json
```

The output records every prediction, label, request ID, and latency. It reports call errors separately. **The script always calls the configured provider model through Mubit; a `--stage` label does not select or prove an adapter.** For an adapter comparison, use Mubit's *Compare with your provider* tool only after its adapter history shows a passing version. Record that result separately from this local benchmark. Public Mubit guidance says first training normally starts after 25 *kept* examples, training access must be enabled, and a passing version is not guaranteed.

## Demo evidence gate

1. Check one support reply live; show its Mubit request ID in Canopy and the corresponding call in Mubit Requests.
2. Correct an erroneous verdict in Canopy and show its local audit record.
3. Ask Mubit staff for the hackathon correction mechanism. Implement and verify their actual contract before claiming the correction reached Mubit. The old guessed `/outcomes` and `/feedback` calls were removed.
4. In Mubit Tasks and Adapters, show the kept-example count, training state, and actual adapter test outcome. A recorded call or local review is not proof of a model update.
5. Compare a passing adapter with the provider on unseen cases. Report observed outputs and failures. If training is pending or below target, say so.

Mubit references: [Connect with OpenAI](https://docs.mubit.ai/guides/connect-openai), [Create your first adapter](https://docs.mubit.ai/guides/first-adapter).

## Safety and limitations

The UI is local-only, limits field and request sizes, checks origin and a per-process form token, escapes user content, and sends no key to the browser. SQLite stores case text in plaintext on the local machine; do not enter private customer records. Reviews cannot yet be transmitted to Mubit, and no real adapter update has been verified from this checkout.

Run checks with `python -m unittest -v`.
