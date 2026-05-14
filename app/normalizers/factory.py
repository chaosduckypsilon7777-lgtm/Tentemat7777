from app.normalizers.base import NormalizedRecord
from app.normalizers.event_normalizer import normalize_event
from app.normalizers.macro_normalizer import normalize_macro
from app.normalizers.news_normalizer import normalize_news
from app.sources.base import SourceConfig


def normalize_payload(payload: dict, source: SourceConfig) -> NormalizedRecord | None:
    if source.category == "market":
        return None
    if source.category == "macro":
        return normalize_macro(payload, source.name)
    if source.category == "event":
        return normalize_event(payload, source.name)
    return normalize_news(payload, source.name)

