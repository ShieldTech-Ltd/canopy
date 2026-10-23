# Canopy

> Autonomous claim verification powered by Mubit and Banyan Sapling.
> The intelligence layer that handles all three verdicts — not just two.

Built at **Night Shift 2026**, Mubit Hackathon — Canary Wharf, London.

---

## What is Canopy?

Canopy is a self-improving claim verification agent that routes every decision through
Mubit's Banyan Sapling model. It runs continuously, verifies claims against evidence,
and corrects itself automatically when it gets something wrong.

No human corrects it. No human restarts it. It just gets better.

---

## The problem

Banyan Sapling returns three possible verdicts:

| Verdict | Meaning |
|---|---|
| `SUPPORTED` | The claim is backed by the evidence |
| `VIOLATES` | The claim contradicts the evidence |
| `INSUFFICIENT` | There is not enough evidence to decide |

Most agents treat `INSUFFICIENT` as a failure and stop. That is the wrong approach.
`INSUFFICIENT` is a signal, not an error. It means the model needs more context before
it can make a confident decision.

**Canopy is the first agent to handle all three verdicts correctly.**

---

## How it works

```
                        ┌─────────────────────────────────┐
                        │          CANOPY AGENT           │
                        │                                 │
  ┌─────────────┐       │   ┌─────────────────────────┐   │
  │   Claim     │──────►│   │     Banyan Sapling       │   │
  │   Evidence  │       │   │     via Mubit proxy      │   │
  │   Policy    │       │   └────────────┬────────────┘   │
  └─────────────┘       │                │                │
                        │      ┌─────────┴──────────┐     │
                        │      │                    │     │
                        │  SUPPORTED            VIOLATES  │
                        │      │                    │     │
                        │  Log it.          record_outcome│
                        │  Move on.         fires auto.   │
                        │                    │            │
                        │             Mubit trains        │
                        │             adapter. v++ up.    │
                        │                                 │
                        │         INSUFFICIENT            │
                        │              │                  │
                        │   1. Fetch extra evidence       │
                        │      (Wikipedia / Wikidata)     │
                        │   2. Re-submit to Banyan        │
                        │   3. Resolve to final verdict   │
                        │   4. If VIOLATES: correct it    │
                        └─────────────────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────┐
                        │    Live Dashboard  :8080        │
                        │                                 │
                        │  Accuracy %     Model version   │
                        │  Corrections    INSUFF resolved │
                        │  Live log       Decision table  │
                        └─────────────────────────────────┘
```

---

## Why this matters for Mubit

Mubit's own documentation states:

> "Your application verifies outcomes. An agent saying it succeeded is not enough."

Canopy is that verification layer. It closes the exact loop Mubit was designed to close:

- Every wrong verdict triggers `record_outcome()` with no human involved
- Every `INSUFFICIENT` case becomes a richer training signal after evidence gathering
- Every 3 corrections, Mubit promotes a new versioned adapter
- The frontier model stays untouched — the adapter sits on top and takes over only when it does better

By demo time, the model running is measurably better than the one that started. That proof
lives in the accuracy chart and the model version counter, updating live on screen.

---

## Mubit integration

Canopy connects to Mubit with a single line change:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.mubit.ai/openai/v1",  # was: https://api.openai.com/v1
    api_key=MUBIT_API_KEY,
)

response = client.chat.completions.create(
    model="banyan-sapling",
    messages=[
        {
            "role": "system",
            "content": (
                "Verify the claim against the policy and evidence. "
                "Reply with exactly one word: SUPPORTED, VIOLATES, or INSUFFICIENT."
            ),
        },
        {
            "role": "user",
            "content": f"Policy: {policy}\nEvidence: {evidence}\nClaim: {claim}",
        },
    ],
)
```

Everything else in the application stays identical. No rewrite. No new framework.

---

## How record_outcome() trains the model

When Canopy detects a wrong verdict, it immediately sends a correction to Mubit:

```python
POST https://api.mubit.ai/openai/v1/outcomes

{
    "model":          "banyan-sapling",
    "input":          "Policy: ...\nEvidence: ...\nClaim: ...",
    "predicted":      "VIOLATES",
    "correct_output": "SUPPORTED"
}
```

Mubit groups corrections by task, builds a versioned adapter, and promotes it once it
outperforms the base model. The adapter is reversible — if accuracy drops, you roll back
to the previous version instantly.

---

## INSUFFICIENT handling — the core innovation

When Banyan Sapling returns `INSUFFICIENT`, Canopy does not stop. It:

1. Queries Wikipedia's REST API using the claim as a search term
2. Extracts the most relevant passage (up to 300 characters)
3. Appends it to the original evidence
4. Re-submits the enriched claim to Banyan Sapling
5. Records the resolved verdict

This turns ambiguous cases into resolved training signal instead of wasted calls.
Over time, the adapter learns which claim types need richer context from the start,
reducing `INSUFFICIENT` responses on future runs.

---

## Running Canopy

### Prerequisites

```bash
pip install openai
```

### Configuration

Open `canopy.py` and set your Mubit API key:

```python
MUBIT_KEY      = "your-mubit-api-key"
USE_REAL_API   = True
```

In simulation mode (`USE_REAL_API = False`), the agent runs without any API key
using a built-in model simulator. Accuracy and model version still climb to demonstrate
the full loop.

### Start the agent

```bash
python canopy.py
```

### Open the dashboard

```
http://localhost:8080
```

The dashboard auto-refreshes every 2 seconds. No page reload needed.

---

## Dashboard overview

| Metric | What it shows |
|---|---|
| Accuracy % | Percentage of correct verdicts since start |
| Decisions | Total claims processed |
| Corrections sent | Times record_outcome() fired automatically |
| INSUFFICIENT caught | Times Banyan Sapling needed more evidence |
| Resolved with evidence | INSUFFICIENT cases that Canopy resolved autonomously |
| Model version | Current adapter version promoted by Mubit |

The live log shows every decision, every correction, every evidence fetch, and every
model promotion in real time.

---

## Hackathon track alignment

| Track | How Canopy fits |
|---|---|
| **Recurring tasks** | Claim verification runs continuously on the same task type, with corrections becoming model updates |
| **Own your intelligence layer** | Banyan Sapling (open, task-adapted via Mubit) replaces a closed frontier model for this specific task |
| **Fast refresh** | New claims feed in continuously and the adapter updates as failure patterns change |

Canopy is the only submission that addresses all three tracks simultaneously.

---

## Project structure

```
canopy/
├── canopy.py        Main agent and HTTP dashboard server
├── README.md        This file
├── RITIK-PLAN.md    Build plan and task division for the team
├── requirements.txt pip install openai
├── .env.example     API key template
└── .gitignore
```

---

## Team

**Tanvir** and **Ritik** — Night Shift 2026, Canary Wharf, London.

Powered by [Mubit](https://mubit.ai) and Banyan Sapling.
