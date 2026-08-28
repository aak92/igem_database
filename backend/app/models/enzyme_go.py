from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

from app.database import Base


class EnzymeGoTerm(Base):
    __tablename__ = "enzyme_go"

    go_record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[str] = mapped_column(String(20), ForeignKey("enzyme.enzyme_id"), nullable=False)
    go_id: Mapped[Optional[str]] = mapped_column(String(30))
    go_term: Mapped[Optional[str]] = mapped_column(String(500))
    go_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enzyme = relationship("Enzyme", back_populates="go_terms")
