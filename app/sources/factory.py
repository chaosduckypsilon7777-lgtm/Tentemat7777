import httpx

from app.sources.base import Connector, SourceConfig
from app.sources.fred import FredConnector
from app.sources.gdelt import GdeltConnector
from app.sources.polymarket import PolymarketConnector
from app.sources.rss import RssConnector
from app.sources.sec_edgar import SecEdgarConnector


def build_connector(source: SourceConfig, client: httpx.AsyncClient) -> Connector:
    connectors = {
        "polymarket_clob": PolymarketConnector,
        "gdelt": GdeltConnector,
        "fred": FredConnector,
        "sec_edgar": SecEdgarConnector,
        "rss_official": RssConnector,
    }
    connector_type = connectors.get(source.name)
    if connector_type is None:
        raise ValueError(f"No connector registered for source: {source.name}")
    return connector_type(source, client)

