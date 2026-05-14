from app.sources.base import HttpConnector, RawRecord


class GdeltConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        data = await self.get_json(
            "/doc/doc",
            params={
                "query": self.source.metadata.get("query", "market OR economy OR election"),
                "mode": "ArtList",
                "format": "json",
                "maxrecords": self.source.metadata.get("maxrecords", 10),
                "sort": "DateDesc",
                "timespan": self.source.metadata.get("timespan", "15min"),
            },
        )
        articles = data.get("articles") or []
        return [
            RawRecord(
                external_id=article.get("url"),
                payload=article,
                url=article.get("url"),
            )
            for article in articles
        ]
