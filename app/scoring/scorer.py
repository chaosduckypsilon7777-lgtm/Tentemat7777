from __future__ import annotations

from dataclasses import dataclass, field

SIGNAL_THRESHOLD = 0.45

_HIGH_IMPACT_FRED = {"FEDFUNDS", "CPIAUCSL", "UNRATE", "GDP", "DGS10"}


@dataclass
class ScoreResult:
    score: float
    signal_type: str
    reasons: list[str] = field(default_factory=list)


def score_normalized_item(
    source_name: str,
    item_type: str,
    metadata: dict | None,
) -> ScoreResult | None:
    meta = metadata or {}

    if source_name == "sec_edgar":
        form = meta.get("form", "")
        if form == "10-K":
            return ScoreResult(0.90, "important", ["SEC 10-K annual report"])
        if form == "8-K":
            return ScoreResult(0.80, "important", ["SEC 8-K current report"])
        return ScoreResult(0.65, "event", [f"SEC filing: {form}"])

    if source_name == "rss_official":
        return ScoreResult(0.60, "news", ["SEC official press release"])

    if source_name == "fred":
        series_id = meta.get("series_id", "")
        score = 0.75 if series_id in _HIGH_IMPACT_FRED else 0.60
        return ScoreResult(score, "macro_alert", [f"FRED macro: {series_id}"])

    if source_name == "gdelt":
        return ScoreResult(0.35, "news", ["GDELT news — unconfirmed"])

    return None


def score_market_data(
    source_name: str,
    volume: float | None,
    spread: float | None,
) -> ScoreResult | None:
    if source_name != "polymarket_clob":
        return None

    vol = volume or 0.0
    sp = spread if spread is not None else 1.0

    if vol > 1_000_000 and sp < 0.01:
        return ScoreResult(0.85, "market_watch", [f"volume {vol:,.0f}, spread {sp:.4f}"])
    if vol > 500_000:
        return ScoreResult(0.75, "market_watch", [f"volume {vol:,.0f} > 500K"])
    if vol > 100_000:
        return ScoreResult(0.60, "market_watch", [f"volume {vol:,.0f} > 100K"])

    return ScoreResult(0.35, "market_watch", [f"volume {vol:,.0f} — low"])
