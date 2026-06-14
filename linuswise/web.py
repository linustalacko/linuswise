"""Local web app: daily review (skip / keep / rewind), library, and Q&A.

Served by Flask on localhost. `linuswise app` wraps this in a native desktop
window; `linuswise serve` just opens it in your browser. Every dimension in the
UI is a multiple of 4px (see the design tokens at the top of the <style>).
"""

from __future__ import annotations

import sqlite3
import threading
import webbrowser

from flask import Flask, Response, jsonify, request

from . import db, qa
from .config import Config


def _d(row: sqlite3.Row) -> dict:
    keys = (
        "id",
        "text",
        "note",
        "source_title",
        "source_author",
        "source_type",
        "location",
        "favorite",
        "review_count",
    )
    out = {k: (row[k] if k in row.keys() else None) for k in keys}
    if "action" in row.keys():
        out["action"] = row["action"]
    return out


def create_app(cfg: Config) -> Flask:
    app = Flask(__name__)

    # The server only ever binds to loopback, but any web page you visit can still
    # try to POST to it (CSRF). Browsers attach an Origin header to such requests,
    # so we reject state-changing requests whose Origin isn't our own local origin.
    local_origins = {
        f"http://127.0.0.1:{cfg.web_port}",
        f"http://localhost:{cfg.web_port}",
    }

    @app.before_request
    def _csrf_guard():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("Origin") not in local_origins:
                return jsonify({"error": "cross-origin request blocked"}), 403

    @app.after_request
    def _headers(resp):
        # The native webview otherwise caches the page and serves stale UI.
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        # Defense-in-depth: no MIME sniffing, no framing, and lock the page's
        # network/asset origins. ('unsafe-inline' stays because the UI uses inline
        # styles and event handlers; untrusted text is HTML-escaped before render.)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'"
        )
        return resp

    def conn() -> sqlite3.Connection:
        # One connection per request thread; SQLite handles this fine.
        return db.connect(cfg.db_path)

    @app.get("/")
    def index() -> Response:
        return Response(INDEX_HTML, mimetype="text/html")

    @app.get("/api/today")
    def api_today():
        c = conn()
        rows = db.get_or_create_today(c, cfg.review_count, cfg.min_highlight_chars)
        s = db.stats(c)
        return jsonify({"items": [_d(r) for r in rows], "library_total": s["total"]})

    @app.post("/api/action")
    def api_action():
        body = request.get_json(silent=True) or {}
        action = body.get("action")
        if action not in ("keep", "skip", "discard"):
            return jsonify({"error": "bad action"}), 400
        try:
            hid = int(body["id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "bad id"}), 400
        db.set_action(conn(), hid, action)
        return jsonify({"ok": True})

    @app.get("/api/library")
    def api_library():
        c = conn()
        rows = db.all_highlights(
            c,
            query=request.args.get("q", "").strip(),
            only_favorites=request.args.get("fav") == "1",
        )
        return jsonify({"items": [_d(r) for r in rows], "stats": db.stats(c)})

    @app.post("/api/ask")
    def api_ask():
        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error": "empty question"}), 400
        try:
            ans = qa.ask(
                conn(),
                question,
                k=cfg.qa.retrieve_k,
                model=cfg.qa.groq_model,
                api_key=cfg.qa.groq_api_key,
                embed_model=cfg.qa.embed_model,
            )
        except Exception:  # noqa: BLE001
            # Log the detail server-side; don't leak internals (keys, paths) to the page.
            app.logger.exception("ask failed")
            return jsonify(
                {
                    "error": "Ask failed. Check that GROQ_API_KEY is set and embeddings are built (linuswise embed). See the server log for details."
                }
            ), 500
        return jsonify({"answer": ans.text, "sources": [_d(r) for r in ans.sources]})

    return app


def serve(cfg: Config, open_browser: bool = True) -> None:
    url = f"http://127.0.0.1:{cfg.web_port}/"
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"linuswise running at {url}  (ctrl-c to stop)")
    create_app(cfg).run(host="127.0.0.1", port=cfg.web_port, debug=False)


# --------------------------------------------------------------------- frontend
# All sizes are multiples of 4px. Hairline 1px borders are the documented
# exception. Palette is fully monochrome — black ink on light grey, no colour.
INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#ffffff">
<link rel="manifest" href="/static/manifest.webmanifest">
<link rel="apple-touch-icon" href="/static/icon-180.png">
<link rel="icon" href="/static/logo.svg">
<title>Linuswise</title>
<style>
  :root{
    --paper:#ffffff; --card:#ffffff; --ink:#111111; --muted:#666666;
    --faint:#999999; --gold:#111111; --gold-deep:#111111; --line:#e5e5e5;
    --serif:Georgia,'Times New Roman',serif;
    --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--paper);color:var(--ink);font-family:var(--sans);
       font-size:16px;line-height:24px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:720px;margin:0 auto;padding:72px 16px 64px}
  .sr-only{position:absolute;width:4px;height:4px;overflow:hidden;clip:rect(0 0 0 0)}

  header{display:flex;align-items:center;gap:16px;margin-bottom:32px}
  .brand{display:flex;align-items:center;gap:8px;font-size:16px;line-height:28px;font-weight:600;color:var(--ink)}
  .brand svg{display:block;flex:none;width:28px;height:28px}
  .tabs{display:flex;gap:24px;margin-left:auto}
  .tab{height:40px;padding:0 4px;border:none;background:transparent;font-size:16px;
       line-height:40px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent}
  .tab.active{color:var(--ink);font-weight:600;border-bottom:2px solid var(--ink)}

  /* ---- review card ---- */
  .progress{display:flex;align-items:center;gap:8px;margin-bottom:16px;height:8px}
  .dot{width:8px;height:8px;border-radius:8px;background:var(--line)}
  .dot.seen{background:var(--gold)} .dot.now{background:var(--gold-deep)}
  .count{margin-left:auto;font-size:12px;line-height:16px;color:var(--faint);
         letter-spacing:4px;text-transform:uppercase}

  .card{padding:0}
  .src-title{font-size:16px;line-height:24px;font-weight:600}
  .src-author{font-size:12px;line-height:16px;color:var(--muted);font-style:italic;margin-top:4px}
  .htext{font-family:var(--serif);font-size:24px;line-height:36px;margin-top:24px;
         padding-left:16px;border-left:2px solid var(--gold)}
  .note{margin-top:20px;background:#f6f6f6;border-radius:8px;padding:16px;
        font-size:16px;line-height:24px;color:var(--muted)}
  .note b{color:var(--gold-deep);font-weight:600}
  .loc{margin-top:16px;font-size:12px;line-height:16px;color:var(--faint);
       letter-spacing:4px;text-transform:uppercase}

  .actions{display:flex;gap:16px;margin-top:32px;align-items:center}
  .btn{height:48px;padding:0 24px;border-radius:12px;border:1px solid var(--line);
       background:var(--card);font-size:16px;line-height:24px;color:var(--ink);
       cursor:pointer;display:inline-flex;align-items:center;gap:8px}
  .btn:hover{border-color:var(--gold)}
  .btn.keep{background:var(--ink);border-color:var(--ink);color:var(--card)}
  .btn.icon{width:48px;height:48px;padding:0;justify-content:center;font-size:20px}
  .btn.ghost{color:var(--muted);border-color:transparent}
  .spacer{flex:1}

  .done{text-align:center;padding:64px 32px}
  .done h2{font-family:var(--serif);font-size:32px;line-height:40px;font-weight:400}
  .done p{color:var(--muted);margin-top:16px}

  /* ---- library + ask ---- */
  .ask{margin-bottom:40px}
  .ask textarea{width:100%;min-height:80px;border:1px solid var(--line);border-radius:12px;
       padding:16px;font-family:var(--sans);font-size:16px;line-height:24px;resize:vertical}
  .ask .row{display:flex;gap:16px;align-items:center;margin-top:16px}
  .answer{margin-top:24px;padding:24px;background:var(--card);border:1px solid var(--ink);
       border-radius:12px;font-size:16px;line-height:28px;white-space:pre-wrap}
  .sources{margin-top:16px;display:flex;flex-direction:column;gap:8px}
  .source{font-size:12px;line-height:20px;color:var(--muted);padding-left:16px;
       border-left:2px solid var(--gold)}

  .filters{display:flex;gap:8px;margin-bottom:16px}
  .filters input{flex:1;height:40px;border:1px solid var(--line);border-radius:8px;
       padding:0 16px;font-size:16px;font-family:var(--sans)}
  .lib-item{padding:24px 0;border-bottom:1px solid var(--line)}
  .lib-item .t{font-family:var(--serif);font-size:16px;line-height:24px}
  .lib-item .m{font-size:12px;line-height:16px;color:var(--muted);margin-top:8px}
  .kept{font-size:12px;line-height:16px;letter-spacing:4px;text-transform:uppercase;color:var(--muted);margin-left:8px}
  .hidden{display:none}
  .muted{color:var(--muted)}
