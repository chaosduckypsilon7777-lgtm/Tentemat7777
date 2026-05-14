from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from app.normalizers.base import NormalizedRecord


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return parsedate_to_datetime(str(value)).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None


def normalize_news(payload: dict[str, Any], source_name: str) -> NormalizedRecord:
    title = payload.get("title") or payload.get("headline")
    content = payload.get("seendate") or payload.get("summary") or payload.get("description")
    published_at = parse_datetime(
        payload.get("published_at")
        or payload.get("published")
        or payload.get("pubDate")
        or payload.get("seendate")
        or payload.get("filing_date")
    )
    return NormalizedRecord(
        item_type="news",
        title=title,
        content=content,
        url=payload.get("url") or payload.get("link"),
        published_at=published_at,
        language=payload.get("language") or payload.get("lang"),
        metadata={"source_name": source_name, "raw_keys": sorted(payload.keys())},
    )

