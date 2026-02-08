from __future__ import annotations

import re
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.tools import search_products, create_lead


def is_buy_now(message: str) -> bool:
    """Only exact phrase starts checkout."""
    return (message or "").strip().lower() == "buy now"


def _extract_phone(text: str) -> str | None:
    """
    Basic phone extraction: accepts 07XXXXXXXX, +94XXXXXXXXX, with spaces/dashes.
    Returns cleaned string or None.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    cleaned = re.sub(r"[^\d+]", "", raw)          # keep digits and +
    digits = re.sub(r"\D", "", cleaned)           # digits only for validation

    if len(digits) < 9:
        return None

    # Simple Sri Lanka-friendly patterns:
    if cleaned.startswith("+"):
        return cleaned
    if digits.startswith("0") and len(digits) >= 10:
        return digits
    if len(digits) >= 9:
        return digits

    return None


def _looks_like_name(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 2:
        return False
    if _extract_phone(t):
        return False
    # avoid command-like strings
    bad = ["buy now", "buy", "purchase", "checkout", "order", "track", "ticket", "#"]
    if any(b in t.lower() for b in bad):
        return False
    return True


def _build_pick_list(matches: list[dict], limit: int = 6) -> str:
    lines = ["I found multiple products. Reply with the SKU you want:"]
    for p in matches[:limit]:
        lines.append(f"- {p.get('name','—')} [SKU: {p.get('sku','—')}]")
    return "\n".join(lines)


def handle(db: Session, message: str, history: list[dict] | None, memory: dict | None) -> str:
    """
    Purchase agent:
    - Start only when user says exactly "buy now"
    - Then collect product, name, phone
    - Create lead and return lead id
    """
    history = history or []
    memory = memory or {}

    msg = (message or "").strip()
    lower = msg.lower()

    # Memory flow object
    flow = memory.get("buy_flow") or {}
    if not isinstance(flow, dict):
        flow = {}

    active = bool(flow.get("active", False))

    # 1) Start gate: only "buy now" can START the flow
    if not active:
        if not is_buy_now(msg):
            return 'To start a purchase, type exactly: "buy now".'
        # Activate and ask for product first
        flow = {"active": True, "step": "product"}
        memory["buy_flow"] = flow
        return "Sure. What product model or SKU do you want to buy? (Example: iPhone 15 Pro 256GB or SKU: PHN-...)"

    # 2) If flow is active, proceed step-by-step
    step = flow.get("step", "product")

    # Step: product
    if step == "product":
        # If user repeats "buy now", just ask for product again
        if is_buy_now(msg):
            return "What product model or SKU do you want to buy?"

        matches = search_products(db, msg, in_stock_only=False)

        if not matches:
            return "I couldn’t find that product. Please reply with the exact model name or SKU."

        if len(matches) > 1:
            return _build_pick_list(matches)

        chosen = matches[0]
        flow["product_name"] = chosen.get("name") or msg
        flow["product_sku"] = chosen.get("sku")
        flow["step"] = "name"
        memory["buy_flow"] = flow

        return f"Great. Buying: {flow['product_name']}\nWhat’s your name?"

    # Step: name
    if step == "name":
        if not _looks_like_name(msg):
            return "Please reply with your name (only your name)."

        flow["name"] = msg
        flow["step"] = "phone"
        memory["buy_flow"] = flow
        return "Thanks. What’s your phone number?"

    # Step: phone
    if step == "phone":
        phone = _extract_phone(msg)
        if not phone:
            return "Please reply with a valid phone number (e.g., 07XXXXXXXX or +94XXXXXXXXX)."

        flow["phone"] = phone

        # 3) Create lead only now
        lead = create_lead(
            db=db,
            name=flow["name"],
            phone=flow["phone"],
            product_model=flow.get("product_name"),
            product_sku=flow.get("product_sku"),
        )

        lead_id = lead.get("lead_id") or lead.get("id")

        # Save last lead in memory for later questions
        memory["last_lead_id"] = lead_id
        memory["last_lead_product"] = flow.get("product_name")

        # Reset flow
        memory["buy_flow"] = {"active": False}

        return (
            "Done! Lead created.\n"
            f"Lead ID: {lead_id}\n"
            f"Product: {flow.get('product_name')}\n"
            f"Name: {flow.get('name')}\n"
            f"Phone: {flow.get('phone')}"
        )

    # Safety fallback
    memory["buy_flow"] = {"active": False}
    return 'Something went wrong with the buy flow. Type "buy now" to start again.'