</style>
</head>
<body>
<div class="wrap">
  <h1 class="sr-only">Linuswise daily review</h1>
  <header>
    <div class="brand"><svg width="28" height="28" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="14" fill="#111111"/><rect x="14" y="27" width="36" height="6" rx="3" fill="#ffffff"/><rect x="14" y="39" width="22" height="6" rx="3" fill="#666666"/></svg></div>
    <div class="tabs">
      <button class="tab active" id="tab-today" onclick="show('today')">Today</button>
      <button class="tab" id="tab-library" onclick="show('library')">Library</button>
    </div>
  </header>

  <section id="view-today">
    <div class="progress" id="progress"></div>
    <div id="card-host"></div>
  </section>

  <section id="view-library" class="hidden">
    <div class="ask">
      <textarea id="q" placeholder="Ask anything about your highlights…  e.g. what have I read about decision-making?"></textarea>
      <div class="row">
        <button class="btn keep" onclick="ask()">Ask</button>
        <span class="muted" id="ask-status"></span>
      </div>
      <div id="answer-host"></div>
    </div>
    <div class="filters">
      <input id="search" placeholder="Search highlights…" oninput="loadLibrary()">
      <button class="btn" id="favbtn" onclick="toggleFav()">Kept only</button>
    </div>
    <div id="lib-host"></div>
  </section>
