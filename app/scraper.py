"""
AutoRia HTML scraper — без API ключа.
Парсить сторінки auto.ria.com/uk/car/used/ через requests + BeautifulSoup.
"""

import random
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ── User-Agent пул ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


# ── Data model ──────────────────────────────────────────────────
@dataclass
class Car:
    id: str = ""
    url: str = ""
    title: str = ""
    price_usd: Optional[int] = None
    price_uah: Optional[int] = None
    year: Optional[int] = None
    mileage_km: Optional[int] = None
    engine: str = ""
    fuel: str = ""
    gearbox: str = ""
    drivetrain: str = ""
    city: str = ""
    seller: str = ""
    phone: str = ""
    description: str = ""
    images: list = field(default_factory=list)
    raw_params: dict = field(default_factory=dict)


# ── Session ─────────────────────────────────────────────────────
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    return s


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def sleep_between(min_s: float = 1.5, max_s: float = 4.0):
    time.sleep(random.uniform(min_s, max_s))


# ── Build search URL ────────────────────────────────────────────
def build_search_url(
    page: int = 0,
    brand: str = "",       # напр. "toyota"
    model: str = "",       # напр. "camry"
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    price_from: Optional[int] = None,
    price_to: Optional[int] = None,
    region: str = "",      # напр. "kiev"
) -> str:
    """
    Формує URL для сторінки пошуку.
    auto.ria використовує людинозрозумілі URL вигляду:
    /uk/car/used/toyota/camry/?page=N&...
    """
    parts = ["https://auto.ria.com/uk/car/used"]
    if brand:
        parts.append(brand)
        if model:
            parts.append(model)
    url = "/".join(parts) + "/"

    params = []
    if page > 0:
        params.append(f"page={page}")
    if year_from:
        params.append(f"year[0].gte={year_from}")
    if year_to:
        params.append(f"year[0].lte={year_to}")
    if price_from:
        params.append(f"price.gte={price_from}")
    if price_to:
        params.append(f"price.lte={price_to}")
    if region:
        params.append(f"region={region}")

    if params:
        url += "?" + "&".join(params)
    return url


# ── Parse listing page ──────────────────────────────────────────
def parse_listing(html: str) -> tuple[list[str], int]:
    """
    Повертає (список URL оголошень, загальна кількість).
    """
    soup = BeautifulSoup(html, "lxml")
    urls = []

    # Картки оголошень — секції з класом ticket-item
    for ticket in soup.select("section.ticket-item"):
        link = ticket.select_one("a.address")
        if link and link.get("href"):
            href = link["href"]
            if not href.startswith("http"):
                href = "https://auto.ria.com" + href
            urls.append(href)

    # Загальна кількість оголошень
    total = 0
    count_el = soup.select_one("span.count strong, .search-result-title strong")
    if count_el:
        num = re.sub(r"\D", "", count_el.text)
        total = int(num) if num else 0

    return urls, total


