from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

from app.database import Base


class SearchIndex(Base):
    __tablename__ = "search_index"

    search_index_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    enzyme_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("enzyme.enzyme_id"))
    source_file: Mapped[str] = mapped_column(String(160), nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    field_value_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enzyme = relationship("Enzyme")