</div>

<script>
const api = (p,o)=>fetch(p,o).then(r=>r.json());
let today=[], idx=0, favOnly=false;

function show(v){
  document.getElementById('view-today').classList.toggle('hidden', v!=='today');
  document.getElementById('view-library').classList.toggle('hidden', v!=='library');
  document.getElementById('tab-today').classList.toggle('active', v==='today');
  document.getElementById('tab-library').classList.toggle('active', v==='library');
  if(v==='library') loadLibrary();
}
const esc = s => (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

async function loadToday(){
  const data = await api('/api/today');
  today = data.items;
  idx = Math.max(0, today.findIndex(h=>!h.action));
  if(idx===-1) idx = today.length;
  render();
}
function renderProgress(){
  const p=document.getElementById('progress');
  if(!today.length){p.innerHTML='';return;}
  let dots='';
  for(let i=0;i<today.length;i++)
    dots+=`<span class="dot ${i<idx?'seen':i===idx?'now':''}"></span>`;
  p.innerHTML = dots + `<span class="count">${Math.min(idx+1,today.length)} / ${today.length}</span>`;
}
function render(){
  renderProgress();
  const host=document.getElementById('card-host');
  if(!today.length){host.innerHTML=`<div class="done"><h2>Nothing to review yet</h2><p>Seed some highlights, then come back.</p></div>`;return;}
  if(idx>=today.length){
    const kept=today.filter(h=>h.action==='keep').length;
    const skipped=today.filter(h=>h.action==='skip').length;
    host.innerHTML=`<div class="done"><h2>You're all caught up</h2><p>${kept} kept · ${skipped} skipped · ${today.length} reviewed today</p>
      <div class="actions" style="justify-content:center"><button class="btn" onclick="idx=0;render()">Review again</button>
      <button class="btn keep" onclick="show('library')">Browse library</button></div></div>`;
    return;
  }
  const h=today[idx];
  host.innerHTML=`<div class="card">
    <div class="src-title">${esc(h.source_title)}</div>
    ${h.source_author?`<div class="src-author">${esc(h.source_author)}</div>`:''}
    <div class="htext">${esc(h.text)}</div>
    ${h.note?`<div class="note"><b>Note:</b> ${esc(h.note)}</div>`:''}
    ${h.location?`<div class="loc">${esc(h.location)}</div>`:''}
    <div class="actions">
      <button class="btn ghost" title="Rewind (←)" onclick="rewind()">Rewind</button>
      <button class="btn" onclick="act('skip')">Skip</button>
      <div class="spacer"></div>
      <button class="btn ghost" onclick="act('discard')">Discard</button>
      <button class="btn keep" onclick="act('keep')">Keep</button>
    </div>
  </div>`;
}
async function act(action){
  const h=today[idx]; h.action=action;
  api('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:h.id,action})});
  idx++; render();
}
function rewind(){ if(idx>0){idx--;} render(); }

window.addEventListener('keydown',e=>{
  if(!document.getElementById('view-today').classList.contains('hidden')){
    if(e.key==='ArrowLeft') rewind();
    else if(e.key==='k'||e.key==='ArrowRight') act('keep');
    else if(e.key==='s') act('skip');
    else if(e.key==='d') act('discard');
  }
});

async function loadLibrary(){
  const q=encodeURIComponent(document.getElementById('search').value);
  const data=await api(`/api/library?q=${q}&fav=${favOnly?1:0}`);
  const host=document.getElementById('lib-host');
  host.innerHTML = data.items.length ? data.items.map(h=>`
    <div class="lib-item">
      <div class="t">${esc(h.text)}${h.favorite?'<span class="kept">Kept</span>':''}</div>
      <div class="m">${esc(h.source_title)}${h.source_author?' · '+esc(h.source_author):''}${h.location?' · '+esc(h.location):''}</div>
    </div>`).join('') : `<p class="muted">No highlights match.</p>`;
}
function toggleFav(){favOnly=!favOnly;document.getElementById('favbtn').classList.toggle('keep',favOnly);loadLibrary();}

async function ask(){
  const q=document.getElementById('q').value.trim();
  if(!q) return;
  const st=document.getElementById('ask-status'); st.textContent='Thinking…';
  document.getElementById('answer-host').innerHTML='';
  const data=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
  st.textContent='';
  if(data.error){document.getElementById('answer-host').innerHTML=`<div class="answer">${esc(data.error)}</div>`;return;}
  const src=(data.sources||[]).map((s,i)=>`<div class="source">[${i+1}] ${esc(s.text)} — ${esc(s.source_title)}</div>`).join('');
  document.getElementById('answer-host').innerHTML=`<div class="answer">${esc(data.answer)}</div><div class="sources">${src}</div>`;
}

loadToday();
</script>
</body>
</html>"""
