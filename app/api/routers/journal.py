"""
Trade journal — read-only HTML dashboard served by the same FastAPI process.

No separate frontend build: open /journal in the browser, enter your API key once
(localStorage), positions + history refresh from existing JSON endpoints.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["journal"])

_JOURNAL_HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>NovaBot — Journal de trades</title>
  <style>
    :root {
      --bg:#0c0e12; --panel:#141820; --border:#252b36; --text:#e8eaef;
      --muted:#8b93a7; --accent:#4da3ff; --green:#3ecf8e; --red:#f07178;
      --amber:#e6b450;
    }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text);
           font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
    .wrap { max-width:1200px; margin:0 auto; padding:20px 16px 48px; }
    header { display:flex; flex-wrap:wrap; align-items:center; gap:12px 20px;
              margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid var(--border); }
    h1 { margin:0; font-size:22px; font-weight:600; }
    .sub { color:var(--muted); font-size:13px; }
    .toolbar { margin-left:auto; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
    button, .btn {
      background:var(--panel); border:1px solid var(--border); color:var(--text);
      padding:7px 12px; border-radius:6px; cursor:pointer; font-size:13px;
    }
    button:hover { border-color:var(--accent); color:var(--accent); }
    .auth-bar {
      display:flex; flex-wrap:wrap; gap:8px; align-items:center;
      background:var(--panel); border:1px solid var(--border); border-radius:8px;
      padding:12px 14px; margin-bottom:20px;
    }
    .auth-bar input {
      flex:1; min-width:180px; background:#0a0c10; border:1px solid var(--border);
      color:var(--text); padding:8px 10px; border-radius:6px; font-family:monospace;
    }
    .auth-bar.hidden { display:none; }
    .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-bottom:22px; }
    .stat { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:12px 14px; }
    .stat .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; }
    .stat .value { font-size:20px; font-weight:600; margin-top:4px; }
    .stat .value.pos { color:var(--green); }
    .stat .value.neg { color:var(--red); }
    section { margin-bottom:28px; }
    section h2 { font-size:13px; text-transform:uppercase; letter-spacing:.08em;
                 color:var(--muted); margin:0 0 10px; }
    table { width:100%; border-collapse:collapse; background:var(--panel);
            border:1px solid var(--border); border-radius:8px; overflow:hidden; }
    th, td { padding:9px 11px; text-align:left; border-bottom:1px solid var(--border); }
    th { background:#1a1f28; color:var(--muted); font-size:11px; font-weight:600;
         text-transform:uppercase; letter-spacing:.04em; }
    tr:last-child td { border-bottom:none; }
    tr:hover td { background:#181d26; }
    .empty { color:var(--muted); text-align:center; padding:24px; }
    .side-buy { color:var(--green); font-weight:600; }
    .side-sell { color:var(--red); font-weight:600; }
    .pnl-pos { color:var(--green); }
    .pnl-neg { color:var(--red); }
    .badge { display:inline-block; padding:2px 7px; border-radius:4px; font-size:11px;
             background:#1d2838; color:var(--accent); }
    .status-line { color:var(--muted); font-size:12px; margin-top:6px; }
    .err { color:var(--red); background:#2a1518; border:1px solid #4a2028;
           padding:10px 12px; border-radius:8px; margin-bottom:16px; display:none; }
    .err.show { display:block; }
    .loading { opacity:.55; pointer-events:none; }
    footer { margin-top:32px; color:var(--muted); font-size:12px; }
    footer a { color:var(--accent); }
    @media (max-width:700px) {
      table { font-size:12px; }
      th, td { padding:7px 8px; }
      .hide-sm { display:none; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>NovaBot — Journal de trades</h1>
        <div class="sub">Lecture seule · positions en cours + historique bot</div>
      </div>
      <div class="toolbar">
        <span id="refreshLabel" class="sub">—</span>
        <button type="button" id="btnRefresh">Actualiser</button>
        <button type="button" id="btnClearKey" title="Effacer la clé API locale">Clé API</button>
        <a class="btn" href="/">API</a>
      </div>
    </header>

    <div id="authBar" class="auth-bar">
      <span class="sub">Clé API (header X-API-Key) :</span>
      <input id="apiKeyInput" type="password" placeholder="Collez votre API_KEY" autocomplete="off" />
      <button type="button" id="btnSaveKey">Enregistrer</button>
    </div>

    <div id="errorBox" class="err"></div>

    <div class="stats" id="statsRow">
      <div class="stat"><div class="label">Solde</div><div class="value" id="statBalance">—</div></div>
      <div class="stat"><div class="label">Positions</div><div class="value" id="statPositions">—</div></div>
      <div class="stat"><div class="label">Trades (bot)</div><div class="value" id="statTrades">—</div></div>
      <div class="stat"><div class="label">Win rate</div><div class="value" id="statWinRate">—</div></div>
      <div class="stat"><div class="label">PnL total</div><div class="value" id="statPnl">—</div></div>
    </div>

    <section>
      <h2>Positions ouvertes</h2>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>Symbole</th><th>Côté</th><th>Taille</th><th>Entrée</th>
              <th>PnL</th><th class="hide-sm">Durée</th><th class="hide-sm">Stratégie</th>
            </tr>
          </thead>
          <tbody id="positionsBody"><tr><td colspan="7" class="empty">Chargement…</td></tr></tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>Historique bot <span class="badge">trade_history.csv</span></h2>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Symbole</th><th>Côté</th><th>Entrée</th><th>Sortie</th>
              <th>PnL</th><th class="hide-sm">Stratégie</th><th class="hide-sm">Raison</th>
            </tr>
          </thead>
          <tbody id="historyBody"><tr><td colspan="8" class="empty">Chargement…</td></tr></tbody>
        </table>
      </div>
      <div class="status-line" id="historyMeta"></div>
    </section>

    <footer>
      Rafraîchissement auto toutes les 30 s ·
      <a href="/api/history/bot/trades/download">Télécharger CSV</a> ·
      <a href="/docs">Swagger</a>
    </footer>
  </div>
  <script>
(function () {
  const KEY_STORAGE = "novabot_api_key";
  const REFRESH_MS = 30000;

  const authBar = document.getElementById("authBar");
  const apiKeyInput = document.getElementById("apiKeyInput");
  const errorBox = document.getElementById("errorBox");
  const refreshLabel = document.getElementById("refreshLabel");

  function getApiKey() {
    return localStorage.getItem(KEY_STORAGE) || "";
  }

  function showError(msg) {
    if (!msg) { errorBox.classList.remove("show"); errorBox.textContent = ""; return; }
    errorBox.textContent = msg;
    errorBox.classList.add("show");
  }

  function fmtUsd(n) {
    if (n == null || isNaN(n)) return "—";
    const v = Number(n);
    const s = (v >= 0 ? "+" : "") + v.toFixed(2);
    return s + " $";
  }

  function fmtNum(n, d) {
    if (n == null || n === "" || isNaN(n)) return "—";
    return Number(n).toFixed(d == null ? 2 : d);
  }

  function sideClass(side) {
    const s = String(side || "").toUpperCase();
    if (s === "BUY" || s === "LONG") return "side-buy";
    if (s === "SELL" || s === "SHORT") return "side-sell";
    return "";
  }

  async function apiFetch(path) {
    const headers = {};
    const key = getApiKey();
    if (key) headers["X-API-Key"] = key;
    const res = await fetch(path, { headers });
    if (res.status === 401 || res.status === 403) {
      authBar.classList.remove("hidden");
      throw new Error("Authentification requise — saisissez votre clé API.");
    }
    if (!res.ok) {
      let detail = res.statusText;
      try { const j = await res.json(); detail = j.detail || JSON.stringify(j); } catch (_) {}
      throw new Error(path + " → " + detail);
    }
    return res.json();
  }

  function renderPositions(positions) {
    const tbody = document.getElementById("positionsBody");
    const open = (positions || []).filter(p => Math.abs(Number(p.size || p.sz || 0)) > 0);
    document.getElementById("statPositions").textContent = String(open.length);
    if (!open.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">Aucune position ouverte</td></tr>';
      return;
    }
    tbody.innerHTML = open.map(p => {
      const sym = p.symbol || p.coin || "—";
      const side = p.side || (Number(p.size || p.sz) > 0 ? "LONG" : "SHORT");
      const size = p.size != null ? p.size : p.sz;
      const entry = p.entry_price != null ? p.entry_price : p.entryPx;
      const pnl = p.pnl != null ? p.pnl : p.unrealized_pnl;
      const pnlCls = Number(pnl) >= 0 ? "pnl-pos" : "pnl-neg";
      return `<tr>
        <td><strong>${sym}</strong></td>
        <td class="${sideClass(side)}">${side}</td>
        <td>${fmtNum(size, 4)}</td>
        <td>${fmtNum(entry, 4)}</td>
        <td class="${pnlCls}">${fmtUsd(pnl)}</td>
        <td class="hide-sm">${p.duration || "—"}</td>
        <td class="hide-sm">${p.strategy || p.source || "—"}</td>
      </tr>`;
    }).join("");
  }

  function renderHistory(trades) {
    const tbody = document.getElementById("historyBody");
    const list = trades || [];
    document.getElementById("statTrades").textContent = String(list.length);
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty">Aucun trade enregistré</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(t => {
      const pnl = t.pnl != null ? t.pnl : t.realized_pnl;
      const pnlCls = Number(pnl) >= 0 ? "pnl-pos" : "pnl-neg";
      const dt = t.timestamp || t.exit_time || t.close_time || t.entry_time || "—";
      return `<tr>
        <td>${dt}</td>
        <td><strong>${t.symbol || "—"}</strong></td>
        <td class="${sideClass(t.side)}">${t.side || "—"}</td>
        <td>${fmtNum(t.entry_price || t.entry, 4)}</td>
        <td>${fmtNum(t.exit_price || t.exit, 4)}</td>
        <td class="${pnlCls}">${fmtUsd(pnl)}</td>
        <td class="hide-sm">${t.strategy || "—"}</td>
        <td class="hide-sm">${t.exit_reason || t.reason || "—"}</td>
      </tr>`;
    }).join("");
  }

  function renderStats(stats, balance) {
    const balEl = document.getElementById("statBalance");
    const av = balance?.account_value ?? balance?.total_equity;
    balEl.textContent = av != null ? fmtUsd(av).replace("+", "") : "—";

    const s = stats || {};
    const wr = s.win_rate != null ? Number(s.win_rate).toFixed(1) + " %" : "—";
    document.getElementById("statWinRate").textContent = wr;

    const pnl = s.total_pnl != null ? s.total_pnl : s.net_pnl;
    const pnlEl = document.getElementById("statPnl");
    pnlEl.textContent = fmtUsd(pnl);
    pnlEl.className = "value " + (Number(pnl) >= 0 ? "pos" : "neg");
  }

  async function loadAll() {
    document.body.classList.add("loading");
    showError("");
    try {
      const [status, hist, stats] = await Promise.all([
        apiFetch("/api/status"),
        apiFetch("/api/history/bot/trades?limit=100"),
        apiFetch("/api/history/bot/trades/stats"),
      ]);
      const positions = status.open_positions || status.positions || [];
      renderPositions(positions);
      const trades = hist.trades || [];
      renderHistory(trades);
      renderStats(stats.stats || stats, { account_value: status.balance });
      document.getElementById("historyMeta").textContent =
        (hist.count != null ? hist.count + " trades affichés" : "") +
        (status.active_symbol ? " · Symbole actif : " + status.active_symbol : "");
      const now = new Date().toLocaleTimeString("fr-FR");
      refreshLabel.textContent = "MAJ " + now;
      if (getApiKey()) authBar.classList.add("hidden");
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      document.body.classList.remove("loading");
    }
  }

  document.getElementById("btnRefresh").addEventListener("click", loadAll);
  document.getElementById("btnSaveKey").addEventListener("click", () => {
    localStorage.setItem(KEY_STORAGE, apiKeyInput.value.trim());
    authBar.classList.add("hidden");
    loadAll();
  });
  document.getElementById("btnClearKey").addEventListener("click", () => {
    localStorage.removeItem(KEY_STORAGE);
    apiKeyInput.value = "";
    authBar.classList.remove("hidden");
  });

  if (getApiKey()) {
    authBar.classList.add("hidden");
    apiKeyInput.value = "••••••••";
  }

  loadAll();
  setInterval(loadAll, REFRESH_MS);
})();
  </script>
</body>
</html>"""


@router.get("/journal", include_in_schema=False, response_class=HTMLResponse)
def trade_journal():
    """Read-only trade journal (positions + bot history)."""
    return HTMLResponse(_JOURNAL_HTML)
