from datetime import datetime
from typing import Any


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_market(payload: dict[str, Any]) -> dict[str, Any]:
    bid = to_float(payload.get("best_bid") or payload.get("bid"))
    ask = to_float(payload.get("best_ask") or payload.get("ask"))
    mid_price = to_float(payload.get("mid_price") or payload.get("last_trade_price"))
    if mid_price is None and bid is not None and ask is not None:
        mid_price = (bid + ask) / 2
    return {
        "market_or_asset_id": str(
            payload.get("condition_id")
            or payload.get("token_id")
            or payload.get("id")
            or payload.get("question")
        ),
        "timestamp": datetime.utcnow(),
        "bid": bid,
        "ask": ask,
        "mid_price": mid_price,
        "volume": to_float(payload.get("volume") or payload.get("volume_num")),
        "spread": (ask - bid) if ask is not None and bid is not None else None,
        "open_interest": to_float(payload.get("open_interest")),
        "raw_json": payload,
    }

