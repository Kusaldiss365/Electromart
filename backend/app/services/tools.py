import re
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Lead
from app.models.order import Order
from app.models.product import Product
from app.models.promotion import Promotion
from app.models.ticket import SupportTicket
from app.models.return_request import ReturnRequest
from app.services.mailer import send_lead_email

# -------------------------
# Order helpers
# -------------------------

ORDER_RE = re.compile(
    r"(?:order\s*(?:id)?\s*#?\s*|#|id\s*)(\d{1,10})\b",
    re.IGNORECASE
)

def extract_order_id(text: str) -> int | None:
    if not text:
        return None

    m = ORDER_RE.search(text)
    if m:
        return int(m.group(1))

    # fallback: "101"
    t = text.strip()
    if t.isdigit():
        return int(t)

    return None


def get_order_status(db: Session, text: str, order_id: int | None = None) -> dict:
    oid = order_id if order_id is not None else extract_order_id(text)

    if oid is None:
        return {"found": False, "need_order_id": True}

    order = db.get(Order, oid)
    if not order:
        return {"found": False, "need_order_id": False, "order_id": oid}

    product = order.product

    return {
        "found": True,
        "order_id": order.id,
        "status": order.status,
        "tracking_number": order.tracking_number,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "total_amount": float(order.total_amount),

        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price": float(product.price),
        } if product else None
    }



# -------------------------
# Promotions
# -------------------------

def list_promotions(db: Session) -> list[dict]:
    promos = (
        db.query(Promotion)
        .order_by(Promotion.valid_until.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "title": p.title,
            "details": p.details,
            "discount_percent": float(p.discount_percent),
            "valid_until": p.valid_until.isoformat(),
        }
        for p in promos
    ]


# -------------------------
# Product search (generic)
# -------------------------

CATEGORY_ALIASES = {
    "smartphone": "phone",
    "smartphones": "phone",
    "phone": "phone",
    "phones": "phone",
    "iphone": "phone",
    "iphones": "phone",
    "mobile": "phone",
    "mobiles": "phone",
    "television": "tv",
    "tvs": "tv",
    "tv": "tv",
    "fridge": "fridge",
    "fridges": "fridge",
    "refrigerator": "fridge",
}

STOPWORDS = {
    "i", "want", "to", "buy", "need", "show", "me", "please", "do", "you", "have",
    "in", "stock", "available", "now", "looking", "for", "any", "options", "a", "an", "the"
}

BRANDS = ["samsung", "apple", "iphone", "lg", "sony", "asus", "dell", "hp", "lenovo"]


def _tokens(message: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (message or "").lower())
    out = []
    for w in words:
        w = CATEGORY_ALIASES.get(w, w)
        if w not in STOPWORDS:
            out.append(w)
    return out


def _extract_brand(message: str) -> str | None:
    toks = _tokens(message)
    for b in BRANDS:
        b_norm = CATEGORY_ALIASES.get(b, b)
        if b_norm in toks or b_norm in (message or "").lower():
            # normalize "iphone" -> "apple" if you want
            return "apple" if b_norm == "iphone" else b_norm
    return None


def _extract_keyword(message: str) -> str | None:
    toks = _tokens(message)
    return max(toks, key=len) if toks else None  # longest useful token

def search_products(db: Session, message: str, in_stock_only: bool = True) -> list[dict]:
    stmt = db.query(Product)

    if in_stock_only:
        stmt = stmt.filter(Product.in_stock == True)  # noqa: E712

    # dynamic categories from DB (future-proof)
    categories = [c[0] for c in db.query(Product.category).distinct().all() if c and c[0]]
    cat_map = {c.lower(): c for c in categories}

    toks = _tokens(message)
    msg_joined = " ".join(toks)

    # try to match a category from tokens (e.g., "phone", "tv", "fridge")
    matched_category = None
    for c_lower, c_real in sorted(cat_map.items(), key=lambda x: len(x[0]), reverse=True):
        if c_lower in msg_joined:
            matched_category = c_real
            break

    if matched_category:
        brand = _extract_brand(message)
        if brand:
            stmt = stmt.filter(Product.name.ilike(f"%{brand}%"))
    else:
        kw = _extract_keyword(message)
        if kw:
            like = f"%{kw}%"
            stmt = stmt.filter(
                or_(
                    Product.name.ilike(like),
                    Product.category.ilike(like),
                    Product.description.ilike(like),
                    Product.sku.ilike(like),
                )
            )

    products = stmt.limit(8).all()
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "price": float(p.price),
            "in_stock": bool(p.in_stock),
        }
        for p in products
    ]



# -------------------------
# Support / returns
# -------------------------

def create_support_ticket(db: Session, issue: str, details: str, order_id: int | None = None) -> dict:
    t = SupportTicket(order_id=order_id, issue=issue[:200], details=details)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"ticket_id": t.id, "created_at": t.created_at.isoformat()}


def create_return_request(db: Session, order_id: int, reason: str, notes: str = "") -> dict:
    existing = (
        db.query(ReturnRequest)
        .filter(ReturnRequest.order_id == order_id)
        .order_by(ReturnRequest.id.desc())
        .first()
    )
    if existing and existing.status in {"requested", "approved"}:
        return {
            "return_request_id": existing.id,
            "status": existing.status,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
            "already_exists": True,
        }

    rr = ReturnRequest(
        order_id=order_id,
        reason=reason[:200],
        notes=notes,
        status="requested",
    )
    db.add(rr)
    db.commit()
    db.refresh(rr)
    return {
        "return_request_id": rr.id,
        "status": rr.status,
        "created_at": rr.created_at.isoformat(),
        "already_exists": False,
    }



RETURN_RE = re.compile(r"(?:return\s*(?:request)?\s*#?\s*|rr\s*#?\s*)(\d{1,10})\b", re.IGNORECASE)

def extract_return_request_id(text: str) -> int | None:
    if not text:
        return None
    m = RETURN_RE.search(text)
    return int(m.group(1)) if m else None


def get_return_request(db: Session, rr_id: int) -> dict:
    rr = db.get(ReturnRequest, rr_id)
    if not rr:
        return {"found": False, "return_request_id": rr_id}

    # order/product info (safe if relationship exists)
    order = getattr(rr, "order", None)
    product = getattr(order, "product", None) if order else None

    return {
        "found": True,
        "return_request_id": rr.id,
        "status": rr.status,
        "reason": rr.reason,
        "notes": rr.notes,
        "created_at": rr.created_at.isoformat() if rr.created_at else None,
        "order": {
            "order_id": order.id,
            "status": order.status,
            "tracking_number": order.tracking_number,
        } if order else {"order_id": rr.order_id},
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price": float(product.price),
        } if product else None,
    }


# -------------------------
# Leads
# -------------------------

def create_lead(
    db: Session,
    conversation_id: str,
    name: str,
    phone: str,
    interest: str = "",
    notes: str = "",
) -> dict:
    lead = Lead(
        conversation_id=conversation_id,
        name=name.strip(),
        phone=phone.strip(),
        interest=interest.strip(),
        notes=notes.strip(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Send email AFTER commit (so lead.id exists)
    subject = f"New Lead #{lead.id} — {lead.interest or 'Purchase'}"
    body = (
        f"Lead ID: {lead.id}\n"
        f"Name: {lead.name}\n"
        f"Phone: {lead.phone}\n"
        f"Interest: {lead.interest}\n"
        f"Notes: {lead.notes}\n"
    )
    send_lead_email(subject=subject, body=body)

    return {"lead_id": lead.id, "created_at": lead.created_at.isoformat()}