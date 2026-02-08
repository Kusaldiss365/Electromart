from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.faq_rag import search_faq
from app.services.tools import create_support_ticket, extract_order_id
from app.services.llm import get_client

SYSTEM = """You are the Technical Support Agent for ElectroMart.
Use FAQ context for troubleshooting/warranty.
Create a support ticket ONLY when the user explicitly asks for it, OR when the user confirms after you offer to open one.
Ask only necessary questions.

IMPORTANT:
- If memory contains support_ticket_id, do NOT create a new ticket (unless user clearly asks for a NEW/ANOTHER ticket).
- If user asks for ticket number/status, answer using support_ticket_id from memory.

Rules (STRICT):
- Reply fully in ONE message. Never say “please hold”, “I’ll check”, or imply future replies.
- Always mention prices in LKR (Sri Lankan Rupees)

Ambiguity handling (important):
- If the user describes a problem vaguely or without enough detail to diagnose (e.g., device model, issue type, or error),
  do NOT guess the cause or solution.
- Ask ONE short clarifying question to gather the minimum required detail.
- When helpful, provide 2–3 example options the user can choose from (e.g., issue type or device model).
- Do not open a support ticket unless the user explicitly asks for it or clearly confirms after you offer.
"""

YES_WORDS = {
    "yes", "y", "yeah", "yep", "ok", "okay", "sure", "please", "go ahead", "do it"
}

def _wants_ticket(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "support ticket", "create ticket", "open ticket", "raise ticket",
        "create a ticket", "open a ticket", "raise a ticket",
        "log a ticket", "make a ticket",
        "need a ticket", "need to create a support ticket",
        "contact support", "talk to support", "agent", "representative",
    ]
    return any(x in t for x in triggers)

def _wants_new_ticket(text: str) -> bool:
    t = (text or "").lower()
    return any(x in t for x in ["new ticket", "another ticket", "different ticket", "open a new", "create a new"])

def _is_yes(text: str) -> bool:
    t = (text or "").lower().strip()
    # allow "yes please", "ok go ahead", etc.
    return any(w == t or w in t for w in YES_WORDS)

def _create_ticket_now(db: Session, message: str, memory: dict) -> str:
    oid = extract_order_id(message) or memory.get("last_order_id")

    # Keep issue simple; you can improve this later (e.g., detect warranty/return/technical).
    issue = memory.get("last_issue") or "Support request"
    details = message or "User requested a support ticket."

    t = create_support_ticket(db, issue, details, oid)

    memory["support_ticket_id"] = t["ticket_id"]
    memory["active_flow"] = "support"
    memory.pop("ticket_pending", None)

    if oid:
        memory["order_id"] = oid
        memory["last_order_id"] = oid

    memory["last_issue"] = issue

    return f"I opened a support ticket for you: **#{t['ticket_id']}**. Our team will follow up soon."

def handle(db: Session, message: str, history: list[dict], memory: dict) -> str:
    faqs = search_faq(db, message, k=4)
    history = history or []
    memory = memory or {}
    message = message or ""
    lower = message.lower()

    existing_ticket_id = memory.get("support_ticket_id")

    # Ticket ID queries
    if existing_ticket_id and any(k in lower for k in [
        "ticket number", "ticket id", "reference number", "my ticket",
        "what's the ticket", "whats the ticket", "ticket status", "status of my ticket"
    ]):
        memory["active_flow"] = "support"
        return f"Your support ticket number is **#{existing_ticket_id}**."

    wants_ticket = _wants_ticket(message)
    wants_new_ticket = _wants_new_ticket(message)

    confirms_ticket = bool(memory.get("ticket_pending")) and _is_yes(message)
    effective_wants_ticket = wants_ticket or confirms_ticket

    # Existing ticket handling
    if existing_ticket_id:
        memory["active_flow"] = "support"
        if effective_wants_ticket and not wants_new_ticket:
            return f"A support ticket is already open for this issue: **#{existing_ticket_id}**."
        if wants_new_ticket:
            memory.pop("support_ticket_id", None)
            existing_ticket_id = None

    # ✅ HARD RULE: If user explicitly wants a ticket (or confirmed), create it NOW (no LLM dependency)
    if effective_wants_ticket:
        return _create_ticket_now(db, message, memory)

    # -------------------------
    # No-LLM path
    # -------------------------
    if not settings.OPENAI_API_KEY:
        # Troubleshooting first
        memory["active_flow"] = "support"

        if faqs:
            memory["ticket_pending"] = True
            return (
                "Try these steps:\n"
                + "\n".join([f"- {f['answer']}" for f in faqs[:2]])
                + "\n\nIf this doesn’t help, want me to open a support ticket? (yes/no)"
            )

        memory["ticket_pending"] = True
        return (
            "What’s the exact model and what happens when you try to use it "
            "(won’t turn on, screen issue, battery, overheating, etc.)?\n"
            "If you want, I can open a support ticket — reply **yes**."
        )

    # -------------------------
    # LLM path (for troubleshooting + asking 1 question)
    # -------------------------
    client = get_client()
    ctx = {
        "faq": faqs,
        "ticket_pending": bool(memory.get("ticket_pending")),
        "has_existing_ticket": bool(existing_ticket_id),
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
                    "Do troubleshooting using FAQ if relevant.\n"
                    "Ask ONE short clarifying question if needed.\n"
                    "If you offer to open a support ticket, include: 'Reply yes to open a ticket.'"
                ),
            },
        ],
        temperature=0.3
    )
    text = (resp.choices[0].message.content or "").strip()

    if any(x in text.lower() for x in ["reply yes to open", "want me to open", "open a support ticket", "create a ticket", "raise a ticket"]):
        memory["ticket_pending"] = True

    memory["active_flow"] = "support"
    return text
