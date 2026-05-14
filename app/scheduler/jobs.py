import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.fetchers.engine import FetchingEngine
from app.sources.registry import load_sources
from app.storage.postgres import SessionLocal

logger = logging.getLogger(__name__)


def run_source_job(source_name: str) -> None:
    sources = load_sources()
    source = sources[source_name]
    with SessionLocal() as session:
        result = asyncio.run(FetchingEngine(session).fetch_source(source))
        logger.info("source fetched", extra=result)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    for source in load_sources().values():
        scheduler.add_job(
            run_source_job,
            "interval",
            seconds=source.interval_seconds,
            args=[source.name],
            id=f"fetch:{source.name}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    return scheduler

