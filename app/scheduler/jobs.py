import asyncio
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.fetchers.engine import FetchingEngine
from app.sources.registry import load_sources
from app.storage.postgres import SessionLocal

logger = logging.getLogger(__name__)

_STAGGER_SECONDS = 15


def run_source_job(source_name: str) -> None:
    try:
        sources = load_sources()
        source = sources[source_name]
        with SessionLocal() as session:
            result = asyncio.run(FetchingEngine(session).fetch_source(source))
        logger.info(
            "fetch completed: %s  status=%s  items=%s",
            source_name,
            result["status"],
            result["items_fetched"],
        )
    except Exception:
        logger.exception("unhandled error in scheduled job for %s", source_name)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    sources = sorted(load_sources().values(), key=lambda s: s.priority, reverse=True)
    for i, source in enumerate(sources):
        scheduler.add_job(
            run_source_job,
            "interval",
            seconds=source.interval_seconds,
            args=[source.name],
            id=f"fetch:{source.name}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(UTC) + timedelta(seconds=i * _STAGGER_SECONDS),
        )
    return scheduler
