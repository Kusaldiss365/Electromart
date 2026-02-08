from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.faq_rag import search_faq
from app.services.llm import get_client
from app.services.tools import (
    get_order_status,
    extract_order_id,
    create_return_request,
    extract_return_request_id,
    get_return_request,
)

SYSTEM = """You are the Orders & Logistics Agent for ElectroMart.
Handle tracking/shipping/delivery/returns/refunds/cancel/exchange for EXISTING orders.
Use order info and FAQ policy context.

Return flow (STRICT):
- Do NOT create a return until you have BOTH: order_id and a clear reason.
- If user asks to return but provides no reason, ask for the reason (one question).
- If memory.return_pending is true, treat the next user message as the reason ONLY if it is a real reason.

Return request lookup:
- If user asks about a return request number (e.g., "return request 1", "request 1", "rr 1"), fetch and summarize it.

Rules (STRICT):
- Reply fully in ONE message.
- Never say “please hold”, “I’ll check”, or imply future replies.
- Keep it concise and practical.
- Always mention prices in LKR (Sri Lankan Rupees)

Ambiguity handling (important):
- If the user request is unclear or missing required order identifiers (such as order_id, phone number, or request number),
  do NOT assume or guess.
- Ask ONE short clarifying question to obtain the missing information.
- When helpful, provide 2–3 examples of what the user can reply with (e.g., order ID or request number).
- Do not ask unrelated questions or multiple questions at once.

"""


# Reason keywords (strict): ONLY these (or "because ...") count as a return reason
REASON_HINTS = [
    "defect", "defective", "broken", "crack", "cracked", "damaged", "not working",
    "wrong item", "wrong product", "late", "delay", "changed my mind", "no longer need",
    "faulty", "missing", "incomplete", "problem", "issue",
    "screen", "battery", "overheat", "overheating"
]

def _has_return_reason(text: str) -> bool:
    t = (text or "").lower().strip()
    if not t:
        return False
    if "because" in t:
        return True
    return any(h in t for h in REASON_HINTS)


def _format_item_line(prod: dict | None) -> str:
    prod = prod or {}
    name = prod.get("name") or "Item details not available"
    price = prod.get("price")
    if price is not None and name != "Item details not available":
        return f"{name} (LKR {price})"
    return name


