from typing import Any

from app.normalizers.base import NormalizedRecord
from app.normalizers.news_normalizer import parse_datetime


def normalize_macro(payload: dict[str, Any], source_name: str) -> NormalizedRecord:
    series_id = payload.get("series_id", "macro")
    date = payload.get("date")
    value = payload.get("value")
    return NormalizedRecord(
        item_type="macro",
        title=f"{series_id} {date}",
        content=str(value),
        url=None,
        published_at=parse_datetime(date),
        metadata={"source_name": source_name, "series_id": series_id, "value": value},
    )

