from typing import Any

from app.normalizers.base import NormalizedRecord
from app.normalizers.news_normalizer import parse_datetime


def normalize_event(payload: dict[str, Any], source_name: str) -> NormalizedRecord:
    form = payload.get("form") or payload.get("event_type") or "event"
    accession = payload.get("accession_number") or payload.get("id")
    return NormalizedRecord(
        item_type="event",
        title=f"{form} {accession}".strip(),
        content=None,
        url=payload.get("url"),
        published_at=parse_datetime(payload.get("filing_date") or payload.get("published_at")),
        metadata={"source_name": source_name, **payload},
    )

