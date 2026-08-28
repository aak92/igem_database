from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

from app.database import Base
from app.models._enums import ReviewStatus


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[str] = mapped_column(String(20), ForeignKey("enzyme.enzyme_id"), nullable=False)
    doi: Mapped[Optional[str]] = mapped_column(String(200))
    pubmed_id: Mapped[Optional[str]] = mapped_column(String(20))
    title: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[str]] = mapped_column(Text)
    journal: Mapped[Optional[str]] = mapped_column(String(300))
    volume: Mapped[Optional[str]] = mapped_column(String(80))
    pages: Mapped[Optional[str]] = mapped_column(String(80))
    publication_year: Mapped[Optional[int]] = mapped_column(Integer)
    reference_type: Mapped[Optional[str]] = mapped_column(String(120))
    positions: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(500))
    source_description: Mapped[Optional[str]] = mapped_column(String(500))
    review_status: Mapped[ReviewStatus] = mapped_column(default=ReviewStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enzyme = relationship("Enzyme", back_populates="evidences")