def handle(db: Session, message: str, history: list[dict], memory: dict) -> str:
    memory = memory or {}
    history = history or []
    message = message or ""
    lower = message.lower()

    # -------------------------
    # 0) Return-request lookup (e.g., "tell me about request 1")
    # -------------------------
    rr_id = extract_return_request_id(message)
    if rr_id:
        rr_info = get_return_request(db, rr_id)
        if not rr_info.get("found"):
            return f"I couldn’t find return request **#{rr_id}**."

        order = rr_info.get("order") or {}
        prod = rr_info.get("product") or {}
        item_line = _format_item_line(prod)

        # persist for followups ("tell me about it")
        memory["last_return_request_id"] = rr_info["return_request_id"]
        memory["active_flow"] = "orders"

        return (
            f"Return request **#{rr_info['return_request_id']}** — **{rr_info['status']}**.\n"
            f"Order: **{order.get('order_id', rr_info.get('order_id'))}**\n"
            f"Item: **{item_line}**\n"
            f"Reason: {rr_info.get('reason')}"
        )

    # Follow-up like "tell me about it"
    if any(k in lower for k in ["tell me about it", "return details", "show details", "details of the return"]) and memory.get("last_return_request_id"):
        rr_info = get_return_request(db, int(memory["last_return_request_id"]))
        if rr_info.get("found"):
            order = rr_info.get("order") or {}
            prod = rr_info.get("product") or {}
            item_line = _format_item_line(prod)
            memory["active_flow"] = "orders"
            return (
                f"Return request **#{rr_info['return_request_id']}** — **{rr_info['status']}**.\n"
                f"Order: **{order.get('order_id', rr_info.get('order_id'))}**\n"
                f"Item: **{item_line}**\n"
                f"Reason: {rr_info.get('reason')}"
            )

    # -------------------------
    # 1) Order id extraction + persist
    # -------------------------
    oid = extract_order_id(message) or memory.get("last_order_id")
    if oid:
        memory["last_order_id"] = oid
        memory["active_flow"] = "orders"

    # -------------------------
    # 2) Return flow gating
    # -------------------------
    wants_return = any(w in lower for w in ["return", "refund", "cancel", "exchange"])

    # If user asks to return but provides no reason → ask for reason and set pending
    if wants_return and not _has_return_reason(message):
        memory["return_pending"] = True
        memory["active_flow"] = "orders"
        if oid:
            memory["last_order_id"] = oid
        if oid:
            return f"Please provide a reason for returning order **{oid}** (e.g., damaged, wrong item, not working, changed mind)."
        return "Please provide your order ID and the reason for the return (e.g., Order 101 — damaged)."

    # If we were waiting for a reason:
    if memory.get("return_pending") and not wants_return:
        # Guard: user just sent order id / short text, not a reason
        maybe_oid = extract_order_id(message)
        if maybe_oid and len(message.split()) <= 3:
            memory["last_order_id"] = maybe_oid
            memory["active_flow"] = "orders"
            return "Got it — what’s the reason for the return? (e.g., damaged, wrong item, not working, changed mind)"

        # If still not a real reason, ask again
        if not _has_return_reason(message):
            memory["active_flow"] = "orders"
            return "What’s the reason for the return? (e.g., damaged, wrong item, not working, changed mind)"

        # Create return now
        reason = (message.strip() or "Customer requested return")[:200]
        oid2 = extract_order_id(message) or memory.get("last_order_id")
        if not oid2:
            return "Please provide your order ID to proceed with the return."

        rr = create_return_request(db, oid2, reason, message)
        memory["return_pending"] = False
        memory["last_return_request_id"] = rr["return_request_id"]
        memory["active_flow"] = "orders"

        if rr.get("already_exists"):
            return f"You already have a return request: **#{rr['return_request_id']}** (status: {rr['status']})."
        return f"Return request created: **#{rr['return_request_id']}** (status: {rr['status']})."

    # -------------------------
    # 3) Fetch order + FAQs
    # -------------------------
    order_info = get_order_status(db, message, oid)
    if order_info.get("found"):
        memory["last_order_id"] = order_info["order_id"]
        memory["active_flow"] = "orders"

    faqs = search_faq(db, message, k=4)

    # -------------------------
    # 4) Non-LLM path
    # -------------------------
    if not settings.OPENAI_API_KEY:
        if order_info.get("need_order_id"):
            return "Please share your order number (e.g., Order 101)."

        if not order_info.get("found"):
            return f"I couldn’t find order {order_info.get('order_id')}. Please double-check the number."

        # Create return ONLY if reason exists in message
        if wants_return and _has_return_reason(message):
            rr = create_return_request(db, order_info["order_id"], message[:200], message)
            memory["last_return_request_id"] = rr["return_request_id"]
            memory["return_pending"] = False
            memory["active_flow"] = "orders"

            if rr.get("already_exists"):
                return f"You already have a return request: **#{rr['return_request_id']}** (status: {rr['status']})."
            return f"Return request created: **#{rr['return_request_id']}** (status: {rr['status']})."

        prod = order_info.get("product") or {}
        item_line = _format_item_line(prod)
        tracking = order_info.get("tracking_number") or "N/A"

        return (
            f"Order **{order_info['order_id']}** is **{order_info['status']}**.\n"
            f"Item: **{item_line}**\n"
            f"Tracking: {tracking}"
        )

    # -------------------------
    # 5) LLM path (with guardrails)
    # -------------------------
    client = get_client()
    ctx = {
        "order": order_info,
        "faq": faqs,
        "wants_return": wants_return,
        "return_pending": bool(memory.get("return_pending")),
    }

    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            *history,
            {
                "role": "user",
                "content": (
                    f"User: {message}\n"
                    f"Context: {ctx}\n\n"
                    "If you want to create a return, reply with: CREATE_RETURN: <reason>\n"
                    "Only output CREATE_RETURN if:\n"
                    "- order.found is true, AND\n"
                    "- the user message contains a real reason (keywords or 'because ...') OR return_pending=true and the message is a reason.\n"
                    "Otherwise, ask for the missing info (order id and/or reason).\n"
                ),
            },
        ],
        temperature=0.2
    )

    text = resp.choices[0].message.content or ""

    if text.startswith("CREATE_RETURN:"):
        if order_info.get("need_order_id"):
            memory["return_pending"] = True
            memory["active_flow"] = "orders"
            return "Please provide your order ID to proceed with the return."

        if not order_info.get("found"):
            return f"I couldn’t find order {order_info.get('order_id')}. Please double-check the number."

        reason = text.replace("CREATE_RETURN:", "").strip()
        if not reason or not _has_return_reason(reason):
            memory["return_pending"] = True
            memory["active_flow"] = "orders"
            return "What’s the reason for the return? (e.g., damaged, wrong item, not working, changed mind)"

        rr = create_return_request(db, order_info["order_id"], reason[:200], message)
        memory["return_pending"] = False
        memory["last_return_request_id"] = rr["return_request_id"]
        memory["active_flow"] = "orders"

        if rr.get("already_exists"):
            return f"You already have a return request: **#{rr['return_request_id']}** (status: {rr['status']})."
        return f"Return request created: **#{rr['return_request_id']}** (status: {rr['status']})."

    return text
