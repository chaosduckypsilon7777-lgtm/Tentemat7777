from app.config.settings import get_settings
from app.sources.base import HttpConnector, RawRecord


def sec_filing_url(cik: str, accession_number: str, primary_document: str | None) -> str:
    cik_path = str(int(cik))
    accession_path = accession_number.replace("-", "")
    if primary_document:
        return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/{primary_document}"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/"


class SecEdgarConnector(HttpConnector):
    async def fetch(self) -> list[RawRecord]:
        cik = self.source.metadata.get("cik", "0000320193")
        data = await self.get_json(
            f"/submissions/CIK{cik}.json",
            headers={"User-Agent": get_settings().sec_user_agent},
        )
        entity_name = data.get("name")
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_documents = recent.get("primaryDocument", [])
        records = []
        for index, accession in enumerate(accession_numbers[:50]):
            primary_document = (
                primary_documents[index] if index < len(primary_documents) else None
            )
            url = sec_filing_url(cik, accession, primary_document)
            records.append(
                RawRecord(
                    external_id=accession,
                    payload={
                        "cik": cik,
                        "entity_name": entity_name,
                        "accession_number": accession,
                        "form": forms[index] if index < len(forms) else None,
                        "filing_date": filing_dates[index] if index < len(filing_dates) else None,
                        "primary_document": primary_document,
                        "url": url,
                    },
                    url=url,
                )
            )
        return records
