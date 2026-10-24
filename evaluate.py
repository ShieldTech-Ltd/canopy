"""Run fixed cases via Mubit. Never treats a local label as a model update."""

import argparse
import json
import sys
from datetime import datetime, timezone

from canopy import KEY, MODEL, POLICY, predict
from cases import HOLDOUT, TRAIN


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=("train", "holdout"), required=True)
    parser.add_argument("--output", required=True, help="Local JSON result path")
    parser.add_argument("--stage", required=True, help="Run label, e.g. baseline; this never selects an adapter")
    args = parser.parse_args()
    if not KEY:
        parser.error("MUBIT_API_KEY is required; no simulation is available")
    cases = TRAIN if args.set == "train" else HOLDOUT
    results = []
    for index, case in enumerate(cases, 1):
        try:
            verdict, request_id, latency = predict(case["facts"], case["reply"])
            results.append({**case, "prediction": verdict, "correct": verdict == case["truth"],
                            "request_id": request_id, "latency_ms": latency})
            print(f"{index}/{len(cases)} {verdict} / {case['truth']}", flush=True)
        except Exception as exc:
            results.append({**case, "prediction": None, "correct": None,
                            "error_type": type(exc).__name__})
            print(f"{index}/{len(cases)} ERROR {type(exc).__name__}", file=sys.stderr, flush=True)
    report = {
        "stage": args.stage, "set": args.set, "route": "Mubit OpenAI proxy; adapter selection not asserted",
        "policy_version": POLICY["version"],
        "provider_model": MODEL, "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(cases), "correct": sum(r["correct"] is True for r in results),
        "errors": sum(r["correct"] is None for r in results), "cases": results,
    }
    from pathlib import Path
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved {target}: {report['correct']}/{len(cases)} correct; {report['errors']} call errors")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
