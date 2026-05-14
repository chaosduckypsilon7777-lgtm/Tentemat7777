from app.sources.base import HttpConnector, RawRecord


class PolymarketConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        data = await self.get_json("/markets", params={"limit": 100})
        markets = data if isinstance(data, list) else data.get("data", [])
        return [
            RawRecord(
                external_id=str(item.get("condition_id") or item.get("id") or item.get("question")),
                payload=item,
                url=item.get("url"),
            )
            for item in markets
        ]

