import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from app.config.settings import get_settings
from app.fetchers.engine import FetchingEngine
from app.normalizers.event_normalizer import normalize_event
from app.normalizers.macro_normalizer import normalize_macro
from app.normalizers.market_normalizer import first_outcome_price, normalize_market
from app.normalizers.news_normalizer import _strip_html, normalize_news
from app.sources.base import SourceConfig, SourceConfigurationError
from app.sources.fred import FredConnector
from app.sources.sec_edgar import sec_filing_url
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


def test_sec_filing_url_uses_archive_path():
    assert (
        sec_filing_url("0000320193", "0000320193-25-000079", "aapl-20250927.htm")
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
    )


def test_normalize_sec_event_title_is_readable():
    normalized = normalize_event(
        {
            "entity_name": "Apple Inc.",
            "form": "10-K",
            "accession_number": "0000320193-25-000079",
            "url": "https://www.sec.gov/example",
        },
        "sec_edgar",
    )

    assert normalized.title == "SEC 10-K: Apple Inc. (0000320193-25-000079)"
    assert normalized.url == "https://www.sec.gov/example"


def test_fred_requires_api_key(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("app.sources.fred.get_settings", lambda: SimpleNamespace(fred_api_key=None))
    source = SourceConfig(
        name="fred",
        type="api",
        category="macro",
        base_url="https://api.stlouisfed.org/fred",
        metadata={"series": ["FEDFUNDS"]},
    )

    with pytest.raises(SourceConfigurationError, match="FRED_API_KEY"):
        asyncio.run(FredConnector(source, client=None).fetch())


def test_fetch_retry_does_not_wrap_configuration_errors(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("app.sources.fred.get_settings", lambda: SimpleNamespace(fred_api_key=None))
    engine = FetchingEngine(session=None)
    source = SourceConfig(
        name="fred",
        type="api",
        category="macro",
        base_url="https://api.stlouisfed.org/fred",
        metadata={"series": ["FEDFUNDS"]},
    )

    with pytest.raises(SourceConfigurationError, match="FRED_API_KEY"):
        asyncio.run(engine._fetch_with_retry(source))


def test_normalize_macro_uses_human_readable_label():
    result = normalize_macro({"series_id": "FEDFUNDS", "date": "2026-04-01", "value": "3.64"}, "fred")
    assert result.title == "Federal Funds Rate — 2026-04-01"
    assert result.metadata["series_url"] == "https://fred.stlouisfed.org/series/FEDFUNDS"
    assert result.item_type == "macro"


def test_normalize_macro_falls_back_to_series_id_for_unknown():
    result = normalize_macro({"series_id": "CUSTOM123", "date": "2026-01-01", "value": "42"}, "fred")
    assert result.title == "CUSTOM123 — 2026-01-01"


def test_strip_html_removes_tags_and_collapses_whitespace():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("  <a href='x'>link</a>  text  ") == "link text"
    assert _strip_html("no tags here") == "no tags here"


def test_build_scheduler_staggers_first_runs():
    from datetime import UTC, datetime

    from app.scheduler.jobs import _STAGGER_SECONDS, build_scheduler

    scheduler = build_scheduler()
    jobs = scheduler.get_jobs()
    assert len(jobs) > 1
    run_times = sorted(j.next_run_time for j in jobs)
    gap = (run_times[-1] - run_times[0]).total_seconds()
    assert gap >= _STAGGER_SECONDS * (len(jobs) - 1) - 1  # allow 1s tolerance


def test_normalize_news_strips_html_from_rss_summary():
    payload = {
        "title": "SEC Proposes New Rules",
        "summary": "<p>The SEC today proposed <a href='...'>new rules</a> for disclosure.</p>",
        "link": "https://www.sec.gov/news/1",
    }
    result = normalize_news(payload, "rss_official")
    assert "<" not in (result.content or "")
    assert "new rules" in (result.content or "")
