# Information Engine

Silnik pozyskiwania i normalizacji danych zewnętrznych dla agenta analitycznego. Pobiera dane z pięciu źródeł, zapisuje surowe odpowiedzi, normalizuje, deduplikuje i udostępnia przez wewnętrzne API z dashboardem.

## Źródła danych

| Źródło | Typ | Interwał | Wymaga klucza |
|---|---|---|---|
| Polymarket | dane rynkowe | 10 s | nie |
| GDELT | newsy | 5 min | nie |
| FRED | makro (Fed, CPI, UNRATE) | 1 dzień | tak — FRED_API_KEY |
| SEC EDGAR | eventy (filingi) | 1 godz. | nie (wymaga User-Agent) |
| RSS (SEC) | newsy | 10 min | nie |

## Wymagania

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (menadżer pakietów)

## Uruchomienie lokalne

### 1. Sklonuj i przejdź do katalogu

```bash
git clone https://github.com/chaosduckypsilon7777-lgtm/Tentemat7777.git
cd Tentemat7777
```

### 2. Skonfiguruj środowisko

```bash
cp .env.example .env
```

Otwórz `.env` i ustaw:
- `FRED_API_KEY` — darmowy klucz z [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)
- `SEC_USER_AGENT` — zmień e-mail na swój (wymóg SEC)

### 3. Uruchom API

```bash
uv run uvicorn app.api.main:app --reload
```

Dashboard dostępny pod `http://localhost:8000`.

Przy pierwszym starcie aplikacja automatycznie tworzy bazę SQLite i tabele.

### 4. Uruchom testy

```bash
uv run --with pytest pytest tests/ -v
```

## Struktura danych

```
sources          — rejestr skonfigurowanych źródeł
raw_items        — surowe odpowiedzi API (deduplikacja po hash + external_id)
normalized_items — znormalizowane rekordy: news, event, macro
market_data      — dane rynkowe (Polymarket)
fetch_logs       — historia każdego fetcha: status, czas, błąd
```

## API

| Endpoint | Opis |
|---|---|
| `GET /` | Dashboard (HTML) |
| `GET /health` | Stan API, bazy i schedulera |
| `GET /sources` | Lista źródeł |
| `GET /sources/stats` | Źródła z licznikiem rekordów i ostatnim fetchem |
| `POST /fetch/{source}` | Ręczne pobranie jednego źródła |
| `GET /items` | Znormalizowane rekordy (news, event, macro) |
| `GET /market-data` | Dane rynkowe |
| `GET /fetch-logs` | Historia pobierań |
| `GET /dashboard/summary` | Statystyki zbiorcze |

### Parametry `/items`

```
?source=gdelt      filtruj po źródle
?item_type=macro   filtruj po typie (news / event / macro)
?q=inflation       szukaj w tytule
?limit=50          max rekordów (domyślnie 50, max 200)
```

## Docker (PostgreSQL + Redis)

```bash
docker-compose up -d
```

Następnie w `.env` zmień:

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/information_engine
```

## Konfiguracja źródeł

Źródła są zdefiniowane w `app/config/sources.yaml`. Każde źródło ma:
- `enabled` — włącz/wyłącz bez usuwania z konfiguracji
- `interval_seconds` — jak często scheduler pobiera dane
- `rate_limit_per_minute` — informacyjny (engine pilnuje backoffu samodzielnie)
- `metadata` — parametry specyficzne dla źródła (query, series, cik itp.)
