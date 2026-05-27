import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse

app = FastAPI(title="AutoRia Scraper", version="2.0.0")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

STATIC = Path("static/index.html")


# ── Pages ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(STATIC.read_text(encoding="utf-8"))


# ── Scrape — стрімінг прогресу через SSE ───────────────────────
@app.get("/api/scrape")
async def scrape(
    pages: int       = Query(1, ge=1, le=20),
    brand: str       = Query(""),
    model: str       = Query(""),
    year_from: Optional[int] = Query(None),
    year_to:   Optional[int] = Query(None),
    price_from: Optional[int] = Query(None),
    price_to:   Optional[int] = Query(None),
    region: str      = Query(""),
    delay_min: float = Query(1.5),
    delay_max: float = Query(4.0),
):
    """Запускає парсинг і стрімить прогрес через Server-Sent Events."""

    from app.scraper import scrape as do_scrape

    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(msg: str):
        queue.put_nowait(msg)

    async def run_scrape():
        loop = asyncio.get_event_loop()
        cars = await loop.run_in_executor(
            None,
            lambda: do_scrape(
                pages=pages, brand=brand, model=model,
                year_from=year_from, year_to=year_to,
                price_from=price_from, price_to=price_to,
                region=region,
                delay_min=delay_min, delay_max=delay_max,
                on_progress=on_progress,
            )
        )
        # зберігаємо
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scrape_{ts}.json"
        path = DATA_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "scraped_at": ts,
                "count": len(cars),
                "cars": cars,
            }, f, ensure_ascii=False, indent=2)
        queue.put_nowait(f"💾 Збережено {len(cars)} оголошень → {filename}")
        queue.put_nowait(f"__DONE__:{filename}:{len(cars)}")

    asyncio.create_task(run_scrape())

    async def event_stream():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=120)
                yield f"data: {msg}\n\n"
                if msg.startswith("__DONE__"):
                    break
            except asyncio.TimeoutError:
                yield "data: ⏳ очікування...\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Saved files ─────────────────────────────────────────────────
@app.get("/api/saved-files")
async def list_saved():
    files = []
    for f in sorted(DATA_DIR.iterdir(), reverse=True):
        if f.suffix == ".json":
            stat = f.stat()
            files.append({
                "name": f.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "created": datetime.fromtimestamp(stat.st_ctime).strftime("%d.%m.%Y %H:%M"),
            })
    return files


@app.get("/api/download/{filename}")
async def download(filename: str):
    path = DATA_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(404, "Файл не знайдено")
    return FileResponse(path, media_type="application/json", filename=filename)


@app.get("/api/preview/{filename}")
async def preview(filename: str, limit: int = Query(5)):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cars = data.get("cars", [])[:limit]
    return {"count": data.get("count", 0), "cars": cars}
