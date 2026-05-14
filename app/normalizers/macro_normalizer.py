from typing import Any

from app.normalizers.base import NormalizedRecord
from app.normalizers.news_normalizer import parse_datetime

_SERIES_LABELS: dict[str, str] = {
    "FEDFUNDS": "Federal Funds Rate",
    "CPIAUCSL": "CPI — All Urban Consumers",
    "UNRATE": "Unemployment Rate",
    "GDP": "Gross Domestic Product",
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "DEXUSEU": "USD/EUR Exchange Rate",
    "VIXCLS": "VIX Volatility Index",
}


def normalize_macro(payload: dict[str, Any], source_name: str) -> NormalizedRecord:
    series_id = payload.get("series_id", "macro")
    date = payload.get("date")
    value = payload.get("value")
    label = _SERIES_LABELS.get(series_id, series_id)
    return NormalizedRecord(
        item_type="macro",
        title=f"{label} — {date}",
        content=str(value),
        url=None,
        published_at=parse_datetime(date),
        metadata={
            "source_name": source_name,
            "series_id": series_id,
            "value": value,
            "series_url": f"https://fred.stlouisfed.org/series/{series_id}",
        },
    )

