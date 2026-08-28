from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

from app.database import Base


class EnzymeIsoform(Base):
    __tablename__ = "enzyme_isoform"

    isoform_record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enzyme_id: Mapped[str] = mapped_column(String(20), ForeignKey("enzyme.enzyme_id"), nullable=False)
    isoform_id: Mapped[Optional[str]] = mapped_column(String(80))
    isoform_length: Mapped[Optional[int]] = mapped_column(Integer)
    isoform_mass: Mapped[Optional[str]] = mapped_column(String(80))
    canonical_sequence: Mapped[Optional[str]] = mapped_column(Text)
    canonical_length: Mapped[Optional[int]] = mapped_column(Integer)
    canonical_mass: Mapped[Optional[str]] = mapped_column(String(80))
    sequence: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enzyme = relationship("Enzyme", back_populates="isoforms")
