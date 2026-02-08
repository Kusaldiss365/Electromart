from openai import OpenAI
from app.core.config import settings

def get_client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing in .env")
    return OpenAI(api_key=settings.OPENAI_API_KEY)
