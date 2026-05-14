import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from app.normalizers.base import NormalizedRecord


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    # GDELT compact format: "20240514T120000Z"
    if len(s) == 16 and s[8] == "T" and s.endswith("Z"):
        try:
            return datetime.strptime(s, "%Y%m%dT%H%M%SZ")
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return parsedate_to_datetime(s).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None


def normalize_news(payload: dict[str, Any], source_name: str) -> NormalizedRecord:
    title = payload.get("title") or payload.get("headline")
    content = payload.get("summary") or payload.get("description")
    if content:
        content = _strip_html(str(content)) or None
    if not content:
        domain = payload.get("domain") or payload.get("sourcecountry")
        if domain:
            content = domain
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

