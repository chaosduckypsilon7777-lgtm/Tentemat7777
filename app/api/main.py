from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import String, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.fetchers.engine import FetchingEngine
from app.monitoring.healthcheck import database_health
from app.monitoring.logs import configure_logging
from app.normalizers.market_normalizer import first_outcome_price
from app.scheduler.jobs import build_scheduler
from app.sources.registry import load_sources
from app.storage.models import FetchLog, MarketData, NormalizedItem, RawItem, Source
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
      --soft: #fbfcff;
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
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .stat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px 14px;
      min-height: 86px;
    }
    .stat-label { color: var(--muted); font-size: 12px; font-weight: 600; }
    .stat-value { margin-top: 6px; font-size: 25px; font-weight: 750; }
    .stat-detail {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
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
      background: var(--soft);
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
    .filters {
      display: grid;
      grid-template-columns: minmax(160px, 1fr) minmax(140px, .8fr) minmax(220px, 1.4fr) auto;
      gap: 10px;
      align-items: end;
      margin-bottom: 12px;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    input, select {
      width: 100%;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--soft);
      color: var(--ink);
      padding: 6px 9px;
      font: inherit;
      font-size: 13px;
    }
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
    .market-cell { max-width: 520px; }
    .number-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
    .error-detail {
      display: block;
      max-width: 380px;
      margin-top: 3px;
      color: var(--muted);
      overflow-wrap: anywhere;
      max-height: 4.2em;
      overflow: hidden;
    }
    .empty {
      color: var(--muted);
      text-align: center;
      padding: 18px 8px;
    }
    @media (max-width: 900px) {
      header { align-items: flex-start; flex-direction: column; }
      main { padding: 14px; }
      .stats { grid-template-columns: 1fr 1fr; }
      .grid { grid-template-columns: 1fr; }
      .wide { grid-column: auto; }
      .filters { grid-template-columns: 1fr; }
      table { font-size: 12px; }
      th, td { padding: 8px 6px; }
    }
    @media (max-width: 560px) {
      .stats { grid-template-columns: 1fr; }
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

  <main>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Rekordy</div>
        <div id="totalRecords" class="stat-value">-</div>
        <div id="recordsDetail" class="stat-detail">raw_items</div>
      </div>
      <div class="stat">
        <div class="stat-label">Aktywne zrodla</div>
        <div id="activeSources" class="stat-value">-</div>
        <div id="sourcesTotal" class="stat-detail">sources</div>
      </div>
      <div class="stat">
        <div class="stat-label">Ostatni sukces</div>
        <div id="lastSuccess" class="stat-value">-</div>
        <div id="lastSuccessDetail" class="stat-detail">-</div>
      </div>
      <div class="stat">
        <div class="stat-label">Ostatni blad</div>
        <div id="lastError" class="stat-value">-</div>
        <div id="lastErrorDetail" class="stat-detail">-</div>
      </div>
    </div>

    <div class="grid">
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
          <thead><tr><th>Zrodlo</th><th>Status</th><th>Rekordy</th><th>Czas</th><th>Blad</th></tr></thead>
          <tbody id="logs"></tbody>
        </table>
      </div>
    </section>

    <section class="wide">
      <div class="section-head">
        <h2>Ostatnie rekordy</h2>
        <span id="itemsCount" class="status">normalized_items</span>
      </div>
      <div class="content">
        <div class="filters">
          <label>
            Zrodlo
            <select id="sourceFilter" onchange="loadItems()">
              <option value="">Wszystkie</option>
            </select>
          </label>
          <label>
            Typ
            <select id="typeFilter" onchange="loadItems()">
              <option value="">Wszystkie</option>
            </select>
          </label>
          <label>
            Szukaj w tytule
            <input id="searchFilter" type="search" placeholder="np. inflation, SEC, market" oninput="queueItemsLoad()">
          </label>
          <button onclick="resetFilters()">Wyczysc</button>
        </div>
        <table>
          <thead><tr><th>Typ</th><th>Tytul</th><th>Publikacja</th><th>Zrodlo</th></tr></thead>
          <tbody id="items"></tbody>
        </table>
      </div>
    </section>

    <section class="wide">
      <div class="section-head">
        <h2>Dane rynkowe</h2>
        <span id="marketsCount" class="status">market_data</span>
      </div>
      <div class="content">
        <div class="filters">
          <label>
            Zrodlo
            <select id="marketSourceFilter" onchange="loadMarkets()">
              <option value="">Wszystkie</option>
            </select>
          </label>
          <label>
            Szukaj rynku
            <input id="marketSearchFilter" type="search" placeholder="np. election, Fed, NBA" oninput="queueMarketsLoad()">
          </label>
          <button onclick="resetMarketFilters()">Wyczysc</button>
        </div>
        <table>
          <thead><tr><th>Rynek</th><th>Mid</th><th>Bid</th><th>Ask</th><th>Volume</th><th>Spread</th><th>Czas</th></tr></thead>
          <tbody id="markets"></tbody>
        </table>
      </div>
    </section>

    <section class="wide">
      <div class="section-head">
        <h2>Dane makro</h2>
        <span id="macroCount" class="status">normalized_items / macro</span>
      </div>
      <div class="content">
        <table>
          <thead><tr><th>Seria</th><th>Wartosc</th><th>Data</th><th>Zrodlo</th></tr></thead>
          <tbody id="macro"></tbody>
        </table>
      </div>
    </section>
    </div>
  </main>

  <script>
    const sourceNames = new Map();
    let itemSearchTimer = null;
    let marketSearchTimer = null;

    async function api(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    function fmtDate(value) {
      if (!value) return "-";
      return new Date(value).toLocaleString("pl-PL");
    }

    function escapeHTML(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function emptyRow(target, colspan, text) {
      target.innerHTML = `<tr><td class="empty" colspan="${colspan}">${escapeHTML(text)}</td></tr>`;
    }

    function setStat(id, value, detailId, detail) {
      document.getElementById(id).textContent = value;
      if (detailId) document.getElementById(detailId).textContent = detail || "-";
    }

    function fmtStatus(status) {
      const map = {
        success: "sukces",
        rate_limited: "limit zapytań",
        needs_config: "brak konfiguracji",
        error: "błąd",
        running: "w toku",
      };
      return map[status] || status;
    }

    function compactError(value) {
      if (!value) return "-";
      const firstLine = String(value).split("\\n")[0];
      if (firstLine.includes("429 Too Many Requests")) return "429 Too Many Requests";
      return firstLine.length > 140 ? `${firstLine.slice(0, 137)}...` : firstLine;
    }

    function fmtNumber(value) {
      if (value === null || value === undefined || value === "") return "-";
      return Number(value).toLocaleString("pl-PL", { maximumFractionDigits: 4 });
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

    async function loadSummary() {
      const data = await api("/dashboard/summary");
      setStat("totalRecords", data.total_records, "recordsDetail", `${data.normalized_records} normalized, ${data.market_records} market`);
      setStat("activeSources", data.active_sources, "sourcesTotal", `${data.total_sources} skonfigurowane`);

      if (data.last_success) {
        setStat("lastSuccess", fmtDate(data.last_success.finished_at || data.last_success.started_at), "lastSuccessDetail", data.last_success.source_name);
      } else {
        setStat("lastSuccess", "-", "lastSuccessDetail", "brak udanych pobran");
      }

      if (data.last_error) {
        setStat("lastError", fmtDate(data.last_error.finished_at || data.last_error.started_at), "lastErrorDetail", `${data.last_error.source_name}: ${data.last_error.error_message || data.last_error.status}`);
      } else {
        setStat("lastError", "-", "lastErrorDetail", "brak bledow");
      }
    }

    async function loadSources() {
      const rows = await api("/sources");
      const body = document.getElementById("sources");
      const actions = document.getElementById("sourceActions");
      const sourceFilter = document.getElementById("sourceFilter");
      const marketSourceFilter = document.getElementById("marketSourceFilter");
      const selectedSource = sourceFilter.value;
      const selectedMarketSource = marketSourceFilter.value;
      body.innerHTML = "";
      actions.innerHTML = "";
      sourceFilter.innerHTML = `<option value="">Wszystkie</option>`;
      marketSourceFilter.innerHTML = `<option value="">Wszystkie</option>`;
      sourceNames.clear();
      for (const row of rows) {
        sourceNames.set(row.id, row.name);
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td>${escapeHTML(row.name)}</td>
            <td>${escapeHTML(row.category)}</td>
            <td class="${row.is_active ? "ok" : "warn"}">${row.is_active ? "aktywne" : "wylaczone"}</td>
          </tr>
        `);
        sourceFilter.insertAdjacentHTML("beforeend", `<option value="${escapeHTML(row.name)}">${escapeHTML(row.name)}</option>`);
        if (row.category === "market") {
          marketSourceFilter.insertAdjacentHTML("beforeend", `<option value="${escapeHTML(row.name)}">${escapeHTML(row.name)}</option>`);
        }
        const button = document.createElement("button");
        button.textContent = `Pobierz ${row.name}`;
        button.onclick = () => fetchSource(row.name, button);
        actions.appendChild(button);
      }
      sourceFilter.value = [...sourceFilter.options].some((option) => option.value === selectedSource) ? selectedSource : "";
      marketSourceFilter.value = [...marketSourceFilter.options].some((option) => option.value === selectedMarketSource) ? selectedMarketSource : "";
      if (!rows.length) emptyRow(body, 3, "Brak zrodel");
    }

    async function loadItemTypes() {
      const rows = await api("/item-types");
      const typeFilter = document.getElementById("typeFilter");
      const selectedType = typeFilter.value;
      typeFilter.innerHTML = `<option value="">Wszystkie</option>`;
      for (const row of rows) {
        typeFilter.insertAdjacentHTML("beforeend", `<option value="${escapeHTML(row)}">${escapeHTML(row)}</option>`);
      }
      typeFilter.value = [...typeFilter.options].some((option) => option.value === selectedType) ? selectedType : "";
    }

    async function fetchSource(name, button) {
      button.disabled = true;
      button.textContent = `Pobieram ${name}`;
      try {
        const result = await api(`/fetch/${name}`, { method: "POST" });
        document.getElementById("lastRun").textContent = `${result.source}: ${fmtStatus(result.status)}, ${result.items_fetched} rekordów`;
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
        const statusClass = row.status === "success"
          ? "ok"
          : (["rate_limited", "needs_config"].includes(row.status) ? "warn" : "error");
        const errorText = row.error_message
          ? `<span class="error-detail" title="${escapeHTML(row.error_message)}">${escapeHTML(compactError(row.error_message))}</span>`
          : "-";
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td>${escapeHTML(row.source_name || sourceNames.get(row.source_id) || row.source_id)}</td>
            <td class="${statusClass}">${escapeHTML(fmtStatus(row.status))}</td>
            <td>${row.items_fetched}</td>
            <td>${fmtDate(row.started_at)}</td>
            <td>${errorText}</td>
          </tr>
        `);
      }
      if (!rows.length) emptyRow(body, 5, "Brak logow pobran");
    }

    async function loadItems() {
      const params = new URLSearchParams({ limit: "50" });
      const source = document.getElementById("sourceFilter").value;
      const itemType = document.getElementById("typeFilter").value;
      const query = document.getElementById("searchFilter").value.trim();
      if (source) params.set("source", source);
      if (itemType) params.set("item_type", itemType);
      if (query) params.set("q", query);

      const rows = await api(`/items?${params.toString()}`);
      const body = document.getElementById("items");
      body.innerHTML = "";
      for (const row of rows) {
        const safeTitle = escapeHTML(row.title || row.url || "-");
        const title = row.url ? `<a href="${escapeHTML(row.url)}" target="_blank" rel="noreferrer">${safeTitle}</a>` : safeTitle;
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td>${escapeHTML(row.item_type)}</td>
            <td class="title-cell">${title}</td>
            <td>${fmtDate(row.published_at)}</td>
            <td>${escapeHTML(row.source_name || sourceNames.get(row.source_id) || row.source_id)}</td>
          </tr>
        `);
      }
      document.getElementById("itemsCount").textContent = `${rows.length} rekordow`;
      if (!rows.length) emptyRow(body, 4, "Brak rekordow dla wybranych filtrow");
    }

    function queueItemsLoad() {
      clearTimeout(itemSearchTimer);
      itemSearchTimer = setTimeout(loadItems, 250);
    }

    function resetFilters() {
      document.getElementById("sourceFilter").value = "";
      document.getElementById("typeFilter").value = "";
      document.getElementById("searchFilter").value = "";
      loadItems();
    }

    async function loadMarkets() {
      const params = new URLSearchParams({ limit: "50" });
      const source = document.getElementById("marketSourceFilter").value;
      const query = document.getElementById("marketSearchFilter").value.trim();
      if (source) params.set("source", source);
      if (query) params.set("q", query);

      const rows = await api(`/market-data?${params.toString()}`);
      const body = document.getElementById("markets");
      body.innerHTML = "";
      for (const row of rows) {
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td class="market-cell">${escapeHTML(row.question || row.market_or_asset_id)}</td>
            <td class="number-cell">${fmtNumber(row.mid_price)}</td>
            <td class="number-cell">${fmtNumber(row.bid)}</td>
            <td class="number-cell">${fmtNumber(row.ask)}</td>
            <td class="number-cell">${fmtNumber(row.volume)}</td>
            <td class="number-cell">${fmtNumber(row.spread)}</td>
            <td>${fmtDate(row.timestamp)}</td>
          </tr>
        `);
      }
      document.getElementById("marketsCount").textContent = `${rows.length} rekordow`;
      if (!rows.length) emptyRow(body, 7, "Brak danych rynkowych dla wybranych filtrow");
    }

    function queueMarketsLoad() {
      clearTimeout(marketSearchTimer);
      marketSearchTimer = setTimeout(loadMarkets, 250);
    }

    function resetMarketFilters() {
      document.getElementById("marketSourceFilter").value = "";
      document.getElementById("marketSearchFilter").value = "";
      loadMarkets();
    }

    async function loadMacro() {
      const rows = await api("/items?item_type=macro&limit=100");
      const body = document.getElementById("macro");
      body.innerHTML = "";
      for (const row of rows) {
        const seriesId = row.metadata?.series_id || row.title?.split(" ")[0] || "-";
        const value = row.metadata?.value ?? row.content ?? "-";
        body.insertAdjacentHTML("beforeend", `
          <tr>
            <td><strong>${escapeHTML(seriesId)}</strong></td>
            <td class="number-cell">${escapeHTML(String(value))}</td>
            <td>${fmtDate(row.published_at)}</td>
            <td>${escapeHTML(row.source_name || "-")}</td>
          </tr>
        `);
      }
      document.getElementById("macroCount").textContent = `${rows.length} rekordow`;
      if (!rows.length) emptyRow(body, 4, "Brak danych makro");
    }

    async function loadAll() {
      await Promise.all([
        loadHealth(),
        loadSummary(),
        loadSources(),
        loadItemTypes(),
        loadLogs(),
        loadItems(),
        loadMarkets(),
        loadMacro(),
      ]);
    }

    loadAll();
    setInterval(loadAll, 30_000);
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


def _fetch_log_payload(row: FetchLog, source_name: str | None = None):
    return {
        "id": row.id,
        "source_id": row.source_id,
        "source_name": source_name,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "status": row.status,
        "items_fetched": row.items_fetched,
        "error_message": row.error_message,
        "latency_ms": row.latency_ms,
    }


@app.get("/dashboard/summary")
def dashboard_summary(session: Session = Depends(get_session)):
    total_records = session.scalar(select(func.count(RawItem.id))) or 0
    normalized_records = session.scalar(select(func.count(NormalizedItem.id))) or 0
    market_records = session.scalar(select(func.count(MarketData.id))) or 0
    total_sources = session.scalar(select(func.count(Source.id))) or 0
    active_sources = session.scalar(
        select(func.count(Source.id)).where(Source.is_active.is_(True))
    ) or 0

    last_success = session.execute(
        select(FetchLog, Source.name)
        .join(Source, FetchLog.source_id == Source.id)
        .where(FetchLog.status == "success")
        .order_by(desc(FetchLog.finished_at), desc(FetchLog.started_at))
        .limit(1)
    ).first()
    last_error = session.execute(
        select(FetchLog, Source.name)
        .join(Source, FetchLog.source_id == Source.id)
        .where(FetchLog.status.not_in(["success", "running"]))
        .order_by(desc(FetchLog.finished_at), desc(FetchLog.started_at))
        .limit(1)
    ).first()

    return {
        "total_records": total_records,
        "normalized_records": normalized_records,
        "market_records": market_records,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "last_success": _fetch_log_payload(*last_success) if last_success else None,
        "last_error": _fetch_log_payload(*last_error) if last_error else None,
    }


@app.post("/fetch/{source_name}")
async def fetch_source(source_name: str, session: Session = Depends(get_session)):
    sources = load_sources()
    source = sources.get(source_name)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
    return await FetchingEngine(session).fetch_source(source)


@app.get("/items")
def list_items(
    limit: int = 50,
    source: str | None = None,
    item_type: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
):
    limit = min(max(limit, 1), 200)
    query = select(NormalizedItem, Source.name).join(Source, NormalizedItem.source_id == Source.id)

    if source:
        source_filter = Source.name == source
        if source.isdigit():
            source_filter = or_(source_filter, Source.id == int(source))
        query = query.where(source_filter)
    if item_type:
        query = query.where(NormalizedItem.item_type == item_type)
    if q:
        query = query.where(NormalizedItem.title.ilike(f"%{q}%"))

    rows = session.execute(
        query.order_by(desc(NormalizedItem.retrieved_at)).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "source_id": row.source_id,
            "source_name": source_name,
            "item_type": row.item_type,
            "title": row.title,
            "url": row.url,
            "published_at": row.published_at,
            "retrieved_at": row.retrieved_at,
            "language": row.language,
            "metadata": row.metadata_,
        }
        for row, source_name in rows
    ]


@app.get("/item-types")
def list_item_types(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(NormalizedItem.item_type).distinct().order_by(NormalizedItem.item_type)
    ).all()
    return rows


def _market_question(raw_json: dict | None) -> str | None:
    if not raw_json:
        return None
    return (
        raw_json.get("question")
        or raw_json.get("title")
        or raw_json.get("slug")
        or raw_json.get("description")
    )


def _market_token_price(raw_json: dict | None) -> float | None:
    if not raw_json:
        return None
    return first_outcome_price(raw_json)


@app.get("/market-data")
def list_market_data(
    limit: int = 50,
    source: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
):
    limit = min(max(limit, 1), 200)
    query = select(MarketData, Source.name).join(Source, MarketData.source_id == Source.id)

    if source:
        source_filter = Source.name == source
        if source.isdigit():
            source_filter = or_(source_filter, Source.id == int(source))
        query = query.where(source_filter)
    if q:
        query = query.where(
            or_(
                MarketData.market_or_asset_id.ilike(f"%{q}%"),
                cast(MarketData.raw_json, String).ilike(f"%{q}%"),
            )
        )

    rows = session.execute(query.order_by(desc(MarketData.timestamp)).limit(limit)).all()
    return [
        {
            "id": row.id,
            "source_id": row.source_id,
            "source_name": source_name,
            "market_or_asset_id": row.market_or_asset_id,
            "question": _market_question(row.raw_json),
            "timestamp": row.timestamp,
            "bid": row.bid,
            "ask": row.ask,
            "mid_price": row.mid_price if row.mid_price is not None else _market_token_price(row.raw_json),
            "volume": row.volume,
            "spread": row.spread,
            "open_interest": row.open_interest,
        }
        for row, source_name in rows
    ]


@app.get("/fetch-logs")
def list_fetch_logs(limit: int = 50, session: Session = Depends(get_session)):
    limit = min(max(limit, 1), 200)
    rows = session.execute(
        select(FetchLog, Source.name)
        .join(Source, FetchLog.source_id == Source.id)
        .order_by(desc(FetchLog.started_at))
        .limit(limit)
    ).all()
    return [
        _fetch_log_payload(row, source_name)
        for row, source_name in rows
    ]
