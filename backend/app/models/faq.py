from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from pgvector.sqlalchemy import Vector

# text-embedding-3-small => 1536 dims
class FAQ(Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
