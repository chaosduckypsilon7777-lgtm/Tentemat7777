from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from app.fetchers.engine import FetchingEngine
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
