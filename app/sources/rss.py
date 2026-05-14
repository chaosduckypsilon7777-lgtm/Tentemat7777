import feedparser

from app.sources.base import HttpConnector, RawRecord


class RssConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        response = await self.client.get(self.source.base_url)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        return [
            RawRecord(
                external_id=entry.get("id") or entry.get("link"),
                payload=dict(entry),
                url=entry.get("link"),
            )
            for entry in feed.entries
        ]

