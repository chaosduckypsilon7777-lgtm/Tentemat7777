from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.scoring.confirmation import _keywords
from app.storage.models import Signal

NOVELTY_WINDOW_HOURS = 24
_MIN_OVERLAP = 3


def is_novel(
    session: Session,
    title: str | None,
    source_id: int,
    window_hours: int = NOVELTY_WINDOW_HOURS,
) -> bool:
    """Return False if a very similar signal from the same source exists within the window."""
    if not title:
        return True

    kw = _keywords(title)
    if len(kw) < _MIN_OVERLAP:
        return True

    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=window_hours)

    existing = session.scalars(
        select(Signal.title).where(
            Signal.source_id == source_id,
            Signal.created_at >= since,
            Signal.title.isnot(None),
        )
    ).all()

    for other_title in existing:
        overlap = len(kw & _keywords(other_title))
        if overlap >= _MIN_OVERLAP:
            return False

    return True


def novelty_score_penalty(is_new: bool) -> float:
    """Score reduction for repeated signals (applied multiplicatively)."""
    return 1.0 if is_new else 0.75
