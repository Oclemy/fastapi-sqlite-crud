import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import aiosqlite
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DATABASE = os.getenv("DATABASE_PATH", "data/app.db")


async def get_db():
    db = await aiosqlite.connect(DATABASE)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            completed BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    await db.commit()
    await db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="CRUD App", lifespan=lifespan)


# ── Pydantic Models ──────────────────────────────────────────────
class ItemCreate(BaseModel):
    title: str
    description: str = ""
    completed: bool = False


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


# ── API Routes ───────────────────────────────────────────────────
@app.post("/api/items", status_code=201)
async def create_item(item: ItemCreate):
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO items (title, description, completed) VALUES (?, ?, ?)",
        (item.title, item.description, item.completed),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM items WHERE id = ?", (cursor.lastrowid,))
    result = dict(await row.fetchone())
    await db.close()
    return result


@app.get("/api/items")
async def read_items(skip: int = 0, limit: int = 100, q: str = ""):
    db = await get_db()
    if q:
        rows = await db.execute(
            "SELECT * FROM items WHERE title LIKE ? OR description LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (f"%{q}%", f"%{q}%", limit, skip),
        )
    else:
        rows = await db.execute(
            "SELECT * FROM items ORDER BY id DESC LIMIT ? OFFSET ?", (limit, skip)
        )
    items = [dict(r) for r in await rows.fetchall()]
    await db.close()
    return items


@app.get("/api/items/{item_id}")
async def read_item(item_id: int):
    db = await get_db()
    row = await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = await row.fetchone()
    await db.close()
    if not item:
        raise HTTPException(404, "Item not found")
    return dict(item)


