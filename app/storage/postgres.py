from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.sources.base import SourceConfig
from app.storage.models import Base, Source


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    get_settings().database_url,
    connect_args=_connect_args(get_settings().database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def upsert_source(session: Session, config: SourceConfig) -> Source:
    source = session.scalar(select(Source).where(Source.name == config.name))
    if source is None:
        source = Source(name=config.name)
        session.add(source)
    source.type = config.type
    source.category = config.category
    source.base_url = config.base_url
    source.rate_limit = config.rate_limit_per_minute
    source.is_active = config.enabled
    session.commit()
    session.refresh(source)
    return source

