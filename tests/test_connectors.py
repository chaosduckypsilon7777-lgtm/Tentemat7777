import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.sources.base import SourceConfig
from app.sources.polymarket import PolymarketConnector
from app.sources.rss import RssConnector
from app.sources.sec_edgar import SecEdgarConnector, sec_filing_url


# ── helpers ──────────────────────────────────────────────────────────────────

def _mock_client(response_body, status_code=200, is_json=True):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = {}
    if is_json:
        response.json.return_value = response_body
    else:
        response.text = response_body
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    return client


def _source(name, base_url, **meta):
    return SourceConfig(name=name, type="api", category="news", base_url=base_url, metadata=meta)


# ── Polymarket ────────────────────────────────────────────────────────────────

POLY_MARKET = {
    "conditionId": "0xabc123",
    "question": "Will BTC exceed $100k?",
    "slug": "btc-100k",
    "active": True,
    "closed": False,
}


def test_polymarket_parses_list_response():
    client = _mock_client([POLY_MARKET])
    source = _source("polymarket_clob", "https://gamma-api.polymarket.com", limit=1)
    records = asyncio.run(PolymarketConnector(source, client).fetch())

    assert len(records) == 1
    assert records[0].external_id == "0xabc123"
    assert records[0].url == "https://polymarket.com/event/btc-100k"
    assert records[0].payload["question"] == "Will BTC exceed $100k?"


def test_polymarket_parses_dict_response_with_data_key():
    client = _mock_client({"data": [POLY_MARKET]})
    source = _source("polymarket_clob", "https://gamma-api.polymarket.com")
    records = asyncio.run(PolymarketConnector(source, client).fetch())

    assert len(records) == 1
    assert records[0].external_id == "0xabc123"


def test_polymarket_handles_empty_list():
    client = _mock_client([])
    source = _source("polymarket_clob", "https://gamma-api.polymarket.com")
    records = asyncio.run(PolymarketConnector(source, client).fetch())
    assert records == []


def test_polymarket_uses_question_as_fallback_external_id():
    market = {"question": "Will it rain?", "slug": "rain"}
    client = _mock_client([market])
    source = _source("polymarket_clob", "https://gamma-api.polymarket.com")
    records = asyncio.run(PolymarketConnector(source, client).fetch())
    assert records[0].external_id == "Will it rain?"


# ── RSS ───────────────────────────────────────────────────────────────────────

RSS_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>SEC Press Releases</title>
    <item>
      <title>SEC Charges Firm With Fraud</title>
      <link>https://www.sec.gov/news/press-release/2024-1</link>
      <description>The SEC today charged...</description>
      <pubDate>Wed, 14 May 2024 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>SEC Approves New Rules</title>
      <link>https://www.sec.gov/news/press-release/2024-2</link>
      <pubDate>Thu, 15 May 2024 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_rss_connector_returns_one_record_per_entry():
    client = _mock_client(RSS_FEED, is_json=False)
    source = SourceConfig(
        name="rss_official", type="rss", category="news",
        base_url="https://www.sec.gov/news/pressreleases.rss",
    )
    records = asyncio.run(RssConnector(source, client).fetch())

    assert len(records) == 2
    assert records[0].url == "https://www.sec.gov/news/press-release/2024-1"
    assert records[0].payload["title"] == "SEC Charges Firm With Fraud"


def test_rss_connector_uses_link_as_external_id():
    client = _mock_client(RSS_FEED, is_json=False)
    source = SourceConfig(
        name="rss_official", type="rss", category="news",
        base_url="https://www.sec.gov/news/pressreleases.rss",
    )
    records = asyncio.run(RssConnector(source, client).fetch())
    assert records[0].external_id == "https://www.sec.gov/news/press-release/2024-1"


# ── SEC Edgar ─────────────────────────────────────────────────────────────────

SEC_RESPONSE = {
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "form": ["10-K", "8-K"],
            "accessionNumber": ["0000320193-25-000079", "0000320193-25-000080"],
            "filingDate": ["2025-01-01", "2025-01-15"],
            "primaryDocument": ["aapl-20241231.htm", "d123456d8k.htm"],
        }
    },
}


def test_sec_edgar_returns_one_record_per_filing():
    from types import SimpleNamespace
    client = _mock_client(SEC_RESPONSE)
    source = SourceConfig(
        name="sec_edgar", type="api", category="event",
        base_url="https://data.sec.gov",
        metadata={"cik": "0000320193"},
    )

    import app.sources.sec_edgar as _sec
    original = _sec.get_settings
    _sec.get_settings = lambda: SimpleNamespace(sec_user_agent="test/1.0 test@test.com")

    try:
        records = asyncio.run(SecEdgarConnector(source, client).fetch())
    finally:
        _sec.get_settings = original

    assert len(records) == 2
    assert records[0].external_id == "0000320193-25-000079"
    assert records[0].payload["entity_name"] == "Apple Inc."
    assert records[0].payload["form"] == "10-K"


def test_sec_edgar_builds_archive_url():
    url = sec_filing_url("0000320193", "0000320193-25-000079", "aapl-20241231.htm")
    assert "Archives/edgar/data/320193" in url
    assert "000032019325000079" in url
    assert url.endswith("aapl-20241231.htm")


def test_sec_edgar_url_without_primary_document():
    url = sec_filing_url("0000320193", "0000320193-25-000079", None)
    assert url.endswith("/")
