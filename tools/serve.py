"""Live translation progress page, served locally.

    python tools/serve.py [port]        # default 8765, open http://localhost:8765

Reads work/*/ on every request (no state of its own): batches, tasks given
out, answers in out/, validation results and the latest translated lines.
Standard library only.
"""
import glob
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate import check  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cache = {}


def load(path):
    """JSON load cached by mtime (files can be large and polled often)."""
    try:
        m = os.path.getmtime(path)
    except OSError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == m:
        return hit[1]
    try:
        data = json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return None  # being written right now
    _cache[path] = (m, data)
    return data


def mod_status(work):
    slug = os.path.basename(work)
    batches = []
    total = done = bad = chars_total = chars_done = 0
    recent = []
    for bp in sorted(glob.glob(os.path.join(work, 'batches', '*.json'))):
        n = os.path.basename(bp)[:3]
        doc = load(bp)
        if not doc:
            continue
        items = doc['items']
        size = sum(len(i['en']) for i in items)
        total += len(items)
        chars_total += size
        op = os.path.join(work, 'out', f'{n}.json')
        tp = os.path.join(work, 'tasks', f'{n}.md')
        out = load(op) if os.path.exists(op) else None
        state, ok, invalid = 'todo', 0, 0
        if out is not None:
            for it in items:
                ru = out.get(it['id'])
                if ru and not check(it['en'], ru):
                    ok += 1
                elif ru:
                    invalid += 1
            state = 'done' if ok == len(items) else ('partial' if ok else 'invalid')
            done += ok
            bad += invalid
            chars_done += sum(len(i['en']) for i in items if out.get(i['id']) and not check(i['en'], out[i['id']]))
            mtime = os.path.getmtime(op)
            for it in items[-3:]:
                if out.get(it['id']):
                    recent.append((mtime, n, it['ctx'], it['en'], out[it['id']]))
        elif os.path.exists(tp):
            state = 'working'
        batches.append({'n': n, 'state': state, 'items': len(items), 'ok': ok, 'invalid': invalid})
    auto = load(os.path.join(work, 'auto.json')) or {}
    recent.sort(reverse=True)
    return {
        'slug': slug, 'batches': batches, 'total': total, 'done': done, 'invalid': bad,
        'auto': len(auto), 'chars_total': chars_total, 'chars_done': chars_done,
        'recent': [{'batch': r[1], 'ctx': r[2], 'en': r[3], 'ru': r[4]} for r in recent[:8]],
    }


def status():
    mods = [mod_status(w) for w in sorted(glob.glob(os.path.join(ROOT, 'work', '*')))
            if os.path.isdir(os.path.join(w, 'batches'))]  # skip scratch folders
    return {'time': time.strftime('%H:%M:%S'), 'mods': mods}


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Перевод модов — прогресс</title>
<style>
:root { --bg:#f6f5f2; --panel:#fff; --fg:#1d1c1a; --muted:#6d6a63; --line:#e2dfd8;
  --todo:#e6e3dc; --work:#e9b949; --done:#3f8f5b; --bad:#c2453b; --part:#7fb08d; --accent:#2f5d8a; }
@media (prefers-color-scheme: dark) { :root { --bg:#151514; --panel:#1f1e1c; --fg:#ecebe7; --muted:#9a968d;
  --line:#33312d; --todo:#2c2a27; --work:#c99a2e; --done:#4fa46c; --bad:#d4584d; --part:#3d6e4c; --accent:#7aa7d4; } }
* { box-sizing: border-box }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 "Segoe UI", system-ui, sans-serif;
  padding: 24px max(16px, 4vw) 48px; }
h1 { font-size: 22px; margin: 0 0 4px }
.sub { color: var(--muted); margin: 0 0 20px }
.mod { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 20px; margin-bottom: 20px }
.mod h2 { margin: 0 0 12px; font-size: 18px }
.bar { height: 12px; background: var(--todo); border-radius: 6px; overflow: hidden }
.bar > div { height: 100%; background: var(--done); transition: width .6s ease }
.nums { display: flex; flex-wrap: wrap; gap: 24px; margin: 14px 0 18px }
.num b { display: block; font-size: 24px; font-variant-numeric: tabular-nums }
.num span { color: var(--muted); font-size: 13px }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(44px, 1fr)); gap: 6px }
.cell { border-radius: 6px; padding: 6px 0; text-align: center; font-size: 12px; font-variant-numeric: tabular-nums;
  background: var(--todo); color: var(--muted) }
