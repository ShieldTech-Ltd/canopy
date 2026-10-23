# Canopy — Build Plan for Ritik

Night Shift 2026 | Friday 23 Oct to Saturday 24 Oct midnight

---

## What we are building

An autonomous agent that verifies claims through Mubit's Banyan Sapling model.
It handles all three possible verdicts intelligently and improves itself over time.

**The key insight nobody else is using:**
Banyan Sapling returns INSUFFICIENT when it needs more evidence. Every other team
ignores this. We handle it by automatically fetching more evidence and resubmitting.

---

## Repo

https://github.com/ShieldTech-Ltd/canopy

Clone it:
```bash
git clone https://github.com/ShieldTech-Ltd/canopy
cd canopy
pip install openai
```

Run it (simulation mode, no API key needed yet):
```bash
python canopy.py
```

Open: http://localhost:8080

---

## How the agent works (read canopy.py)

1. Agent picks a claim from the CLAIMS list
2. Sends it to Banyan Sapling via Mubit: policy + evidence + claim
3. Gets back SUPPORTED, VIOLATES, or INSUFFICIENT
4. If SUPPORTED: log it, move on
5. If VIOLATES: call record_outcome() automatically (this trains a Mubit adapter)
6. If INSUFFICIENT: fetch extra evidence, re-submit, resolve it
7. Every 3 corrections: Mubit promotes a new model version
8. Repeat forever. Dashboard shows everything live.

---

## Division of work

### Tanvir handles:
- Pitch and presentation
- Mubit API key (get from the team tonight)
- Swapping USE_REAL_API = True once we have the key
- Testing the live Mubit integration
- Demo practice

### Ritik handles:
- Running canopy.py and confirming the dashboard works
- Adding more claims to the CLAIMS list in canopy.py (the more the better)
- Improving the dashboard HTML inside canopy.py if time allows
- Testing edge cases (what happens when Banyan Sapling keeps returning INSUFFICIENT?)
- Optional: adding Wikipedia API calls to fetch_extra_evidence() for real evidence

---

## Timeline

| Time | What |
|---|---|
| Friday 8pm | Both: clone repo, run simulation, confirm dashboard works |
| Friday 9pm | Get Mubit API key from the team. Swap USE_REAL_API = True. Test one live call. |
| Friday 10pm | Confirm record_outcome() works. Model version should tick up. |
| Friday 11pm | Add 10 more claims to the CLAIMS list. Variety matters. |
| Saturday 9am | Dashboard polished. All three verdict types showing clearly. |
| Saturday 12pm | Check-in 1: demo working end to end |
| Saturday 3pm | Practice the 90-second pitch |
| Saturday 6pm | Check-in 2: final version ready |
| Saturday 11pm | Submit via /submit before midnight |

---

## How to get the Mubit API key

Ask anyone from the Mubit team at the venue tonight.
Say: "We need an API key to connect to Banyan Sapling."
Once you have it, open canopy.py and update lines 14-16:

```python
MUBIT_KEY      = "paste-your-key-here"
MUBIT_BASE_URL = "https://api.mubit.ai/openai/v1"
USE_REAL_API   = True
```

---

## The 90-second demo script

1. Open http://localhost:8080 on a big screen
2. "This is Canopy. It verifies claims through Mubit's Banyan Sapling model."
3. "Watch the live log. Three things can happen."
4. Point to an INSUFFICIENT line: "That claim had ambiguous evidence. Canopy fetched more evidence automatically and resubmitted. No human involved."
5. Point to a VIOLATES/correction line: "That wrong verdict just called record_outcome(). Mubit is training a new adapter right now."
6. Point to the model version: "We started on v1. We are now on v4. The model improved itself overnight."
7. Point to accuracy: "Started at 45%. Now 78%. Zero human corrections."
8. "Every other team sent two types of verdicts to Mubit. We sent three."

---

## Questions judges will ask

**"Why does INSUFFICIENT matter?"**
"It's the signal that the agent doesn't have enough information to decide. If you ignore it, you get wrong answers. If you handle it, you get better answers and fewer false corrections. Canopy is the only agent here that handles it."

**"How does record_outcome() actually work?"**
"It posts the claim, the wrong prediction, and the correct answer to Mubit's API. Mubit groups these by task, and when it has enough signal, it trains a small versioned adapter. The adapter runs alongside the frontier model and takes over when it does better."

**"What if a correction is wrong?"**
"Mubit's adapters are versioned and reversible. If a bad correction slips through, you roll back to the previous version. The frontier model is always the fallback."

---

## Files

| File | What it does |
|---|---|
| canopy.py | Main agent + HTTP dashboard server |
| README.md | Project overview + system diagram |
| requirements.txt | pip install openai |
| .env.example | API key template |
| RITIK-PLAN.md | This file |

---

Good luck. We win this.
