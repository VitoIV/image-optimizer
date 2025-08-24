import os, uuid, time, datetime
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import redis
from rq import Queue
import openpyxl

from .storage import Storage
from .processor import process_urls, extract_urls_mode_A, extract_urls_mode_table, write_results

APP_TITLE = "Optimalizátor fotografií"

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:18085/imgopt")
STORAGE_ROOT   = os.getenv("STORAGE_ROOT", "/app/data")
REDIS_URL      = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME     = os.getenv("QUEUE_NAME", "batches")
THREADS_PER_WORKER = int(os.getenv("THREADS_PER_WORKER", "8"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")

r = redis.from_url(REDIS_URL, decode_responses=True)
q = Queue(QUEUE_NAME, connection=r)
storage = Storage(STORAGE_ROOT)

app = FastAPI(title=APP_TITLE)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

def now_iso(): return datetime.datetime.utcnow().isoformat()
def bkey(bid: str) -> str: return f"batch:{bid}"

def set_status(bid: str, **fields):
    r.hset(bkey(bid), mapping=fields)

def get_batch(bid: str) -> Dict:
    d = r.hgetall(bkey(bid)) or {}
    if "processed" in d: d["processed"] = int(d["processed"])
    if "total" in d: d["total"] = int(d["total"])
    d["deleted"] = d.get("deleted","0") == "1"
    return d

def add_to_index(bid: str): r.lpush("batches:index", bid)
def get_index(n=200): return r.lrange("batches:index", 0, n-1)

# --- worker job ---
def job_process_batch(bid: str):
    meta = storage.load_meta(bid)
    mode = meta.get("mode","A")
    inp = storage.batch_input_xlsx(bid)
    if not os.path.exists(inp):
        set_status(bid, status="failed"); return
    wb = openpyxl.load_workbook(inp)
    ws = wb.active

    if mode == "A":
        pairs = extract_urls_mode_A(ws)
    else:
        pairs = extract_urls_mode_table(ws)
    total = len(pairs)
    set_status(bid, total=str(total), processed="0", status="processing")

    def prog(done, tot): set_status(bid, processed=str(done))
    mapping = process_urls(bid, pairs, storage, PUBLIC_BASE_URL, int(r.get("threads:per_worker") or THREADS_PER_WORKER), prog)
    write_results(ws, mapping)
    outp = storage.batch_output_xlsx(bid)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    wb.save(outp)
    set_status(bid, status="done", result_zip="1")

def do_purge():
    keep = int(r.get("retention_days") or RETENTION_DAYS)
    cutoff = time.time() - keep*24*3600
    for bid in get_index(1000):
        b = get_batch(bid)
        if not b: continue
        if b.get("status") in ("done","failed","cancelled","deleted"):
            try: ts = datetime.datetime.fromisoformat(b.get("created_at","")).timestamp()
            except: ts = 0
            if ts and ts < cutoff:
                delete_everything(bid)

def delete_everything(bid: str):
    storage.delete_batch_files(bid)
    set_status(bid, deleted="1", status="deleted")
    return True

@app.get("/", response_class=HTMLResponse)
def index_html():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/admin", response_class=HTMLResponse)
def admin_html(request: Request):
    if request.cookies.get("admin") != "1":
        with open(os.path.join(os.path.dirname(__file__), "static", "login.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    with open(os.path.join(os.path.dirname(__file__), "static", "admin.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/api/admin/login")
def admin_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        resp = JSONResponse({"ok": True}); resp.set_cookie("admin","1", max_age=8*3600, httponly=True, samesite="Lax"); return resp
    raise HTTPException(status_code=403, detail="Bad password")

@app.post("/api/admin/logout")
def admin_logout():
    resp = JSONResponse({"ok": True}); resp.delete_cookie("admin"); return resp

@app.get("/api/admin/workers")
def admin_workers():
    return {
        "desired": int(r.get("workers:desired") or os.getenv("WORKER_PROCESSES","2")),
        "threads": int(r.get("threads:per_worker") or os.getenv("THREADS_PER_WORKER","8")),
        "retention_days": int(r.get("retention_days") or os.getenv("RETENTION_DAYS","30")),
        "auto_purge": (r.get("auto_purge_enabled") or os.getenv("AUTO_PURGE_ENABLED","false")).lower()=="true"
    }

@app.post("/api/admin/workers/set/{n}")
def admin_set_workers(n: int): r.set("workers:desired", str(n)); return {"ok": True}

@app.post("/api/admin/threads/set/{n}")
def admin_set_threads(n: int): r.set("threads:per_worker", str(n)); return {"ok": True}

@app.post("/api/admin/retention/set/{days}")
def admin_set_retention(days: int): r.set("retention_days", str(days)); return {"ok": True}

@app.post("/api/admin/auto-purge/{flag}")
def admin_set_auto(flag: str): r.set("auto_purge_enabled", "true" if flag.lower() in ("1","true","yes","on") else "false"); return {"ok": True}

@app.post("/api/admin/purge")
def admin_purge(): do_purge(); return {"ok": True}

@app.get("/api/batches")
def list_batches():
    return {"batches": [get_batch(bid) for bid in get_index(500) if get_batch(bid)]}

@app.post("/api/batches")
def create_batch(file: UploadFile = File(...), mode: str = Form("A")):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Očekávám .xlsx soubor.")
    bid = uuid.uuid4().hex[:12]
    with open(storage.batch_input_xlsx(bid), "wb") as f: f.write(file.file.read())
    mode_norm = "A" if mode.lower().startswith("a") else "table"
    storage.save_meta(bid, {"mode": mode_norm})
    set_status(bid, id=bid, status="queued", processed="0", total="0", created_at=now_iso(), original_filename=file.filename, result_zip="0", deleted="0", mode=mode_norm)
    add_to_index(bid)
    q.enqueue(job_process_batch, bid, job_timeout=60*60*12)
    return {"ok": True, "id": bid}

@app.post("/api/batches/{bid}/cancel")
def cancel_batch(bid: str): set_status(bid, status="cancelled"); r.set(f"batch:{bid}:cancel","1"); return {"ok": True}

@app.delete("/api/batches/{bid}")
def delete_batch(bid: str): delete_everything(bid); return Response(status_code=204)

@app.get("/api/batches/{bid}/download")
def download_batch(bid: str):
    outp = storage.batch_output_xlsx(bid)
    if not os.path.exists(outp): raise HTTPException(status_code=404, detail="Výstup není k dispozici.")
    return FileResponse(outp, filename=f"batch-{bid}.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.get("/api/i/{bid}/{nice_id}")
def serve_image(bid: str, nice_id: str):
    p = storage.image_file_from_nice(bid, nice_id)
    if not os.path.exists(p): raise HTTPException(status_code=404, detail="Obrázek nenalezen.")
    return FileResponse(p, media_type="image/jpeg")