.cell.done { background: var(--done); color: #fff }
.cell.partial { background: var(--part); color: #fff }
.cell.invalid { background: var(--bad); color: #fff }
.cell.working { background: var(--work); color: #1d1c1a; animation: pulse 1.4s ease-in-out infinite }
@keyframes pulse { 50% { opacity: .55 } }
@media (prefers-reduced-motion: reduce) { .cell.working { animation: none } .bar > div { transition: none } }
.legend { display: flex; flex-wrap: wrap; gap: 14px; color: var(--muted); font-size: 13px; margin: 10px 0 0 }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px }
h3 { font-size: 14px; margin: 22px 0 8px; color: var(--muted); font-weight: 600; letter-spacing: .02em }
.pair { border-top: 1px solid var(--line); padding: 10px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 16px }
.pair div { min-width: 0; white-space: pre-wrap; overflow-wrap: anywhere }
.pair .en { color: var(--muted) }
.pair .ctx { grid-column: 1 / -1; font-size: 12px; color: var(--muted); font-family: Consolas, monospace }
@media (max-width: 600px) { .pair { grid-template-columns: 1fr } }
.empty { color: var(--muted) }
</style></head><body>
<h1>Перевод модов</h1>
<p class="sub">Обновляется каждые 2 секунды · <span id="time">—</span></p>
<div id="mods"><p class="empty">Загрузка…</p></div>
<script>
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = (n) => n.toLocaleString('ru-RU');
const STATE = {todo:'ждёт', working:'в работе', partial:'частично', invalid:'с ошибками', done:'готово'};
function render(s) {
  document.getElementById('time').textContent = 'данные на ' + s.time;
  if (!s.mods.length) { document.getElementById('mods').innerHTML = '<p class="empty">В work/ пока нет модов.</p>'; return; }
  document.getElementById('mods').innerHTML = s.mods.map((m) => {
    const pct = m.total ? (100 * m.done / m.total) : 0;
    const left = m.batches.filter((b) => b.state !== 'done').length;
    const cells = m.batches.map((b) => `<div class="cell ${b.state}" title="Порция ${b.n}: ${STATE[b.state]}, ${b.ok}/${b.items}${b.invalid ? ', ошибок ' + b.invalid : ''}">${b.n}</div>`).join('');
    const recent = m.recent.length ? m.recent.map((r) => `<div class="pair"><div class="ctx">порция ${esc(r.batch)} · ${esc(r.ctx)}</div><div class="en">${esc(r.en)}</div><div>${esc(r.ru)}</div></div>`).join('')
      : '<p class="empty">Пока ничего не переведено.</p>';
    return `<section class="mod"><h2>${esc(m.slug)}</h2>
      <div class="bar"><div style="width:${pct.toFixed(2)}%"></div></div>
      <div class="nums">
        <div class="num"><b>${pct.toFixed(1)}%</b><span>готово</span></div>
        <div class="num"><b>${fmt(m.done)} / ${fmt(m.total)}</b><span>строк переведено</span></div>
        <div class="num"><b>${m.batches.length - left} / ${m.batches.length}</b><span>порций</span></div>
        <div class="num"><b>${fmt(m.invalid)}</b><span>с ошибками</span></div>
        <div class="num"><b>${fmt(m.auto)}</b><span>из ванили сразу</span></div>
      </div>
      <div class="grid">${cells}</div>
      <div class="legend"><span><i style="background:var(--todo)"></i>ждёт</span><span><i style="background:var(--work)"></i>в работе</span><span><i style="background:var(--part)"></i>частично</span><span><i style="background:var(--done)"></i>готово</span><span><i style="background:var(--bad)"></i>с ошибками</span></div>
      <h3>ПОСЛЕДНИЕ ПЕРЕВОДЫ</h3>${recent}</section>`;
  }).join('');
}
async function tick() {
  try { render(await (await fetch('/api/status', {cache: 'no-store'})).json()); }
  catch { document.getElementById('time').textContent = 'сервер не отвечает'; }
}
tick(); setInterval(tick, 2000);
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/status'):
            body = json.dumps(status(), ensure_ascii=False).encode('utf-8')
            ctype = 'application/json; charset=utf-8'
        elif self.path in ('/', '/index.html'):
            body, ctype = PAGE.encode('utf-8'), 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f'http://localhost:{port}  (Ctrl+C to stop)')
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
