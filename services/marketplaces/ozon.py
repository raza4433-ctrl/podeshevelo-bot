"""
Ozon: официального публичного API нет, страница защищена JS-антиботом
(отдаёт "Antibot Challenge Page" на обычные HTTP-запросы даже с
браузероподобными заголовками — проверено). Поэтому цену тянем через
headless-браузер (services/browser.py), который реально выполняет JS
страницы. Это медленнее обычного запроса и не даёт 100% гарантии — антибот
всё ещё может распознать headless Chromium. При неудаче просто возвращаем
None, не роняя бота и не слав ложных уведомлений.
"""
import json
import logging
import re

from services import browser

MARKETPLACE = "ozon"

_ID_RE = re.compile(r"-(\d{6,})(?:[/?]|$)")
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)


def matches(url: str) -> bool:
    return "ozon.ru" in url


def extract_item_id(url: str) -> str | None:
    match = _ID_RE.search(url.split("?")[0])
    return match.group(1) if match else None


def _find_price_in_obj(obj) -> int | None:
    """Рекурсивно ищет разумное значение цены в произвольном JSON-дереве."""
    if isinstance(obj, dict):
        for key in ("cardPrice", "price", "priceValue", "finalPrice"):
            value = obj.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)
        for value in obj.values():
            found = _find_price_in_obj(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_price_in_obj(item)
            if found:
                return found
    return None


async def fetch_price(url: str) -> tuple[str | None, int | None]:
    item_id = extract_item_id(url)
    if item_id is None:
        return None, None

    html = await browser.fetch_rendered_html(url)
    if html is None:
        return None, None

    try:
        title = None
        ld_match = _LD_JSON_RE.search(html)
        if ld_match:
            try:
                ld_data = json.loads(ld_match.group(1))
                title = ld_data.get("name")
                offers = ld_data.get("offers") or {}
                price = offers.get("price")
                if price:
                    return title, int(float(price) * 100)
            except Exception:
                pass

        next_match = _NEXT_DATA_RE.search(html)
        if next_match:
            try:
                data = json.loads(next_match.group(1))
                price = _find_price_in_obj(data)
                if price:
                    return title, price * 100
            except Exception:
                pass

        logging.warning("Ozon: не удалось найти цену на странице %s", url)
        return title, None
    except Exception:
        logging.exception("Не удалось получить цену Ozon для %s", url)
        return None, None
