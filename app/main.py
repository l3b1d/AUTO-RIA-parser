import httpx
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="AutoRia Parser", version="1.0.0")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

BASE_URL = "https://developers.ria.com/auto"

# ──────────────────────────── Models ────────────────────────────

class SearchParams(BaseModel):
    api_key: str
    category_id: int = 1          # 1 = легкові
    brand_id: Optional[int] = None
    model_id: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    price_from: Optional[int] = None
    price_to: Optional[int] = None
    region_id: Optional[int] = None
    page: int = 0
    count: int = 10               # max 100


# ──────────────────────────── Helpers ────────────────────────────

def save_to_json(data: dict | list, filename: str) -> str:
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)


async def ria_get(url: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ──────────────────────────── Routes ────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path("static/index.html")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/search")
async def search_cars(
    api_key: str = Query(..., description="API ключ з developers.ria.com"),
    category_id: int = Query(1),
    brand_id: Optional[int] = Query(None),
    model_id: Optional[int] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    price_from: Optional[int] = Query(None),
    price_to: Optional[int] = Query(None),
    region_id: Optional[int] = Query(None),
    page: int = Query(0),
    count: int = Query(10, le=100),
):
    """Пошук оголошень — повертає список ID + зберігає у JSON."""
    params = {
        "api_key": api_key,
        "category_id": category_id,
        "page": page,
        "countpage": count,
    }
    if brand_id:    params["marka_id[0]"]  = brand_id
    if model_id:    params["model_id[0]"]  = model_id
    if year_from:   params["s_yers[0]"]    = year_from
    if year_to:     params["po_yers[0]"]   = year_to
    if price_from:  params["price_ot"]     = price_from
    if price_to:    params["price_do"]     = price_to
    if region_id:   params["state_id[0]"]  = region_id

    try:
        data = await ria_get(f"{BASE_URL}/search", params)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # зберігаємо список
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"search_{ts}.json"
    save_to_json(data, filename)

    return {
        "total": data.get("count", 0),
        "ids": data.get("result", {}).get("search_result", {}).get("ids", []),
        "saved_as": filename,
    }


@app.get("/api/car/{car_id}")
async def get_car(car_id: int, api_key: str = Query(...)):
    """Деталі одного оголошення."""
    try:
        data = await ria_get(f"{BASE_URL}/info", {"api_key": api_key, "auto_id": car_id})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"car_{car_id}.json"
    save_to_json(data, filename)
    return data


@app.get("/api/parse-batch")
async def parse_batch(
    api_key: str = Query(...),
    car_ids: str = Query(..., description="ID через кому: 12345,67890"),
):
    """Масовий збір деталей по списку ID → один JSON файл."""
    ids = [int(i.strip()) for i in car_ids.split(",") if i.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="Немає валідних ID")

    results = []
    errors = []

    async with httpx.AsyncClient(timeout=30) as client:
        for car_id in ids:
            try:
                resp = await client.get(
                    f"{BASE_URL}/info",
                    params={"api_key": api_key, "auto_id": car_id},
                )
                resp.raise_for_status()
                results.append(resp.json())
            except Exception as e:
                errors.append({"id": car_id, "error": str(e)})

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_{ts}.json"
    output = {"parsed_at": ts, "count": len(results), "cars": results, "errors": errors}
    save_to_json(output, filename)

    return {"saved_as": filename, "success": len(results), "failed": len(errors)}


@app.get("/api/brands")
async def get_brands(api_key: str = Query(...), category_id: int = Query(1)):
    """Список марок авто."""
    try:
        data = await ria_get(
            f"{BASE_URL}/categories/{category_id}/marks",
            {"api_key": api_key},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return data


@app.get("/api/models")
async def get_models(
    api_key: str = Query(...),
    category_id: int = Query(1),
    brand_id: int = Query(...),
):
    """Список моделей для обраної марки."""
    try:
        data = await ria_get(
            f"{BASE_URL}/categories/{category_id}/marks/{brand_id}/models",
            {"api_key": api_key},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return data


@app.get("/api/saved-files")
async def list_saved():
    """Список збережених JSON файлів."""
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
async def download_file(filename: str):
    path = DATA_DIR / filename
    if not path.exists() or not path.name.endswith(".json"):
        raise HTTPException(status_code=404, detail="Файл не знайдено")
    return FileResponse(path, media_type="application/json", filename=filename)
