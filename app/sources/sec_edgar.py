from app.config.settings import get_settings
from app.sources.base import HttpConnector, RawRecord


class SecEdgarConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        cik = self.source.metadata.get("cik", "0000320193")
        data = await self.get_json(
            f"/submissions/CIK{cik}.json",
            headers={"User-Agent": get_settings().sec_user_agent},
        )
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        records = []
        for index, accession in enumerate(accession_numbers[:50]):
            records.append(
                RawRecord(
                    external_id=accession,
                    payload={
                        "cik": cik,
                        "accession_number": accession,
                        "form": forms[index] if index < len(forms) else None,
                        "filing_date": filing_dates[index] if index < len(filing_dates) else None,
                    },
                )
            )
        return records

