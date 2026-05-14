from typing import Any

from app.normalizers.base import NormalizedRecord
from app.normalizers.news_normalizer import parse_datetime


def normalize_event(payload: dict[str, Any], source_name: str) -> NormalizedRecord:
    form = payload.get("form") or payload.get("event_type") or "event"
    accession = payload.get("accession_number") or payload.get("id")
    entity_name = payload.get("entity_name")
    title_parts = [f"SEC {form}" if source_name == "sec_edgar" else str(form)]
    if entity_name:
        title_parts.append(str(entity_name))
    if accession:
        title_parts.append(f"({accession})")
    return NormalizedRecord(
        item_type="event",
        title=": ".join(title_parts[:2]) + (f" {title_parts[2]}" if len(title_parts) > 2 else ""),
        content=None,
        url=payload.get("url"),
        published_at=parse_datetime(payload.get("filing_date") or payload.get("published_at")),
        metadata={"source_name": source_name, **payload},
    )
