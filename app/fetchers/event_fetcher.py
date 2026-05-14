from sqlalchemy.orm import Session

from app.fetchers.engine import FetchingEngine
from app.sources.base import SourceConfig


async def fetch_event(session: Session, source: SourceConfig):
    return await FetchingEngine(session).fetch_source(source)

