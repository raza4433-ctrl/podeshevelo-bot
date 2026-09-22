"""
Avito: частные объявления, а не каталожные товары. Официального API нет,
сайт активно защищается от скрапинга. Best-effort: запрашиваем страницу
и ищем цену в JSON-LD (Schema.org Offer), это самый распространённый
способ разметки цены на карточках объявлений.

Важно: объявление может быть снято с публикации или цена может значить
не совсем то же самое, что "снижение цены" у каталожного товара (продавец
мог просто отредактировать объявление). Ложных ошибок избегаем тем, что
при неудаче парсинга просто не обновляем цену и не шлём уведомление.
"""
import json
import logging
import re

import httpx

MARKETPLACE = "avito"

_ID_RE = re.compile(r"_(\d+)(?:[/?]|$)")
_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def matches(url: str) -> bool:
    return "avito.ru" in url


def extract_item_id(url: str) -> str | None:
    match = _ID_RE.search(url.split("?")[0])
    return match.group(1) if match else None


async def fetch_price(url: str) -> tuple[str | None, int | None]:
    item_id = extract_item_id(url)
    if item_id is None:
        return None, None

    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        for ld_match in _LD_JSON_RE.finditer(html):
            try:
                ld_data = json.loads(ld_match.group(1))
            except Exception:
                continue
            if not isinstance(ld_data, dict):
                continue
            offers = ld_data.get("offers")
            if isinstance(offers, dict) and offers.get("price"):
                title = ld_data.get("name")
                return title, int(float(offers["price"]) * 100)

        logging.warning("Avito: не удалось найти цену на странице %s", url)
        return None, None
    except Exception:
        logging.exception("Не удалось получить цену Avito для %s", url)
        return None, None
