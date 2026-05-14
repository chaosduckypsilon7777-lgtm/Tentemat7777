from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.normalizers.factory import normalize_payload
from app.normalizers.market_normalizer import normalize_market
from app.scoring.scorer import SIGNAL_THRESHOLD, score_market_data, score_normalized_item
from app.sources.base import SourceConfig, SourceConfigurationError
from app.sources.factory import build_connector
from app.storage.models import FetchLog, MarketData, NormalizedItem, RawItem, Signal, Source
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


_source_cooldowns: dict[str, datetime] = {}
_DEFAULT_COOLDOWN_SECONDS = 300


class FetchingEngine:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()

    async def fetch_source(self, source_config: SourceConfig) -> dict[str, int | str]:
        cooldown_until = _source_cooldowns.get(source_config.name)
        if cooldown_until and datetime.now(UTC).replace(tzinfo=None) < cooldown_until:
            remaining = int((cooldown_until - datetime.now(UTC).replace(tzinfo=None)).total_seconds())
            return {"source": source_config.name, "status": "rate_limited", "items_fetched": 0, "cooldown_seconds": remaining}

        source = upsert_source(self.session, source_config)
        started = datetime.now(UTC).replace(tzinfo=None)
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
            cooldown_secs = exc.retry_after_seconds or _DEFAULT_COOLDOWN_SECONDS
            _source_cooldowns[source_config.name] = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=cooldown_secs)
        except SourceConfigurationError as exc:
            inserted = 0
            status = "needs_config"
            error_message = str(exc)
        except Exception as exc:
            inserted = 0
            status = "error"
            error_message = str(exc)

        log.finished_at = datetime.now(UTC).replace(tzinfo=None)
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
                    retry_after = self._parse_retry_after(exc.response.headers.get("Retry-After"))
                    if attempt == self.settings.fetch_retry_attempts - 1:
                        raise RateLimitError(source_config.name, retry_after) from exc
                    cooldown = retry_after if retry_after is not None else min(
                        self.settings.fetch_backoff_seconds * 2 ** attempt, 60.0
                    )
                    await asyncio.sleep(cooldown)
            except SourceConfigurationError:
                raise
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(self.settings.fetch_backoff_seconds * (attempt + 1))
        raise RuntimeError(f"Fetch failed for {source_config.name}: {last_error}") from last_error

    def _store_records(self, source: Source, source_config: SourceConfig, records) -> int:
        inserted = 0
        for record in records:
            payload_hash = stable_hash(record.payload)
            dedup = RawItem.hash == payload_hash
            if record.external_id:
                dedup = or_(dedup, RawItem.external_id == record.external_id)
            exists = self.session.scalar(
                select(RawItem.id).where(RawItem.source_id == source.id, dedup)
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

            try:
                if source_config.category == "market":
                    md = MarketData(source_id=source.id, **normalize_market(record.payload))
                    self.session.add(md)
                    self.session.flush()
                    sig = self._score_market(source, md, record.payload, source_config.name)
                    if sig:
                        self.session.add(sig)
                else:
                    normalized = normalize_payload(record.payload, source_config)
                    if normalized and self._is_valid_normalized(normalized.title, normalized.url):
                        ni = NormalizedItem(
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
                        self.session.add(ni)
                        self.session.flush()
                        sig = self._score_item(source, ni, normalized, source_config.name)
                        if sig:
                            self.session.add(sig)
                self.session.commit()
                inserted += 1
            except IntegrityError:
                self.session.rollback()
        return inserted

    @staticmethod
    def _is_valid_normalized(title: str | None, url: str | None) -> bool:
        return bool(title or url)

    @staticmethod
    def _score_market(source: Source, md: MarketData, payload: dict, source_name: str) -> Signal | None:
        result = score_market_data(source_name, md.volume, md.spread)
        if not result or result.score < SIGNAL_THRESHOLD:
            return None
        slug = payload.get("slug")
        return Signal(
            source_id=source.id,
            market_data_id=md.id,
            score=result.score,
            signal_type=result.signal_type,
            title=payload.get("question") or slug,
            url=f"https://polymarket.com/event/{slug}" if slug else None,
            score_reason={"rules": result.reasons},
        )

    @staticmethod
    def _score_item(source: Source, ni: NormalizedItem, normalized, source_name: str) -> Signal | None:
        result = score_normalized_item(source_name, ni.item_type, normalized.metadata)
        if not result or result.score < SIGNAL_THRESHOLD:
            return None
        return Signal(
            source_id=source.id,
            normalized_item_id=ni.id,
            score=result.score,
            signal_type=result.signal_type,
            title=ni.title,
            url=ni.url,
            score_reason={"rules": result.reasons},
        )

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
