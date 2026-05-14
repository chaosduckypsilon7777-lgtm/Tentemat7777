from app.sources.base import HttpConnector, RawRecord


class PolymarketConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        data = await self.get_json(
            "/markets",
            params={
                "limit": self.source.metadata.get("limit", 100),
                "active": self.source.metadata.get("active", True),
                "closed": self.source.metadata.get("closed", False),
                "order": self.source.metadata.get("order", "volume24hr"),
                "ascending": self.source.metadata.get("ascending", False),
            },
        )
        markets = data if isinstance(data, list) else data.get("data", [])
        return [
            RawRecord(
                external_id=str(
                    item.get("conditionId")
                    or item.get("condition_id")
                    or item.get("id")
                    or item.get("question")
                ),
                payload=item,
                url=f"https://polymarket.com/event/{item['slug']}" if item.get("slug") else None,
            )
            for item in markets
        ]
