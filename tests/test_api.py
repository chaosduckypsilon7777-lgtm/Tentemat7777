"""FastAPI endpoint tests — use the api_client fixture from conftest.py."""
from datetime import UTC, datetime

import pytest

from app.storage.models import FetchLog, NormalizedItem, Source


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_ok(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert "scheduler" in body


def test_health_scheduler_reports_disabled(api_client):
    r = api_client.get("/health")
    assert r.json()["scheduler"] == "wyłączony"


# ── /sources ──────────────────────────────────────────────────────────────────

def test_sources_returns_configured_list(api_client):
    r = api_client.get("/sources")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert {"gdelt", "fred", "polymarket_clob", "sec_edgar", "rss_official"} == names


def test_sources_stats_has_record_count_field(api_client):
    r = api_client.get("/sources/stats")
    assert r.status_code == 200
    for row in r.json():
        assert "record_count" in row
        assert "last_status" in row
        assert "last_fetch_at" in row


# ── /items ────────────────────────────────────────────────────────────────────

def test_items_empty_initially(api_client):
    r = api_client.get("/items")
    assert r.status_code == 200
    assert r.json() == []


def test_items_filter_by_type_returns_subset(api_client, in_memory_engine):
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=in_memory_engine)
    with Session() as s:
        source = s.query(Source).filter_by(name="gdelt").first()
        s.add(NormalizedItem(
            source_id=source.id, item_type="news",
            title="Test headline", url="https://example.com/1",
        ))
        s.add(NormalizedItem(
            source_id=source.id, item_type="event",
            title="Test event", url="https://example.com/2",
        ))
        s.commit()

    r_news = api_client.get("/items?item_type=news")
    r_event = api_client.get("/items?item_type=event")
    assert all(row["item_type"] == "news" for row in r_news.json())
    assert all(row["item_type"] == "event" for row in r_event.json())


def test_items_search_filters_by_title(api_client):
    r = api_client.get("/items?q=headline")
    assert r.status_code == 200
    assert all("headline" in (row["title"] or "").lower() for row in r.json())


def test_items_limit_is_respected(api_client):
    r = api_client.get("/items?limit=1")
    assert r.status_code == 200
    assert len(r.json()) <= 1


# ── /market-data ──────────────────────────────────────────────────────────────

def test_market_data_empty_initially(api_client):
    r = api_client.get("/market-data")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── /fetch-logs ───────────────────────────────────────────────────────────────

def test_fetch_logs_returns_list(api_client):
    r = api_client.get("/fetch-logs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_fetch_logs_has_required_fields(api_client, in_memory_engine):
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=in_memory_engine)
    with Session() as s:
        source = s.query(Source).filter_by(name="fred").first()
        s.add(FetchLog(
            source_id=source.id,
            started_at=datetime.now(UTC).replace(tzinfo=None),
            status="success",
            items_fetched=3,
        ))
        s.commit()

    r = api_client.get("/fetch-logs?limit=1")
    row = r.json()[0]
    assert "source_name" in row
    assert "status" in row
    assert "items_fetched" in row


# ── /dashboard/summary ────────────────────────────────────────────────────────

def test_dashboard_summary_has_expected_keys(api_client):
    r = api_client.get("/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_records", "normalized_records", "market_records",
                "total_sources", "active_sources"):
        assert key in body


def test_dashboard_summary_counts_are_non_negative(api_client):
    body = api_client.get("/dashboard/summary").json()
    assert body["total_records"] >= 0
    assert body["active_sources"] >= 0
    assert body["total_sources"] == 5


# ── /fetch/{source} ───────────────────────────────────────────────────────────

def test_fetch_unknown_source_returns_404(api_client):
    r = api_client.post("/fetch/nonexistent_source_xyz")
    assert r.status_code == 404


# ── /item-types ───────────────────────────────────────────────────────────────

def test_item_types_returns_list(api_client):
    r = api_client.get("/item-types")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
