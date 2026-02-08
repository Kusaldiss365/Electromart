from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from app.agents.router import route_intent

LABELS = ["sales", "marketing", "support", "orders"]
CASES_PATH = Path(__file__).resolve().parents[1] / "tests" / "router_intent_cases.jsonl"


def main():
    cases = []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            cases.append(json.loads(line))

    correct = 0
    total = 0
    confusion = defaultdict(Counter)

    for c in cases:
        pred = route_intent(c["text"], c.get("history") or [], c.get("memory") or {})
        expected = c["expected"]
        confusion[expected][pred] += 1
        total += 1
        correct += int(pred == expected)

    acc = correct / total if total else 0.0
    print(f"Cases: {total}")
    print(f"Accuracy: {acc:.2%}")

    print("\nConfusion matrix:")
    print("expected\\pred".ljust(14) + "".join(l.ljust(12) for l in LABELS))
    for e in LABELS:
        row = e.ljust(14)
        for p in LABELS:
            row += str(confusion[e][p]).ljust(12)
        print(row)


if __name__ == "__main__":
    main()
