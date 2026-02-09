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
- If asked about purchasing / checkout / buying now, DO NOT tell them to contact a sales team.
  Instead, tell them to type exactly: "buy now" to start the purchase flow in this chat.

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

# If user is clearly asking policy/info, we should NOT enter/continue return_pending flow
INFO_ONLY_HINTS = [
    "policy", "return policy", "refund policy", "how refunds", "refunds work",
    "delivery time", "how long does delivery", "shipping time", "delivery take",
    "when will it arrive", "eta", "track", "tracking", "shipping", "delivery",
    "how to return", "return process", "refund process"
]

# If user switches topics while return_pending, we should release them from the return flow
TOPIC_SWITCH_HINTS = [
    "delivery", "shipping", "track", "tracking", "eta", "where is my order",
    "support", "technical", "warranty", "issue", "problem", "help"
]


def _has_return_reason(text: str) -> bool:
    t = (text or "").lower().strip()
    if not t:
        return False
    if "because" in t:
        return True
    return any(h in t for h in REASON_HINTS)


def _is_info_question(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in INFO_ONLY_HINTS)


def _wants_return_action(text: str) -> bool:
    """
    User is trying to DO a return/refund/cancel/exchange, not just ask policy.
    We intentionally do NOT trigger on the bare words "return/refund" because
    policy questions like "What is your return policy?" would get stuck.
    """
    t = (text or "").lower()
    action_phrases = [
        "i want to return", "i wanna return", "return my", "refund my",
        "i want a refund", "i need a refund", "i want to cancel", "cancel my",
        "i want to exchange", "exchange my", "start a return", "create return",
        "raise a return", "return order", "refund order", "cancel order", "exchange order"
    ]
    return any(p in t for p in action_phrases)


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

    # Return intent split:
    wants_return_action = _wants_return_action(message)
    info_question = _is_info_question(message)

    # -------------------------
    # 2) Return flow gating (NO STICKY TRAP)
    # -------------------------

    # If user asks policy/info, do NOT enter return flow; also clear pending state
    if info_question and not wants_return_action:
        memory["return_pending"] = False
        memory["active_flow"] = "orders"
        # continue to FAQ/LLM answering

    # If we were waiting for a reason and user changed topic → release them
    if memory.get("return_pending") and not wants_return_action:
        if any(k in lower for k in TOPIC_SWITCH_HINTS):
            memory["return_pending"] = False
            memory["active_flow"] = "orders"
            # continue normal handling (do NOT return here)

    # If user is trying to DO a return but provides no reason → ask for reason and set pending
    if wants_return_action and not _has_return_reason(message):
        memory["return_pending"] = True
        memory["active_flow"] = "orders"
        if oid:
            memory["last_order_id"] = oid
            return f"Please provide a reason for returning order **{oid}** (e.g., damaged, wrong item, not working, changed mind)."
        return "Please provide your order ID and the reason for the return (e.g., Order 101 - damaged)."

    # If we were waiting for a reason and user provided it now → create return
    if memory.get("return_pending") and not info_question:
        # Guard: user just sent order id / short text, not a reason
        maybe_oid = extract_order_id(message)
        if maybe_oid and len(message.split()) <= 3 and not _has_return_reason(message):
            memory["last_order_id"] = maybe_oid
            memory["active_flow"] = "orders"
            return "Got it — what’s the reason for the return? (e.g., damaged, wrong item, not working, changed mind)"

        # If still not a real reason, ask again (one question)
        if not _has_return_reason(message):
            memory["active_flow"] = "orders"
            return "What’s the reason for the return? (e.g., damaged, wrong item, not working, changed mind)"

        # Create return now (we have a reason)
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
        # Policy/info answers from FAQ if available
        if info_question and faqs:
            memory["active_flow"] = "orders"
            return " ".join([f["answer"] for f in faqs[:2]]).strip()

        if order_info.get("need_order_id") and not info_question:
            return "Please share your order number (e.g., Order 101)."

        if not order_info.get("found") and not info_question:
            return f"I couldn’t find order {order_info.get('order_id')}. Please double-check the number."

        # Create return ONLY if user is doing a return action + reason exists + order is found
        if wants_return_action and order_info.get("found") and _has_return_reason(message):
            rr = create_return_request(db, order_info["order_id"], message[:200], message)
            memory["last_return_request_id"] = rr["return_request_id"]
            memory["return_pending"] = False
            memory["active_flow"] = "orders"

            if rr.get("already_exists"):
                return f"You already have a return request: **#{rr['return_request_id']}** (status: {rr['status']})."
            return f"Return request created: **#{rr['return_request_id']}** (status: {rr['status']})."

        # If it's info-only and no FAQ, give a safe generic response
        if info_question and not faqs:
            memory["active_flow"] = "orders"
            return "Could you tell me if you’re asking about **returns/refunds** or **delivery/tracking**? I can explain the policy."

        # Normal order status response
        prod = (order_info.get("product") or {}) if order_info.get("found") else {}
        item_line = _format_item_line(prod)
        tracking = order_info.get("tracking_number") or "N/A"

        if order_info.get("found"):
            return (
                f"Order **{order_info['order_id']}** is **{order_info['status']}**.\n"
                f"Item: **{item_line}**\n"
                f"Tracking: {tracking}"
            )

        return "Please share your order ID (e.g., Order 101) or the return request number (e.g., request 2)."

    # -------------------------
    # 5) LLM path (with guardrails)
    # -------------------------
    client = get_client()
    ctx = {
        "order": order_info,
        "faq": faqs,
        "wants_return_action": wants_return_action,
        "return_pending": bool(memory.get("return_pending")),
        "info_question": info_question,
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
                    "If the user is asking policy/info (info_question=true), answer using FAQ context. Do NOT ask for order id.\n"
                    "If you want to create a return, reply with: CREATE_RETURN: <reason>\n"
                    "Only output CREATE_RETURN if:\n"
                    "- order.found is true, AND\n"
                    "- wants_return_action=true, AND\n"
                    "- if the user message contains a real reason (keywords or 'because ...') OR return_pending=true and the message is a reason.\n"
                    "- If asked to buy/checkout, tell them to type exactly: 'buy now' to start the purchase flow.\n"
                    "Otherwise, ask for the missing info (order id and/or reason) with ONE short question.\n"
                ),
            },
        ],
        temperature=0.2
    )

    text = (resp.choices[0].message.content or "").strip()

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

    # If LLM offers return ticket creation, set pending (but avoid sticky trap on info questions)
    if (not info_question) and any(x in text.lower() for x in ["what’s the reason", "what is the reason", "reason for the return"]):
        memory["return_pending"] = True

    memory["active_flow"] = "orders"
    return text
