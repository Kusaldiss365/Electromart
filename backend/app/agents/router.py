import re
from app.core.config import settings
from app.services.llm import get_client

ROUTER_SYSTEM = """You are an intent router for an electronics store.
Return ONLY one label: sales, marketing, support, orders.

Rules (strict):
- sales: buying intent, product inquiries, specs, pricing, availability/stock, comparisons, recommendations,
         payment methods (card/bank/COD), delivery location for a purchase, bundles/offers when selecting products.
- orders: ONLY existing order flows: tracking/status/shipping updates, returns/refunds/cancel/exchange for an order.
- support: troubleshooting, warranty, repairs, setup, technical help, support tickets.
- marketing: promotions/discounts/campaigns (when not actively buying a product).

Return exactly one label word only.
"""

ORDER_ID_RE = re.compile(r"(?:order\s*(?:id)?\s*#?\s*|#|id\s*)(\d{1,10})\b", re.IGNORECASE)
BARE_ID_RE = re.compile(r"^\s*(\d{1,10})\s*$")

SALES_KW = [
    "buy", "purchase", "price", "cost", "available", "availability", "in stock", "stock",
    "recommend", "suggest", "compare", "spec", "specs", "features",
    "payment", "pay", "credit", "debit", "card", "bank transfer", "cash on delivery", "cod",
    "delivery to", "deliver to", "deliver", "delivery", "location", "area",
]

ORDERS_KW = [
    "track", "tracking", "where is my order", "order status", "shipped", "delivered",
    "return", "refund", "cancel", "exchange",
]

SUPPORT_KW = [
    "not working", "won't", "doesn't", "broken", "issue", "problem", "error",
    "warranty", "repair", "setup", "install", "troubleshoot",
    "support ticket", "open ticket", "create ticket",
]

MARKETING_KW = ["discount", "promo", "deal", "offer", "coupon", "loyalty", "campaign"]

POLICY_KW = [
    "policy",
    "return policy",
    "refund policy",
    "exchange policy",
    "cancellation policy",
    "terms",
    "conditions",
]

def _set_flow(memory: dict, label: str) -> str:
    memory["active_flow"] = label
    return label


def route_intent(message: str, history: list[dict], memory: dict | None = None) -> str:
    if memory is None:
        memory = {}
    message = message or ""
    m = message.lower()
    clean = " ".join(m.split())

    if memory.get("return_pending"):
        memory["active_flow"] = "orders"
        return "orders"

    # -------------------------
    # 0) Sticky orders flow (VERY IMPORTANT)
    # -------------------------
    if memory.get("active_flow") == "orders":
        if any(k in m for k in POLICY_KW) and not ORDER_ID_RE.search(message):
            return _set_flow(memory, "support")

        # Bare "101" should continue orders flow
        if BARE_ID_RE.match(message):
            return _set_flow(memory, "orders")

        # Explicit switches
        if any(k in m for k in SUPPORT_KW):
            return _set_flow(memory, "support")
        if any(k in m for k in MARKETING_KW):
            return _set_flow(memory, "marketing")
        if any(k in m for k in SALES_KW) and not any(k in m for k in ORDERS_KW) and not ORDER_ID_RE.search(message):
            return _set_flow(memory, "sales")

        return _set_flow(memory, "orders")

    # -------------------------
    # 1) Greetings → sales
    # -------------------------
    GREETINGS = {
        "hi", "hello", "hey",
        "good morning", "good afternoon", "good evening",
        "gm", "ga", "ge",
    }
    if clean in GREETINGS or clean.rstrip("!") in GREETINGS:
        return _set_flow(memory, "sales")

    # -------------------------
    # 2) Sticky sales flow
    # -------------------------
    if memory.get("active_flow") == "sales":
        if any(k in m for k in SUPPORT_KW):
            return _set_flow(memory, "support")
        if ORDER_ID_RE.search(message) or any(k in m for k in ORDERS_KW):
            return _set_flow(memory, "orders")
        if any(k in m for k in MARKETING_KW):
            return _set_flow(memory, "marketing")
        return _set_flow(memory, "sales")

    # -------------------------
    # 3) Keyword intent detection
    # -------------------------
    has_order_id = bool(ORDER_ID_RE.search(message))

    is_sales = any(k in m for k in SALES_KW)
    is_orders = any(k in m for k in ORDERS_KW)
    is_support = any(k in m for k in SUPPORT_KW)
    is_marketing = any(k in m for k in MARKETING_KW)

    # Strong rule: explicit order-id means existing order context
    if has_order_id and (is_orders or "order" in m or "status" in m or "track" in m):
        return _set_flow(memory, "orders")

    # Conflict: user mentions delivery + return/refund etc.
    if is_sales and is_orders:
        # If return/refund/track etc. → orders
        if any(k in m for k in ["return", "refund", "cancel", "exchange", "track", "tracking", "order status"]):
            return _set_flow(memory, "orders")
        return _set_flow(memory, "sales")

    if is_orders:
        return _set_flow(memory, "orders")
    if is_support:
        return _set_flow(memory, "support")
    if is_marketing:
        return _set_flow(memory, "marketing")
    if is_sales:
        return _set_flow(memory, "sales")

    # -------------------------
    # 4) No LLM → default sales
    # -------------------------
    if not settings.OPENAI_API_KEY:
        return _set_flow(memory, "sales")

    # -------------------------
    # 5) LLM fallback
    # -------------------------
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM},
            *(history or []),
            {"role": "user", "content": message},
        ],
        temperature=0,
    )

    label = (resp.choices[0].message.content or "").strip().lower()
    if label not in {"sales", "marketing", "support", "orders"}:
        label = "sales"
    return _set_flow(memory, label)
