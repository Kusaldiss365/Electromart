from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.tools import list_promotions
from app.services.llm import get_client

SYSTEM = """You are the Marketing Agent for ElectroMart.
Explain current promotions clearly. If user asks for a deal, suggest 1–3 promotions.
Short, friendly, no fluff.

Rules (STRICT):
- Reply fully in ONE message. Never say “please hold”, “I’ll check”, or imply future replies.
- Always mention prices in LKR (Sri Lankan Rupees)
- If asked about purchasing / checkout / buying now, DO NOT tell them to contact a sales team.
  Instead, tell them to type exactly: "buy now" to start the purchase flow in this chat.

Ambiguity handling (important):
- If the user asks about deals or offers but does not specify a product category, budget range, or promotion type,
  do NOT assume or invent promotions.
- Ask ONE short clarifying question to understand what kind of deal they want.
- Provide 2–4 quick options the user can choose from (e.g., product category or budget range).
- Keep clarification focused only on promotions and offers.

"""

def handle(db: Session, message: str, history: list[dict], memory: dict) -> str:
    promos = list_promotions(db)

    history = history or []

    if not settings.OPENAI_API_KEY:
        if not promos:
            return "No active promotions right now."
        lines = ["Current promotions:"]
        for p in promos[:5]:
            lines.append(f"- {p['title']} ({p['discount_percent']}%): {p['details']}")
        return "\n".join(lines)

    client = get_client()
    ctx = {"promotions": promos}
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            *history,
            {"role": "user", "content": f"User: {message}\nContext: {ctx}"}
        ],
        temperature=0.2
    )
    return resp.choices[0].message.content or ""
