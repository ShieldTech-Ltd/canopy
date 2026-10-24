"""Fixed, distinct demo cases. Labels follow sample_policy.json, not model output."""

SAMPLE_POLICY_HASH = "6d21c4d579ac8f385d64e0d439c3123d68b14d384455bb1ed99ea0258f15bfa6"

TRAIN = []
for days in (1, 3, 5, 8, 11, 14, 16, 18, 21, 28):
    for used in (False, True):
        facts = f"Purchase was {days} calendar days ago. Paid-feature usage: {'yes' if used else 'none'}."
        eligible = days <= 14 and not used
        TRAIN.append({
            "facts": facts,
            "reply": "You qualify for a standard refund." if eligible else "You do not qualify for a standard refund.",
            "truth": "SUPPORTED",
            "rule": "R1" if eligible else ("R2" if used else "R3"),
        })
        TRAIN.append({
            "facts": facts,
            "reply": "You do not qualify for a standard refund." if eligible else "You qualify for a standard refund.",
            "truth": "VIOLATES",
            "rule": "R1" if eligible else ("R2" if used else "R3"),
        })

HOLDOUT = [
    {"facts": "Purchase was 2 days ago. No paid features used.",
     "reply": "You qualify for a standard refund.", "truth": "SUPPORTED", "rule": "R1"},
    {"facts": "Purchase was 13 days ago. No paid features used.",
     "reply": "You cannot receive a standard refund.", "truth": "VIOLATES", "rule": "R1"},
    {"facts": "Purchase was 15 days ago. No paid features used.",
     "reply": "You qualify for a standard refund.", "truth": "VIOLATES", "rule": "R3"},
    {"facts": "Purchase was 30 days ago. Paid feature used once.",
     "reply": "You do not qualify for a standard refund.", "truth": "SUPPORTED", "rule": "R2"},
    {"facts": "Purchase was 7 days ago. Paid feature used once.",
     "reply": "You qualify for a standard refund.", "truth": "VIOLATES", "rule": "R2"},
    {"facts": "Purchase was 10 days ago. No paid features used.",
     "reply": "You do not qualify for a standard refund.", "truth": "VIOLATES", "rule": "R1"},
    {"facts": "Purchase age unknown. No paid features used.",
     "reply": "You qualify for a standard refund.", "truth": "INSUFFICIENT", "rule": "R5"},
    {"facts": "Purchase was 6 days ago. Paid-feature usage unknown.",
     "reply": "You qualify for a standard refund.", "truth": "INSUFFICIENT", "rule": "R5"},
    {"facts": "Purchase age and usage are unknown.",
     "reply": "Please tell us the purchase date and whether you used paid features.",
     "truth": "SUPPORTED", "rule": "R5"},
    {"facts": "A duplicate charge is confirmed. Purchase was 90 days ago.",
     "reply": "We can correct the duplicate charge.", "truth": "SUPPORTED", "rule": "R4"},
    {"facts": "A duplicate charge is confirmed. Paid features were used.",
     "reply": "We cannot correct the duplicate charge because features were used.",
     "truth": "VIOLATES", "rule": "R4"},
    {"facts": "Purchase was 14 days ago. No paid features used.",
     "reply": "You qualify for a standard refund.", "truth": "SUPPORTED", "rule": "R1"},
]
