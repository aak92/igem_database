from typing import Optional

from app.schemas.common import CamelModel


class EvidenceItem(CamelModel):
    doi: Optional[str] = None
    pubmed_id: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    publication_year: Optional[int] = None
    reference_type: Optional[str] = None
    positions: Optional[str] = None
    url: Optional[str] = None
    source_description: Optional[str] = None
    review_status: str = "official"
