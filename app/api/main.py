from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.fetchers.engine import FetchingEngine
from app.monitoring.healthcheck import database_health
from app.monitoring.logs import configure_logging
from app.scheduler.jobs import build_scheduler
from app.sources.registry import load_sources
from app.storage.models import FetchLog, NormalizedItem, Source
from app.storage.postgres import SessionLocal, get_session, init_db, upsert_source


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    sources = load_sources()
    with SessionLocal() as session:
        for source in sources.values():
            upsert_source(session, source)

    scheduler = None
    if get_settings().scheduler_enabled:
        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Information Engine", version="0.1.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Information Engine</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #65708a;
      --line: #dce3ef;
      --blue: #1f6feb;
      --green: #16833a;
      --red: #c93c37;
      --amber: #a15c00;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      padding: 22px 28px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
    main { padding: 22px 28px 36px; }
    .grid {
      display: grid;
      grid-template-columns: 1.1fr 1fr;
      gap: 18px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .section-head {
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    h2 { margin: 0; font-size: 15px; }
    .status {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 5px 9px;
      border-radius: 8px;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      background: #fbfcff;
    }
    .ok { color: var(--green); }
    .error { color: var(--red); }
    .warn { color: var(--amber); }
    button {
      border: 1px solid #b8c8e6;
      background: #edf4ff;
      color: #123b75;
      border-radius: 8px;
      min-height: 32px;
      padding: 6px 10px;
      font: inherit;
      cursor: pointer;
    }
    button:disabled { opacity: .55; cursor: progress; }
    .content { padding: 12px 16px 16px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      padding: 9px 8px;
      border-bottom: 1px solid #edf1f7;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 600; }
    tr:last-child td { border-bottom: 0; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .wide { grid-column: 1 / -1; }
    a { color: var(--blue); text-decoration: none; }
    .muted { color: var(--muted); }
    .title-cell { max-width: 640px; }
    @media (max-width: 900px) {
      header { align-items: flex-start; flex-direction: column; }
      main { padding: 14px; }
      .grid { grid-template-columns: 1fr; }
      .wide { grid-column: auto; }
      table { font-size: 12px; }
      th, td { padding: 8px 6px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Information Engine</h1>
      <div class="muted">Silnik pobierania, normalizacji i kontroli danych</div>
    </div>
    <div id="health" class="status">Sprawdzanie...</div>
  </header>

  <main class="grid">
    <section>
      <div class="section-head">
        <h2>Zrodla</h2>
        <button onclick="loadAll()">Odswiez</button>
      </div>
      <div class="content">
        <div id="sourceActions" class="actions"></div>
        <table>
          <thead><tr><th>Nazwa</th><th>Kategoria</th><th>Status</th></tr></thead>
          <tbody id="sources"></tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Logi pobran</h2>
        <span id="lastRun" class="status">-</span>
      </div>
      <div class="content">
        <table>
          <thead><tr><th>Zrodlo</th><th>Status</th><th>Rekordy</th><th>Czas</th></tr></thead>
          <tbody id="logs"></tbody>
        </table>
      </div>
    </section>

    <section class="wide">
      <div class="section-head">
        <h2>Ostatnie rekordy</h2>
        <span class="status">normalized_items</span>
      </div>
      <div class="content">
        <table>
          <thead><tr><th>Typ</th><th>Tytul</th><th>Publikacja</th><th>Zrodlo</th></tr></thead>
          <tbody id="items"></tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const sourceNames = new Map();

    async function api(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    function fmtDate(value) {
      if (!value) return "-";
      return new Date(value).toLocaleString("pl-PL");
    }

    async function loadHealth() {
      const el = document.getElementById("health");
      try {
        const data = await api("/health");
        el.textContent = `API: ${data.status}, baza: ${data.database}`;
        el.className = "status ok";
      } catch (error) {
        el.textContent = "API niedostepne";
        el.className = "status error";
      }
    }

    async function loadSources() {
      const rows = await api("/sources");
      const body = document.getElementById("sources");
      const actions = document.getElementById("sourceActions");
      body.innerHTML = "";
      actions.innerHTML = "";
      sourceNames.clear();
      for (const row of rows) {
        sourceNames.set(row.id, row.name);
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td>${row.name}</td>
            <td>${row.category}</td>
            <td class="${row.is_active ? "ok" : "warn"}">${row.is_active ? "aktywne" : "wylaczone"}</td>
          </tr>
        `);
        const button = document.createElement("button");
        button.textContent = `Pobierz ${row.name}`;
        button.onclick = () => fetchSource(row.name, button);
        actions.appendChild(button);
      }
    }

    async function fetchSource(name, button) {
      button.disabled = true;
      button.textContent = `Pobieram ${name}`;
      try {
        const result = await api(`/fetch/${name}`, { method: "POST" });
        document.getElementById("lastRun").textContent = `${result.source}: ${result.status}, ${result.items_fetched}`;
      } catch (error) {
        document.getElementById("lastRun").textContent = `${name}: blad`;
        document.getElementById("lastRun").className = "status error";
      } finally {
        button.disabled = false;
        button.textContent = `Pobierz ${name}`;
        await loadAll();
      }
    }

    async function loadLogs() {
      const rows = await api("/fetch-logs?limit=8");
      const body = document.getElementById("logs");
      body.innerHTML = "";
      for (const row of rows) {
        const statusClass = row.status === "success" ? "ok" : "error";
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td>${sourceNames.get(row.source_id) || row.source_id}</td>
            <td class="${statusClass}">${row.status}</td>
            <td>${row.items_fetched}</td>
            <td>${fmtDate(row.started_at)}</td>
          </tr>
        `);
      }
    }

    async function loadItems() {
      const rows = await api("/items?limit=20");
      const body = document.getElementById("items");
      body.innerHTML = "";
      for (const row of rows) {
        const title = row.url ? `<a href="${row.url}" target="_blank" rel="noreferrer">${row.title || row.url}</a>` : (row.title || "-");
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td>${row.item_type}</td>
            <td class="title-cell">${title}</td>
            <td>${fmtDate(row.published_at)}</td>
            <td>${sourceNames.get(row.source_id) || row.source_id}</td>
          </tr>
        `);
      }
    }

    async function loadAll() {
      await loadHealth();
      await loadSources();
      await loadLogs();
      await loadItems();
    }

    loadAll();
  </script>
</body>
</html>
"""


@app.get("/health")
def health(session: Session = Depends(get_session)):
    return {"status": "ok", **database_health(session)}


@app.get("/sources")
def list_sources(session: Session = Depends(get_session)):
    rows = session.scalars(select(Source).order_by(Source.category, Source.name)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "category": row.category,
            "base_url": row.base_url,
            "rate_limit": row.rate_limit,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@app.post("/fetch/{source_name}")
async def fetch_source(source_name: str, session: Session = Depends(get_session)):
    sources = load_sources()
    source = sources.get(source_name)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
    return await FetchingEngine(session).fetch_source(source)


@app.get("/items")
def list_items(limit: int = 50, session: Session = Depends(get_session)):
    limit = min(max(limit, 1), 200)
    rows = session.scalars(
        select(NormalizedItem).order_by(desc(NormalizedItem.retrieved_at)).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "source_id": row.source_id,
            "item_type": row.item_type,
            "title": row.title,
            "url": row.url,
            "published_at": row.published_at,
            "retrieved_at": row.retrieved_at,
            "language": row.language,
            "metadata": row.metadata_,
        }
        for row in rows
    ]


@app.get("/fetch-logs")
def list_fetch_logs(limit: int = 50, session: Session = Depends(get_session)):
    limit = min(max(limit, 1), 200)
    rows = session.scalars(select(FetchLog).order_by(desc(FetchLog.started_at)).limit(limit)).all()
    return [
        {
            "id": row.id,
            "source_id": row.source_id,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "status": row.status,
            "items_fetched": row.items_fetched,
            "error_message": row.error_message,
            "latency_ms": row.latency_ms,
        }
        for row in rows
    ]
