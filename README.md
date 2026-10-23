# Canopy

**Mubit intelligence layer that handles all three Banyan Sapling responses autonomously.**

Built at Night Shift 2026 — Mubit Hackathon, Canary Wharf, London.

---

## The one-line pitch

> Banyan Sapling gives you three verdicts. Everyone uses two. Canopy uses all three.

---

## The problem Canopy solves

Banyan Sapling returns SUPPORTED, VIOLATES, or INSUFFICIENT.

Most agents treat INSUFFICIENT as an error and stop. Canopy treats it as a signal: the model needs more evidence before it can decide. So Canopy goes and gets that evidence automatically, then resubmits. No human. No loop. No wasted turn.

Every VIOLATES verdict fires `record_outcome()` immediately. Mubit trains a new adapter. The model gets smarter on the next run. Accuracy climbs by itself.

---

## Why this benefits Mubit

Mubit's docs say: "Your application verifies outcomes. An agent saying it succeeded is not enough."

Canopy is that verification layer. It closes the loop Mubit needs closed:

```
Banyan Sapling verdict
        |
   SUPPORTED ──────────────────► Log it. Move on.
        |
   VIOLATES  ──────────────────► record_outcome() fires instantly.
        |                         Mubit trains adapter. Version ticks up.
   INSUFFICIENT ────────────────► Fetch more evidence automatically.
                                  Re-submit to Banyan Sapling.
                                  Resolve to SUPPORTED or VIOLATES.
                                  If VIOLATES: record_outcome() fires.
```

Nobody else at this hackathon is using INSUFFICIENT. That is the gap.

---

## System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CANOPY AGENT                            │
│                                                                 │
│  ┌──────────┐    ┌───────────────────┐    ┌──────────────────┐  │
│  │  Claims  │───►│  Banyan Sapling   │───►│  SUPPORTED       │  │
│  │  pool    │    │  via Mubit proxy  │    │  Log + continue  │  │
│  └──────────┘    └───────────────────┘    └──────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│                    ┌─────────────┐                              │
│                    │  VIOLATES   │                              │
│                    │             │                              │
│                    │ record_     │                              │
│                    │ outcome()   │──► Mubit trains adapter      │
│                    │             │    Model v++ promoted        │
│                    └─────────────┘                              │
│                           │                                     │
│                           ▼                                     │
│                    ┌──────────────────────────────────────┐     │
│                    │  INSUFFICIENT                        │     │
│                    │                                      │     │
│                    │  1. Fetch extra evidence             │     │
│                    │     (Wikipedia / RSS / Wikidata)     │     │
│                    │  2. Re-submit to Banyan Sapling      │     │
│                    │  3. Resolve to final verdict         │     │
│                    │  4. If VIOLATES: record_outcome()    │     │
│                    └──────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │   Live Dashboard :8080       │
               │                              │
               │  Accuracy %   Model version  │
               │  Corrections  INSUFF caught  │
               │  Live log     Decision table │
               └──────────────────────────────┘
```

---

## How to run

### 1. Install dependencies

```bash
pip install openai
```

### 2. Set your Mubit API key

Open `canopy.py` and update:

```python
MUBIT_KEY    = "your-mubit-api-key"
USE_REAL_API = True
```

### 3. Run the agent

```bash
python canopy.py
```

### 4. Open the dashboard

```
http://localhost:8080
```

The dashboard auto-refreshes every 2 seconds. Watch accuracy climb and model version tick up in real time.

---

## How Mubit integration works

One line change from any OpenAI-compatible client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.mubit.ai/openai/v1",   # was: https://api.openai.com/v1
    api_key="YOUR_MUBIT_KEY",
)

# Everything else identical
resp = client.chat.completions.create(
    model="banyan-sapling",
    messages=[...],
)
```

---

## record_outcome() — how corrections train the model

```python
# Called automatically every time the verdict is wrong
POST https://api.mubit.ai/openai/v1/outcomes
{
    "model":          "banyan-sapling",
    "input":          "Policy: ...\nEvidence: ...\nClaim: ...",
    "predicted":      "VIOLATES",
    "correct_output": "SUPPORTED"
}
```

Every 3 corrections, Mubit promotes a new versioned adapter. The frontier model stays untouched. The adapter sits on top.

---

## Track alignment

| Hackathon track | How Canopy fits |
|---|---|
| Recurring tasks | Claim verification runs every 1.4 seconds, same task type, same correction loop |
| Own your intelligence layer | Banyan Sapling (open, task-adapted) replaces a closed frontier model for this task |
| Fast refresh | New claims feed in continuously; model adapts to new failure patterns automatically |

All three tracks. One project.

---

## Team

Built by Tanvir + Ritik at Night Shift 2026, Canary Wharf London.

Powered by Mubit and Banyan Sapling.
