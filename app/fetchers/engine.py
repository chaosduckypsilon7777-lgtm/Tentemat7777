from __future__ import annotations

import asyncio
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.normalizers.factory import normalize_payload
from app.normalizers.market_normalizer import normalize_market
from app.sources.base import SourceConfig
from app.sources.factory import build_connector
from app.storage.models import FetchLog, MarketData, NormalizedItem, RawItem, Source
from app.storage.postgres import upsert_source
from app.utils.hashing import stable_hash


class RateLimitError(RuntimeError):
    def __init__(self, source_name: str, retry_after_seconds: int | None):
        self.source_name = source_name
        self.retry_after_seconds = retry_after_seconds
        retry_hint = (
            f" Retry after {retry_after_seconds} seconds."
            if retry_after_seconds is not None
            else ""
        )
        super().__init__(f"Rate limited by {source_name}.{retry_hint}")


class FetchingEngine:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()

    async def fetch_source(self, source_config: SourceConfig) -> dict[str, int | str]:
        source = upsert_source(self.session, source_config)
        started = datetime.utcnow()
        log = FetchLog(source_id=source.id, started_at=started, status="running")
        self.session.add(log)
        self.session.commit()

        start_time = time.perf_counter()
        try:
            records = await self._fetch_with_retry(source_config)
            inserted = self._store_records(source, source_config, records)
            status = "success"
            error_message = None
        except RateLimitError as exc:
            inserted = 0
            status = "rate_limited"
            error_message = str(exc)
        except Exception as exc:
            inserted = 0
            status = "error"
            error_message = str(exc)

        log.finished_at = datetime.utcnow()
        log.status = status
        log.items_fetched = inserted
        log.error_message = error_message
        log.latency_ms = int((time.perf_counter() - start_time) * 1000)
        self.session.commit()
        return {"source": source_config.name, "status": status, "items_fetched": inserted}

    async def _fetch_with_retry(self, source_config: SourceConfig):
        last_error: Exception | None = None
        for attempt in range(self.settings.fetch_retry_attempts):
            try:
                timeout = httpx.Timeout(self.settings.http_timeout_seconds)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    connector = build_connector(source_config, client)
                    return await connector.fetch()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code == 429:
                    delay = self._parse_retry_after(exc.response.headers.get("Retry-After"))
                    raise RateLimitError(source_config.name, delay) from exc
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(self.settings.fetch_backoff_seconds * (attempt + 1))
        raise RuntimeError(f"Fetch failed for {source_config.name}: {last_error}") from last_error

    def _store_records(self, source: Source, source_config: SourceConfig, records) -> int:
        inserted = 0
        for record in records:
            payload_hash = stable_hash(record.payload)
            exists = self.session.scalar(
                select(RawItem.id).where(
                    RawItem.source_id == source.id,
                    RawItem.hash == payload_hash,
                )
            )
            if exists:
                continue

            raw_item = RawItem(
                source_id=source.id,
                external_id=record.external_id,
                raw_json=record.payload,
                hash=payload_hash,
            )
            self.session.add(raw_item)

            if source_config.category == "market":
                self.session.add(MarketData(source_id=source.id, **normalize_market(record.payload)))
            else:
                normalized = normalize_payload(record.payload, source_config)
                if normalized and self._is_valid_normalized(normalized.title, normalized.url):
                    self.session.add(
                        NormalizedItem(
                            source_id=source.id,
                            item_type=normalized.item_type,
                            title=normalized.title,
                            content=normalized.content,
                            url=normalized.url,
                            published_at=normalized.published_at,
                            language=normalized.language,
                            entities=normalized.entities,
                            metadata_=normalized.metadata,
                        )
                    )
            try:
                self.session.commit()
                inserted += 1
            except IntegrityError:
                self.session.rollback()
        return inserted

    @staticmethod
    def _is_valid_normalized(title: str | None, url: str | None) -> bool:
        return bool(title or url)

    @staticmethod
    def _parse_retry_after(value: str | None) -> int | None:
        if not value:
            return None
        if value.isdigit():
            return int(value)
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        delay = int((retry_at - datetime.now(retry_at.tzinfo)).total_seconds())
        return max(delay, 0)
