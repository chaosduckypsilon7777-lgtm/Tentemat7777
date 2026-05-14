import json
from datetime import UTC, datetime
from typing import Any


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_outcome_price(payload: dict[str, Any]) -> float | None:
    tokens = payload.get("tokens") or []
    if tokens:
        return to_float(tokens[0].get("price"))

    outcome_prices = payload.get("outcomePrices")
    if isinstance(outcome_prices, str):
        try:
            outcome_prices = json.loads(outcome_prices)
        except json.JSONDecodeError:
            return None
    if isinstance(outcome_prices, list) and outcome_prices:
        return to_float(outcome_prices[0])
    return None


def normalize_market(payload: dict[str, Any]) -> dict[str, Any]:
    bid = to_float(payload.get("bestBid") or payload.get("best_bid") or payload.get("bid"))
    ask = to_float(payload.get("bestAsk") or payload.get("best_ask") or payload.get("ask"))
    mid_price = to_float(
        payload.get("mid_price") or payload.get("lastTradePrice") or payload.get("last_trade_price")
    )
    if mid_price is None:
        mid_price = first_outcome_price(payload)
    if mid_price is None and bid is not None and ask is not None:
        mid_price = (bid + ask) / 2
    return {
        "market_or_asset_id": str(
            payload.get("conditionId")
            or payload.get("condition_id")
            or payload.get("token_id")
            or payload.get("id")
            or payload.get("question")
        ),
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
        "bid": bid,
        "ask": ask,
        "mid_price": mid_price,
        "volume": to_float(payload.get("volumeNum") or payload.get("volume") or payload.get("volume_num")),
        "spread": (ask - bid) if ask is not None and bid is not None else None,
        "open_interest": to_float(payload.get("openInterest") or payload.get("open_interest")),
        "raw_json": payload,
    }
