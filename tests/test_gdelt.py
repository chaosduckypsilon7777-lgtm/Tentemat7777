import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.fetchers.engine import FetchingEngine, RateLimitError
from app.normalizers.news_normalizer import parse_datetime
from app.sources.base import SourceConfig
from app.sources.gdelt import GdeltConnector


REAL_ARTICLE = {
    "url": "https://apnews.com/article/fed-rate-hike-inflation-abc123",
    "title": "Federal Reserve raises rates as inflation stays elevated",
    "seendate": "20240514T143000Z",
    "socialimage": "https://apnews.com/hub/img/fed.jpg",
    "domain": "apnews.com",
    "language": "English",
    "sourcecountry": "United States",
}


def _gdelt_source(**overrides):
    params = dict(
        name="gdelt",
        type="api",
        category="news",
        base_url="https://api.gdeltproject.org/api/v2",
        metadata={"query": "economy OR inflation", "maxrecords": 5, "timespan": "15min"},
    )
    params.update(overrides)
    return SourceConfig(**params)


def _mock_client(response_json, status_code=200, response_headers=None):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = response_headers or {}
    response.json.return_value = response_json
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    return client


def test_gdelt_returns_records_from_real_shaped_response():
    client = _mock_client({"articles": [REAL_ARTICLE]})
    connector = GdeltConnector(_gdelt_source(), client)

    records = asyncio.run(connector.fetch())

    assert len(records) == 1
    assert records[0].external_id == REAL_ARTICLE["url"]
    assert records[0].url == REAL_ARTICLE["url"]
    assert records[0].payload["title"] == REAL_ARTICLE["title"]
    assert records[0].payload["language"] == "English"


def test_gdelt_sends_dateesc_sort_and_timespan():
    client = _mock_client({"articles": [REAL_ARTICLE]})
    source = _gdelt_source(metadata={"query": "election", "maxrecords": 5, "timespan": "1h"})
    connector = GdeltConnector(source, client)

    asyncio.run(connector.fetch())

    params = client.get.call_args.kwargs["params"]
    assert params["sort"] == "DateDesc"
    assert params["timespan"] == "1h"
    assert params["query"] == "election"


def test_gdelt_handles_null_articles_without_error():
    for payload in [{"articles": None}, {}]:
        client = _mock_client(payload)
        connector = GdeltConnector(_gdelt_source(), client)
        records = asyncio.run(connector.fetch())
        assert records == []


def test_engine_backs_off_on_429_before_final_raise(monkeypatch):
    """On 429, engine sleeps and retries; raises RateLimitError only after all attempts."""
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    response_429 = MagicMock(spec=httpx.Response)
    response_429.status_code = 429
    response_429.headers = {}
    response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=response_429
    )

    mock_client_instance = MagicMock()
    mock_client_instance.get = AsyncMock(return_value=response_429)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    async def always_429(self):
        raise httpx.HTTPStatusError("429", request=MagicMock(), response=response_429)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr("app.fetchers.engine.build_connector", lambda *a, **kw: MagicMock(fetch=always_429.__get__(MagicMock(), type(MagicMock()))))

    # patch build_connector to return connector whose fetch() always raises 429
    call_count = 0

    async def raising_fetch():
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError("429", request=MagicMock(), response=response_429)

    connector_mock = MagicMock()
    connector_mock.fetch = raising_fetch
    monkeypatch.setattr("app.fetchers.engine.build_connector", lambda *a, **kw: connector_mock)

    engine = FetchingEngine(session=None)
    source = _gdelt_source()

    with pytest.raises(RateLimitError):
        asyncio.run(engine._fetch_with_retry(source))

    assert len(slept) > 0, "engine must sleep between 429 retries"
    assert call_count == engine.settings.fetch_retry_attempts


def test_parse_datetime_handles_gdelt_compact_format():
    result = parse_datetime("20240514T143000Z")
    assert result == datetime(2024, 5, 14, 14, 30, 0)


def test_parse_datetime_handles_iso_format():
    result = parse_datetime("2024-05-14T14:30:00Z")
    assert result == datetime(2024, 5, 14, 14, 30, 0)


def test_parse_datetime_returns_none_for_empty():
    assert parse_datetime(None) is None
    assert parse_datetime("") is None


def test_gdelt_url_dedup_skips_same_url_different_payload(monkeypatch):
    """Two records with the same URL but different payload should be stored only once."""
    stored = []
    committed = []

    class FakeQuery:
        def where(self, *a): return self
        def __iter__(self): return iter([])

    class FakeSession:
        def scalar(self, q): return 1 if stored else None
        def add(self, obj): stored.append(obj)
        def flush(self): pass
        def commit(self): committed.append(1)
        def rollback(self): pass
        def scalars(self, q): return FakeQuery()
        def execute(self, q): return FakeQuery()

    from app.fetchers.engine import FetchingEngine
    from app.sources.base import RawRecord, SourceConfig
    from app.storage.models import Source

    source_config = _gdelt_source()
    source_orm = MagicMock(spec=Source)
    source_orm.id = 1

    engine = FetchingEngine(session=FakeSession())

    article_url = "https://apnews.com/article/abc123"
    records = [
        RawRecord(external_id=article_url, payload={"url": article_url, "title": "Article", "shares": 10}, url=article_url),
        RawRecord(external_id=article_url, payload={"url": article_url, "title": "Article", "shares": 99}, url=article_url),
    ]

    inserted = engine._store_records(source_orm, source_config, records)

    assert inserted == 1, "duplicate URL should be stored only once"


def test_engine_uses_retry_after_header_as_cooldown(monkeypatch):
    """Retry-After header value is used as sleep duration on 429."""
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    response_429 = MagicMock(spec=httpx.Response)
    response_429.status_code = 429
    response_429.headers = {"Retry-After": "30"}
    response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=response_429
    )

    async def raising_fetch():
        raise httpx.HTTPStatusError("429", request=MagicMock(), response=response_429)

    connector_mock = MagicMock()
    connector_mock.fetch = raising_fetch
    monkeypatch.setattr("app.fetchers.engine.build_connector", lambda *a, **kw: connector_mock)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    engine = FetchingEngine(session=None)
    source = _gdelt_source()

    with pytest.raises(RateLimitError):
        asyncio.run(engine._fetch_with_retry(source))

    assert 30 in slept, "should have slept for Retry-After=30 seconds"
