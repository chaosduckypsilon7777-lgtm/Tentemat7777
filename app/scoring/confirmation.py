from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.storage.models import NormalizedItem

WINDOW_HOURS = 2
_MIN_OVERLAP = 2
_STOPWORDS = {
    "the", "a", "an", "of", "in", "to", "for", "is", "are", "was", "will",
    "by", "on", "at", "from", "with", "that", "this", "be", "has", "have",
    "had", "its", "it", "or", "and", "but", "not", "than", "more", "all",
    "would", "could", "should", "their", "they", "which", "when", "what",
}


def _keywords(text: str) -> set[str]:
    return {
        w.strip(".,!?;:\"'()[]/-")
        for w in text.lower().split()
        if len(w) > 3 and w.strip(".,!?;:\"'()[]/-") not in _STOPWORDS
    }


def count_cross_source_confirmations(
    session: Session,
    title: str | None,
    source_id: int,
    window_hours: int = WINDOW_HOURS,
) -> int:
    """Return number of distinct other sources with a recent item sharing ≥2 keywords."""
    if not title:
        return 0

    kw = _keywords(title)
    if len(kw) < _MIN_OVERLAP:
        return 0

    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=window_hours)

    rows = session.execute(
        select(NormalizedItem.title, NormalizedItem.source_id).where(
            NormalizedItem.source_id != source_id,
            NormalizedItem.retrieved_at >= since,
            NormalizedItem.title.isnot(None),
        )
    ).all()

    confirming: set[int] = set()
    for other_title, other_src in rows:
        if len(kw & _keywords(other_title)) >= _MIN_OVERLAP:
            confirming.add(other_src)

    return len(confirming)


def apply_confirmation_boost(score: float, confirmation_count: int) -> float:
    if confirmation_count >= 2:
        return round(min(score + 0.12, 1.0), 2)
    if confirmation_count >= 1:
        return round(min(score + 0.06, 1.0), 2)
    return score
