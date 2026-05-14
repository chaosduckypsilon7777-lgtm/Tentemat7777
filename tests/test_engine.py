from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from app.fetchers.engine import FetchingEngine
from app.normalizers.market_normalizer import first_outcome_price, normalize_market
from app.utils.hashing import stable_hash


def test_stable_hash_is_order_independent():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})


def test_stable_hash_changes_with_payload():
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_parse_retry_after_delta_seconds():
    assert FetchingEngine._parse_retry_after("120") == 120


def test_parse_retry_after_http_date():
    retry_at = datetime.now(UTC) + timedelta(seconds=60)

    assert FetchingEngine._parse_retry_after(format_datetime(retry_at)) in range(0, 61)


def test_normalize_market_reads_gamma_fields():
    normalized = normalize_market(
        {
            "conditionId": "0xabc",
            "bestBid": "0.41",
            "bestAsk": "0.43",
            "lastTradePrice": "0.42",
            "volumeNum": "123.45",
            "openInterest": "10",
        }
    )

    assert normalized["market_or_asset_id"] == "0xabc"
    assert normalized["bid"] == 0.41
    assert normalized["ask"] == 0.43
    assert normalized["mid_price"] == 0.42
    assert normalized["volume"] == 123.45
    assert normalized["open_interest"] == 10


def test_first_outcome_price_reads_gamma_json_string():
    assert first_outcome_price({"outcomePrices": '["0.12", "0.88"]'}) == 0.12
