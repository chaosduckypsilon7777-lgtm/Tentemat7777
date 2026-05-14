from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class SourceConfig:
    name: str
    type: str
    category: str
    base_url: str
    enabled: bool = True
    interval_seconds: int = 300
    rate_limit_per_minute: int | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawRecord:
    external_id: str | None
    payload: dict[str, Any]
    url: str | None = None


class Connector(Protocol):
    source: SourceConfig

    async def fetch(self) -> list[RawRecord]:
        """Fetch raw records from the external source."""


class SourceConfigurationError(RuntimeError):
    pass


class HttpConnector:
    def __init__(self, source: SourceConfig, client: httpx.AsyncClient):
        self.source = source
        self.client = client

    async def get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.client.get(
            f"{self.source.base_url.rstrip('/')}/{path.lstrip('/')}",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
