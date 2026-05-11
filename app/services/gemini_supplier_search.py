import json
import re

from google import genai

from app.core.config import settings


def _extract_json_array(text: str) -> list[dict]:
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
    except Exception:
        pass

    match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not match:
        return []

    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _normalize_supplier_item(item: dict) -> dict:
    trust = item.get("trust", 60)
    try:
        trust = int(float(trust))
    except Exception:
        trust = 60

    trust = max(0, min(trust, 100))

    pros = item.get("pros", [])
    cons = item.get("cons", [])

    if not isinstance(pros, list):
        pros = [str(pros)]
    if not isinstance(cons, list):
        cons = [str(cons)]

    return {
        "name": str(item.get("name") or "Поставщик"),
        "location": str(item.get("location") or "не указано"),
        "trust": trust,
        "price": str(item.get("price") or "не указана"),
        "market_price": str(item.get("market_price") or "не указана"),
        "saving": str(item.get("saving") or ""),
        "pros": [str(x) for x in pros[:3]],
        "cons": [str(x) for x in cons[:3]],
        "url": str(item.get("url") or "#"),
    }


def search_suppliers_with_gemini(query: str) -> list[dict]:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = f"""
Ты помощник отдела закупок LinuxCenter.

Нужно найти потенциальных поставщиков для товара или категории:
{query}

Важно:
- Верни только JSON-массив.
- Без markdown.
- Без текста до или после JSON.
- Не придумывай точные цены, если не уверен.
- Если точных данных нет, предложи типы площадок или поставщиков и явно укажи, что нужна ручная проверка.
- Для url укажи сайт поставщика или поисковую/товарную страницу, если уверен. Если не уверен, поставь "#".

Формат:
[
  {{
    "name": "название поставщика или площадки",
    "location": "город или страна",
    "trust": 80,
    "price": "цена или не указана",
    "market_price": "рыночная цена или не указана",
    "saving": "экономия или не указана",
    "pros": ["плюс 1", "плюс 2"],
    "cons": ["минус 1"],
    "url": "https://example.com"
  }}
]

Верни 3-5 вариантов.
"""

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    items = _extract_json_array(response.text or "")
    return [_normalize_supplier_item(item) for item in items]