@app.put("/api/items/{item_id}")
async def update_item(item_id: int, item: ItemUpdate):
    db = await get_db()
    existing = await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    if not await existing.fetchone():
        await db.close()
        raise HTTPException(404, "Item not found")
    updates = {k: v for k, v in item.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    await db.execute(
        f"UPDATE items SET {set_clause} WHERE id = ?",
        (*updates.values(), item_id),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    result = dict(await row.fetchone())
    await db.close()
    return result


@app.delete("/api/items/{item_id}")
async def delete_item(item_id: int):
    db = await get_db()
    existing = await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    if not await existing.fetchone():
        await db.close()
        raise HTTPException(404, "Item not found")
    await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    await db.commit()
    await db.close()
    return {"deleted": True, "id": item_id}


# ── Stats endpoint ───────────────────────────────────────────────
@app.get("/api/stats")
async def stats():
    db = await get_db()
    total = dict(await (await db.execute("SELECT COUNT(*) as c FROM items")).fetchone())["c"]
    done = dict(await (await db.execute("SELECT COUNT(*) as c FROM items WHERE completed=1")).fetchone())["c"]
    await db.close()
    return {"total": total, "completed": done, "pending": total - done}


# ── Frontend ─────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def frontend():
    return HTML_PAGE


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRUD App</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0e1117;--surface:#161b22;--border:#30363d;--border-hi:#484f58;
  --text:#e6edf3;--text-dim:#8b949e;--accent:#58a6ff;--accent-glow:#58a6ff33;
  --green:#3fb950;--green-bg:#3fb95018;--red:#f85149;--red-bg:#f8514918;
  --orange:#d29922;--radius:10px;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:0}
a{color:var(--accent);text-decoration:none}

/* Header */
.header{
  background:linear-gradient(135deg,#0d1117 0%,#161b22 50%,#0d1117 100%);
  border-bottom:1px solid var(--border);padding:2rem 1.5rem;text-align:center;
  position:relative;overflow:hidden;
}
.header::before{
  content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;
  background:radial-gradient(circle at 30% 50%,#58a6ff08 0%,transparent 50%),
             radial-gradient(circle at 70% 50%,#3fb95008 0%,transparent 50%);
  animation:drift 20s linear infinite;
}
@keyframes drift{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
.header h1{font-size:1.6rem;font-weight:700;position:relative;letter-spacing:-.02em}
.header h1 span{color:var(--accent)}
.header p{color:var(--text-dim);font-size:.85rem;margin-top:.3rem;position:relative}

/* Stats */
.stats{display:flex;gap:.75rem;padding:1.25rem 1.5rem;max-width:720px;margin:0 auto}
.stat{
  flex:1;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:.75rem 1rem;text-align:center;transition:border-color .2s;
}
.stat:hover{border-color:var(--border-hi)}
.stat .num{font-size:1.5rem;font-weight:700;font-family:'JetBrains Mono',monospace}
.stat .label{font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--text-dim);margin-top:.15rem}
.stat.total .num{color:var(--accent)}
.stat.done .num{color:var(--green)}
.stat.pending .num{color:var(--orange)}

/* Container */
.container{max-width:720px;margin:0 auto;padding:0 1.5rem 3rem}

/* Form */
.form-card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:1.25rem;margin-bottom:1.25rem;
}
.form-row{display:flex;gap:.5rem;margin-bottom:.5rem}
.form-row:last-child{margin-bottom:0}
input[type=text],textarea{
  flex:1;background:var(--bg);border:1px solid var(--border);border-radius:8px;
  padding:.6rem .85rem;color:var(--text);font-family:inherit;font-size:.88rem;
  transition:border-color .2s,box-shadow .2s;resize:none;
}
input[type=text]:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
textarea{min-height:2.4rem;height:2.4rem}
.btn{
  padding:.6rem 1.2rem;border-radius:8px;border:1px solid transparent;
  font-family:inherit;font-size:.85rem;font-weight:600;cursor:pointer;
  transition:all .15s ease;white-space:nowrap;
}
.btn-primary{background:var(--accent);color:#0e1117}
.btn-primary:hover{filter:brightness(1.15);transform:translateY(-1px);box-shadow:0 4px 12px var(--accent-glow)}
.btn-sm{padding:.35rem .7rem;font-size:.78rem}
.btn-ghost{background:transparent;color:var(--text-dim);border-color:var(--border)}
.btn-ghost:hover{color:var(--text);border-color:var(--border-hi);background:#ffffff06}
.btn-danger{background:var(--red-bg);color:var(--red);border-color:var(--red)44}
.btn-danger:hover{background:var(--red);color:#fff}

/* Search */
.search-bar{margin-bottom:1rem}
.search-bar input{width:100%;background:var(--surface);border:1px solid var(--border)}

/* Items */
.items-list{display:flex;flex-direction:column;gap:.5rem}
.item{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:1rem 1.15rem;display:flex;align-items:flex-start;gap:.85rem;
  transition:border-color .2s,transform .15s;animation:slideIn .25s ease;
}
.item:hover{border-color:var(--border-hi)}
@keyframes slideIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

.checkbox{
  width:20px;height:20px;min-width:20px;border-radius:6px;border:2px solid var(--border-hi);
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:all .2s;margin-top:2px;background:transparent;
}
.checkbox:hover{border-color:var(--accent)}
.checkbox.checked{background:var(--green);border-color:var(--green)}
.checkbox.checked::after{content:'✓';color:#fff;font-size:12px;font-weight:700}

.item-body{flex:1;min-width:0}
.item-title{font-weight:600;font-size:.95rem;word-break:break-word}
.item-desc{color:var(--text-dim);font-size:.82rem;margin-top:.2rem;word-break:break-word}
.item-meta{display:flex;gap:.75rem;margin-top:.4rem;align-items:center}
.item-time{font-size:.7rem;color:var(--text-dim);font-family:'JetBrains Mono',monospace}
.item.completed .item-title{text-decoration:line-through;opacity:.5}
.item.completed .item-desc{opacity:.4}
.item-actions{display:flex;gap:.35rem;flex-shrink:0}

/* Edit mode */
.edit-form{display:flex;flex-direction:column;gap:.4rem;flex:1}
.edit-form input,.edit-form textarea{font-size:.88rem}
.edit-actions{display:flex;gap:.35rem;margin-top:.25rem}

.empty{text-align:center;padding:3rem 1rem;color:var(--text-dim)}
.empty .icon{font-size:2.5rem;margin-bottom:.5rem;opacity:.4}
.empty p{font-size:.9rem}

/* Toast */
.toast-container{position:fixed;bottom:1.5rem;right:1.5rem;z-index:999;display:flex;flex-direction:column;gap:.4rem}
.toast{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:.65rem 1rem;font-size:.82rem;animation:toastIn .3s ease;
  box-shadow:0 8px 24px #00000060;
}
@keyframes toastIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
.toast.success{border-color:var(--green);color:var(--green)}
.toast.error{border-color:var(--red);color:var(--red)}

@media(max-width:500px){
  .stats{flex-direction:row;gap:.5rem;padding:1rem}
  .stat{padding:.6rem .5rem}
  .form-row{flex-direction:column}
  .container{padding:0 1rem 2rem}
}
</style>
</head>
<body>

<div class="header">
  <h1>⚡ <span>CRUD</span> App</h1>
  <p>FastAPI + SQLite &mdash; Create, Read, Update, Delete</p>
</div>

<div class="stats" id="stats">
  <div class="stat total"><div class="num" id="s-total">-</div><div class="label">Total</div></div>
  <div class="stat done"><div class="num" id="s-done">-</div><div class="label">Done</div></div>
  <div class="stat pending"><div class="num" id="s-pending">-</div><div class="label">Pending</div></div>
</div>

<div class="container">
  <div class="form-card">
    <div class="form-row">
      <input type="text" id="inp-title" placeholder="Item title…" autofocus>
      <button class="btn btn-primary" onclick="createItem()">Add</button>
    </div>
    <div class="form-row">
      <textarea id="inp-desc" placeholder="Description (optional)"></textarea>
    </div>
  </div>

  <div class="search-bar">
    <input type="text" id="inp-search" placeholder="Search items…" oninput="debounceSearch()">
  </div>

  <div class="items-list" id="items-list"></div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
const API = '/api/items';
let editingId = null;
let searchTimer = null;

async function api(url, opts = {}) {
  opts.headers = { 'Content-Type': 'application/json', ...opts.headers };
  const r = await fetch(url, opts);
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
  return r.json();
}

function toast(msg, type = 'success') {
  const d = document.createElement('div');
  d.className = `toast ${type}`;
  d.textContent = msg;
  document.getElementById('toasts').appendChild(d);
  setTimeout(() => d.remove(), 2500);
}

async function loadStats() {
  const s = await api('/api/stats');
  document.getElementById('s-total').textContent = s.total;
  document.getElementById('s-done').textContent = s.completed;
  document.getElementById('s-pending').textContent = s.pending;
}

async function loadItems(q = '') {
  const items = await api(`${API}?q=${encodeURIComponent(q)}`);
  const list = document.getElementById('items-list');
  if (!items.length) {
    list.innerHTML = '<div class="empty"><div class="icon">📦</div><p>No items yet. Add one above!</p></div>';
    return;
  }
  list.innerHTML = items.map(i => editingId === i.id ? editRow(i) : itemRow(i)).join('');
}

function itemRow(i) {
  const cls = i.completed ? 'item completed' : 'item';
  const desc = i.description ? `<div class="item-desc">${esc(i.description)}</div>` : '';
  const time = i.created_at ? `<span class="item-time">${new Date(i.created_at+'Z').toLocaleString()}</span>` : '';
  return `<div class="${cls}" data-id="${i.id}">
    <div class="checkbox ${i.completed?'checked':''}" onclick="toggleDone(${i.id},${!i.completed})"></div>
    <div class="item-body">
      <div class="item-title">${esc(i.title)}</div>${desc}
      <div class="item-meta">${time}</div>
    </div>
    <div class="item-actions">
      <button class="btn btn-sm btn-ghost" onclick="startEdit(${i.id})">✎</button>
      <button class="btn btn-sm btn-danger" onclick="deleteItem(${i.id})">✕</button>
    </div>
  </div>`;
}

function editRow(i) {
  return `<div class="item" data-id="${i.id}">
    <div class="edit-form">
      <input type="text" id="edit-title" value="${esc(i.title)}">
      <textarea id="edit-desc">${esc(i.description||'')}</textarea>
      <div class="edit-actions">
        <button class="btn btn-sm btn-primary" onclick="saveEdit(${i.id})">Save</button>
        <button class="btn btn-sm btn-ghost" onclick="cancelEdit()">Cancel</button>
      </div>
    </div>
  </div>`;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

async function createItem() {
  const title = document.getElementById('inp-title').value.trim();
  if (!title) return;
  const desc = document.getElementById('inp-desc').value.trim();
  try {
    await api(API, { method: 'POST', body: JSON.stringify({ title, description: desc }) });
    document.getElementById('inp-title').value = '';
    document.getElementById('inp-desc').value = '';
    toast('Item created');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

async function toggleDone(id, val) {
  try {
    await api(`${API}/${id}`, { method: 'PUT', body: JSON.stringify({ completed: val }) });
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteItem(id) {
  try {
    await api(`${API}/${id}`, { method: 'DELETE' });
    toast('Deleted');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

function startEdit(id) { editingId = id; loadItems(document.getElementById('inp-search').value); }
function cancelEdit() { editingId = null; loadItems(document.getElementById('inp-search').value); }

async function saveEdit(id) {
  const title = document.getElementById('edit-title').value.trim();
  const desc = document.getElementById('edit-desc').value.trim();
  if (!title) return;
  try {
    await api(`${API}/${id}`, { method: 'PUT', body: JSON.stringify({ title, description: desc }) });
    editingId = null;
    toast('Updated');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadItems(document.getElementById('inp-search').value), 300);
}

function refresh() { loadStats(); loadItems(document.getElementById('inp-search').value); }

// Enter key support
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    if (document.activeElement.id === 'inp-title' || document.activeElement.id === 'inp-desc') {
      e.preventDefault(); createItem();
    }
    if (document.activeElement.id === 'edit-title' || document.activeElement.id === 'edit-desc') {
      e.preventDefault(); const id = editingId; if (id) saveEdit(id);
    }
  }
});

refresh();
</script>
</body>
</html>"""
