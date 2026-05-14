# Information Engine

Silnik pozyskiwania informacji dla agenta analitycznego. Projekt obejmuje pobieranie danych ze zrodel zewnetrznych, zapis surowych odpowiedzi, normalizacje, walidacje, deduplikacje, monitoring i wewnetrzne API.

## Zakres MVP

- rejestr zrodel w `app/config/sources.yaml`,
- konektory: Polymarket, GDELT, FRED, SEC EDGAR i RSS,
- fetchery dla newsow, danych rynkowych, makro i eventow,
- zapis `sources`, `raw_items`, `normalized_items`, `market_data`, `fetch_logs`,
- deduplikacja po `external_id`, `url` i hashu tresci,
- wewnetrzne API FastAPI,
- scheduler APScheduler.

## Uruchomienie lokalne

1. Utworz srodowisko i zainstaluj zaleznosci:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

2. Skopiuj konfiguracje:

```bash
copy .env.example .env
```

3. Uruchom API:

```bash
uvicorn app.api.main:app --reload
```

Domyslnie projekt uzywa lokalnego pliku SQLite, zeby MVP startowalo bez infrastruktury. Dla PostgreSQL ustaw `DATABASE_URL` w `.env`.

## Przydatne endpointy

- `GET /health` - stan aplikacji,
- `GET /sources` - lista zrodel,
- `POST /fetch/{source_name}` - reczne pobranie jednego zrodla,
- `GET /items` - ostatnie znormalizowane rekordy,
- `GET /fetch-logs` - historia pobran.

## Infrastruktura

Plik `docker-compose.yml` zawiera PostgreSQL i Redis dla srodowiska docelowego. TimescaleDB mozna wlaczyc przez zamiane obrazu PostgreSQL na `timescale/timescaledb`.

