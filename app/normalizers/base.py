from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class NormalizedRecord:
    item_type: str
    title: str | None
    content: str | None
    url: str | None
    published_at: datetime | None
    language: str | None = None
    entities: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

