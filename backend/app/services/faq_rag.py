import hashlib
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

def _fake_embedding_1536(text_value: str) -> list[float]:
    """
    Deterministic pseudo-embedding so the system works even without OpenAI key.
    """
    h = hashlib.sha256(text_value.encode("utf-8")).digest()
    # Expand to 1536 floats in [-1, 1]
    out = []
    seed = int.from_bytes(h[:8], "big")
    x = seed
    for _ in range(1536):
        # xorshift-ish
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 7)
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        val = ((x % 2000000) / 1000000.0) - 1.0
        out.append(float(val))
    return out

def embed(text_value: str) -> list[float]:
    # Use OpenAI embeddings if key exists; otherwise fake vectors.
    if settings.OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.embeddings.create(model=settings.EMBED_MODEL, input=text_value)
        return resp.data[0].embedding
    return _fake_embedding_1536(text_value)

def search_faq(db: Session, query: str, k: int = 4) -> list[dict]:
    q_emb = embed(query)

    # Convert Python list -> pgvector literal string: "[0.1,0.2,...]"
    vec_str = "[" + ",".join(f"{x:.6f}" for x in q_emb) + "]"

    sql = text("""
        SELECT question, answer
        FROM faqs
        ORDER BY embedding <-> CAST(:emb AS vector)
        LIMIT :k
    """)

    rows = db.execute(sql, {"emb": vec_str, "k": k}).mappings().all()
    return [dict(r) for r in rows]


