from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

# IMPORTANT:
# Adjust this import path if your router file path differs.
from app.agents.router import route_intent

CASES_PATH = Path(__file__).parent / "router_intent_cases.jsonl"

LABELS = ["sales", "marketing", "support", "orders"]


def load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def test_router_intent_accuracy_min_85(monkeypatch):
    """
    We force deterministic routing by disabling LLM fallback (OPENAI_API_KEY empty).
    This ensures you're testing the rule-based router behavior.
    """
    # Disable LLM fallback for stable tests
    from app.core import config
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "", raising=False)

    cases = list(load_cases())
    assert len(cases) >= 20, "Add more cases (aim 100–300) before trusting the score."

    correct = 0
    total = 0
    confusion = defaultdict(Counter)

    for c in cases:
        text = c["text"]
        expected = c["expected"]
        memory = c.get("memory") or {}
        history = c.get("history") or []

        pred = route_intent(text, history, memory)

        assert pred in LABELS, f"Router returned unknown label: {pred!r}"
        confusion[expected][pred] += 1
        total += 1
        if pred == expected:
            correct += 1

    acc = correct / total if total else 0.0

    # Print confusion matrix in test logs for quick debugging
    header = "expected\\pred".ljust(14) + "".join(l.ljust(12) for l in LABELS)
    lines = [header]
    for e in LABELS:
        row = e.ljust(14)
        for p in LABELS:
            row += str(confusion[e][p]).ljust(12)
        lines.append(row)

    print("\nRouter intent accuracy:", acc)
    print("\n".join(lines))

    assert acc >= 0.85, f"Router accuracy {acc:.2%} < 85%. Tune keywords/rules or add LLM fallback tests."


def test_sticky_orders_flow_bare_id_continues(monkeypatch):
    """
    If active_flow is orders, and user replies with a bare ID like '101',
    router must keep orders.
    """
    from app.core import config
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "", raising=False)

    memory = {"active_flow": "orders"}
    pred = route_intent("101", history=[], memory=memory)
    assert pred == "orders"
    assert memory.get("active_flow") == "orders"


def test_return_pending_forces_orders(monkeypatch):
    """
    If return_pending is set, always route to orders.
    """
    from app.core import config
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "", raising=False)

    memory = {"return_pending": True}
    pred = route_intent("i want to return", history=[], memory=memory)
    assert pred == "orders"
    assert memory.get("active_flow") == "orders"


def test_orders_flow_explicit_switch_support(monkeypatch):
    """
    If in orders flow, explicit support keywords should switch to support.
    """
    from app.core import config
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "", raising=False)

    memory = {"active_flow": "orders"}
    pred = route_intent("my device is broken", history=[], memory=memory)
    assert pred == "support"
    assert memory.get("active_flow") == "support"


def test_sales_flow_order_id_switches_to_orders(monkeypatch):
    """
    If in sales flow and user provides order id / tracking, switch to orders.
    """
    from app.core import config
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "", raising=False)

    memory = {"active_flow": "sales"}
    pred = route_intent("order id 12345 status", history=[], memory=memory)
    assert pred == "orders"
    assert memory.get("active_flow") == "orders"