# ── Parse single car page ───────────────────────────────────────
def parse_car_page(html: str, url: str) -> Car:
    soup = BeautifulSoup(html, "lxml")
    car = Car(url=url)

    # ID з URL
    m = re.search(r"_(\d+)\.html", url)
    if m:
        car.id = m.group(1)

    # Заголовок
    h1 = soup.select_one("h1.head")
    if h1:
        car.title = h1.get_text(strip=True)

    # Ціна USD
    price_usd = soup.select_one("span.price_value strong, div.price_value strong")
    if price_usd:
        num = re.sub(r"\D", "", price_usd.text)
        car.price_usd = int(num) if num else None

    # Ціна UAH
    price_uah = soup.select_one("span.price_value--additional")
    if price_uah:
        num = re.sub(r"\D", "", price_uah.text)
        car.price_uah = int(num) if num else None

    # Рік
    year_el = soup.select_one("span.argument[data-type='year']")
    if not year_el:
        # fallback — шукаємо в заголовку
        m = re.search(r"\b(19|20)\d{2}\b", car.title)
        if m:
            car.year = int(m.group())
    else:
        car.year = int(year_el.text.strip())

    # Пробіг
    mileage_el = soup.select_one("span.argument[data-type='mileage']")
    if mileage_el:
        num = re.sub(r"\D", "", mileage_el.text)
        car.mileage_km = int(num) * 1000 if num else None

    # Характеристики з таблиці dd/dt
    params = {}
    for row in soup.select("dd.item-char"):
        label_el = row.find_previous_sibling("dt")
        if label_el:
            key = label_el.get_text(strip=True).rstrip(":")
            val = row.get_text(strip=True)
            params[key] = val

    car.raw_params = params

    # Витягаємо конкретні поля з параметрів
    for key, val in params.items():
        k = key.lower()
        if "двигун" in k or "об'єм" in k:
            car.engine = val
        elif "паливо" in k or "тип палива" in k:
            car.fuel = val
        elif "коробка" in k:
            car.gearbox = val
        elif "привід" in k:
            car.drivetrain = val

    # Місто
    city_el = soup.select_one("div.item_inner ul.unstyle li.item.city span.argument, span[class*='city']")
    if city_el:
        car.city = city_el.get_text(strip=True)

    # Продавець
    seller_el = soup.select_one("div.seller_info_name, h4.seller_info_name")
    if seller_el:
        car.seller = seller_el.get_text(strip=True)

    # Опис
    desc_el = soup.select_one("div.full-description")
    if desc_el:
        car.description = desc_el.get_text(strip=True)[:500]

    # Фото
    for img in soup.select("div.photo-620-430 img, picture.outline img")[:5]:
        src = img.get("src") or img.get("data-src") or ""
        if src and src.startswith("http"):
            car.images.append(src)

    return car


# ── Main scrape function ────────────────────────────────────────
def scrape(
    pages: int = 1,
    brand: str = "",
    model: str = "",
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    price_from: Optional[int] = None,
    price_to: Optional[int] = None,
    region: str = "",
    delay_min: float = 1.5,
    delay_max: float = 4.0,
    on_progress=None,   # callback(message: str)
) -> list[dict]:
    """
    Головна функція парсингу. Повертає список словників.
    on_progress — колбек для стрімінгу статусу у FastAPI.
    """
    session = make_session()
    all_cars = []

    def log(msg):
        if on_progress:
            on_progress(msg)

    # 1. Збираємо URL з усіх сторінок
    car_urls = []
    for page in range(pages):
        url = build_search_url(
            page=page, brand=brand, model=model,
            year_from=year_from, year_to=year_to,
            price_from=price_from, price_to=price_to,
            region=region,
        )
        log(f"📄 Сторінка {page + 1}: {url}")
        try:
            session.headers["User-Agent"] = random_ua()
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            urls, total = parse_listing(resp.text)
            car_urls.extend(urls)
            log(f"✅ Знайдено {len(urls)} оголошень (всього на сайті: {total})")
        except Exception as e:
            log(f"❌ Помилка сторінки {page + 1}: {e}")

        if page < pages - 1:
            sleep_between(delay_min, delay_max)

    log(f"🔗 Всього URL для парсингу: {len(car_urls)}")

    # 2. Парсимо кожне оголошення
    for i, car_url in enumerate(car_urls):
        log(f"🚗 [{i + 1}/{len(car_urls)}] {car_url}")
        try:
            session.headers["User-Agent"] = random_ua()
            resp = session.get(car_url, timeout=15)
            resp.raise_for_status()
            car = parse_car_page(resp.text, car_url)
            all_cars.append(asdict(car))
            log(f"   ✅ {car.title or car.id} — ${car.price_usd}")
        except Exception as e:
            log(f"   ❌ Помилка: {e}")

        sleep_between(delay_min, delay_max)

    return all_cars
