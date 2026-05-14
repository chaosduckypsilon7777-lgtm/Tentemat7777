from app.config.settings import get_settings
from app.sources.base import HttpConnector, RawRecord


class FredConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        settings = get_settings()
        records: list[RawRecord] = []
        for series_id in self.source.metadata.get("series", []):
            params = {
                "series_id": series_id,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 5,
            }
            if settings.fred_api_key:
                params["api_key"] = settings.fred_api_key
            data = await self.get_json("/series/observations", params=params)
            for observation in data.get("observations", []):
                observation["series_id"] = series_id
                records.append(
                    RawRecord(
                        external_id=f"{series_id}:{observation.get('date')}",
                        payload=observation,
                    )
                )
        return records

