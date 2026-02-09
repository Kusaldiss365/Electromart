from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.tools import search_products
from app.services.llm import get_client

SYSTEM = """You are a helpful Sales Agent for ElectroMart.

Your role is to help customers with:
- Product specifications and comparisons
- Pricing inquiries (always show prices in LKR)
- Stock availability checks
- Product recommendations based on customer needs
- Bundle deals and special offers

Guidelines:
- Be friendly, helpful, and concise
- Always mention prices in LKR (Sri Lankan Rupees)
- Only recommend products that are in stock
- Provide 1–3 product recommendations maximum
- Compare products when asked
- If asked about purchasing / checkout / buying now, DO NOT tell them to contact a sales team.
  Instead, tell them to type exactly: "buy now" to start the purchase flow in this chat.

Ambiguity handling (important):
- If the user request is unclear, vague, or missing key details (such as product category, budget, or usage),
  do NOT make assumptions or guess.
- Ask ONE short clarifying question before giving recommendations.
- When possible, provide 2–4 quick options the user can choose from to clarify their intent.
- Keep clarification questions focused only on product-related details (not personal details).

Keep your responses natural, conversational, and to the point.
Use only the products provided in the context.
"""


def _stock_status(p: dict) -> str:
    """
    Your DB seed uses `in_stock: bool`.
    Some older tools might return `stock_quantity`.
    Support both cleanly.
    """
    qty = p.get("stock_quantity", None)
    if qty is not None:
        try:
            qty_int = int(qty)
        except Exception:
            qty_int = 0
        return f"{qty_int} in stock" if qty_int > 0 else "Out of stock"

    in_stock = bool(p.get("in_stock", True))
    return "In stock" if in_stock else "Out of stock"


def _is_in_stock(p: dict) -> bool:
    qty = p.get("stock_quantity", None)
    if qty is not None:
        try:
            return int(qty) > 0
        except Exception:
            return False
    return bool(p.get("in_stock", True))


def format_products(products: list[dict], max_items: int = 10) -> str:
    if not products:
        return "No matching products found."

    lines = ["Available products:"]
    for p in products[:max_items]:
        name = p.get("name", "—")
        price = p.get("price", 0)
        sku = p.get("sku", "—")
        lines.append(f"• {name} — LKR {price:,.0f} ({_stock_status(p)}) [SKU: {sku}]")
    return "\n".join(lines)


def _is_followup(msg_lower: str) -> bool:
    # Vague follow-ups that usually refer to last shown items
    followup_phrases = [
        "compare", "which one", "which", "that one", "this one", "the first", "the second",
        "price", "spec", "specs", "details", "more details", "what about", "tell me more"
    ]
    return any(p in msg_lower for p in followup_phrases) or len(msg_lower.split()) <= 3


def _is_stock_question(msg_lower: str) -> bool:
    stock_words = ["stock", "available", "availability", "in stock", "out of stock"]
    return any(w in msg_lower for w in stock_words)


def _needs_recommendations(msg_lower: str) -> bool:
    rec_words = ["recommend", "suggest", "best", "which phone", "which tv", "which fridge", "what should i buy"]
    return any(w in msg_lower for w in rec_words)


def handle(
    db: Session,
    message: str,
    history: list[dict] | None,
    memory: dict | None
) -> str:
    history = history or []
    memory = memory or {}

    msg = (message or "").strip()
    if not msg:
        return "Hi! Tell me what you’re looking for (e.g., iPhone 15 Pro price, best TV under 300k, fridge for a small family)."

    lower = msg.lower()

    # 1) Use memory for follow-ups if the user is being vague
    if _is_followup(lower) and memory.get("last_products"):
        products = memory["last_products"]
    else:
        # 2) Search products
        # Rule:
        # - If user is asking about stock explicitly -> allow out-of-stock results (so we can say it's out of stock)
        # - Otherwise default to in-stock only (so we don't recommend out-of-stock)
        wants_stock_check = _is_stock_question(lower)
        products = search_products(db, msg, in_stock_only=not wants_stock_check)

        # Save results for follow-ups
        if products:
            memory["last_products"] = products

    # If user is NOT asking stock explicitly, filter to in-stock for safety (recommendation rule)
    if not _is_stock_question(lower):
        products = [p for p in (products or []) if _is_in_stock(p)]

    # If user wants recommendations, keep it to max 3 items (your requirement)
    if _needs_recommendations(lower) and products:
        products = products[:3]

    # 3) No LLM key -> deterministic listing (free)
    if not settings.OPENAI_API_KEY:
        if not products:
            return "I couldn’t find a matching product in stock. Try a brand/model (e.g., “iPhone 15”, “Samsung 55 QLED”, “LG 260L fridge”)."
        return format_products(products, max_items=10)

    # 4) LLM path (still constrained by our product context)
    client = get_client()

    if products:
        product_lines = []
        for p in products[:10]:
            product_lines.append(
                f"- {p.get('name','—')} — LKR {p.get('price',0):,.0f} "
                f"({_stock_status(p)}) [SKU: {p.get('sku','—')}]"
            )
        product_context = "\n".join(product_lines)
    else:
        product_context = "(No matching products found in stock)"

    # Add a small “policy reminder” to reduce hallucinations
    policy = (
        "Rules:\n"
        "- Only use the products listed in Available products.\n"
        "- If no product matches, ask one clarifying question (budget / size / brand).\n"
        "- Prices must be in LKR.\n"
        '- If asked to buy/checkout, tell them to type exactly: "buy now" to start the purchase flow.\n'
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM},
                *history,
                {
                    "role": "user",
                    "content": (
                        f"{policy}\n"
                        f"Available products:\n{product_context}\n\n"
                        f"Customer question: {msg}"
                    ),
                },
            ],
        )

        response = (resp.choices[0].message.content or "").strip()

        # Fallback to list if LLM returns empty
        if not response:
            if not products:
                return "I couldn’t find a matching product in stock. What brand/model or budget are you looking for?"
            return format_products(products, max_items=10)

        return response

    except Exception as e:
        print(f"[sales_agent] LLM error: {e}")
        if not products:
            return "I couldn’t find a matching product in stock. Try a brand/model (e.g., “iPhone 15”, “Samsung 55 QLED”, “LG 260L fridge”)."
        return format_products(products, max_items=10)
