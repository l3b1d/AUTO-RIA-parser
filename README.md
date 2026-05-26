# AutoRia Parser

Парсер оголошень з [auto.ria.com](https://auto.ria.com) через офіційний REST API.  
FastAPI бекенд + веб-інтерфейс. Результати зберігаються у JSON файли.

## Швидкий старт

```bash
# 1. Клонуй репо і перейди в папку
git clone <твій_репо>
cd autoria-parser

# 2. Встанови залежності
pip install -r requirements.txt

# 3. Запусти
python run.py

# 4. Відкрий в браузері
open http://localhost:8000
```

## Отримання API ключа

1. Зареєструйся на [developers.ria.com](https://developers.ria.com)
2. Перейди у **«Мої дозволи»** → активуй **AUTO.RIA → Вживані авто**
3. Скопіюй свій API ключ

## API Endpoints

| Метод | URL | Опис |
|-------|-----|------|
| `GET` | `/api/search` | Пошук оголошень за фільтрами |
| `GET` | `/api/car/{id}` | Деталі одного оголошення |
| `GET` | `/api/parse-batch` | Масовий збір деталей по списку ID |
| `GET` | `/api/brands` | Список марок |
| `GET` | `/api/models` | Список моделей для марки |
| `GET` | `/api/saved-files` | Список збережених JSON |
| `GET` | `/api/download/{filename}` | Скачати JSON файл |

### Приклад запиту

```bash
# Пошук Toyota до $10k
curl "http://localhost:8000/api/search?api_key=YOUR_KEY&brand_id=79&price_to=10000&count=20"

# Деталі оголошення
curl "http://localhost:8000/api/car/12345678?api_key=YOUR_KEY"
```

### Параметри пошуку

| Параметр | Опис |
|----------|------|
| `brand_id` | ID марки (отримати з `/api/brands`) |
| `model_id` | ID моделі |
| `year_from` / `year_to` | Рік випуску |
| `price_from` / `price_to` | Ціна в USD |
| `region_id` | ID регіону |
| `count` | Кількість результатів (макс. 100) |
| `page` | Сторінка (з 0) |

## Структура проєкту

```
autoria-parser/
├── app/
│   └── main.py          # FastAPI додаток
├── static/
│   └── index.html       # Веб-інтерфейс
├── data/                # Збережені JSON файли
├── run.py               # Точка входу
├── requirements.txt
└── README.md
```

## Збережені дані

Всі результати автоматично зберігаються у папку `data/`:
- `search_YYYYMMDD_HHMMSS.json` — результати пошуку (список ID)
- `car_{id}.json` — деталі одного оголошення
- `batch_YYYYMMDD_HHMMSS.json` — масовий збір деталей

### Поля оголошення

```json
{
  "USD": 8500,
  "markName": "Toyota",
  "modelName": "Camry",
  "year": 2018,
  "raceInt": 120,
  "fuelName": "Бензин",
  "gearBoxName": "Автомат",
  "cityName": "Київ",
  "linkToView": "https://auto.ria.com/...",
  ...
}
```
