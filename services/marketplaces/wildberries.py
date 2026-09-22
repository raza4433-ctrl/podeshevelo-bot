"""
Wildberries: цену отдаёт полуофициальный JSON-эндпоинт card.wb.ru, без
headless-браузера. Формат ответа WB время от времени меняет — парсинг
защищён try/except, при неожиданной структуре просто возвращаем None,
а не роняем бота.
"""
import logging
import re

import httpx

MARKETPLACE = "wildberries"

_ID_RE = re.compile(r"/catalog/(\d+)")
_CARD_API = "https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={id}"


def matches(url: str) -> bool:
    return "wildberries.ru" in url


def extract_item_id(url: str) -> str | None:
    match = _ID_RE.search(url)
    return match.group(1) if match else None


async def fetch_price(url: str) -> tuple[str | None, int | None]:
    item_id = extract_item_id(url)
    if item_id is None:
        return None, None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_CARD_API.format(id=item_id))
            resp.raise_for_status()
            data = resp.json()

        product = data["data"]["products"][0]
        title = product.get("name")

        price_kopecks = None
        sizes = product.get("sizes") or []
        if sizes and isinstance(sizes[0].get("price"), dict):
            price_kopecks = sizes[0]["price"].get("product") or sizes[0]["price"].get("total")
        if price_kopecks is None:
            price_kopecks = product.get("salePriceU") or product.get("priceU")
        if price_kopecks is None:
            return title, None

        return title, int(price_kopecks)
    except Exception:
        logging.exception("Не удалось получить цену WB для nm=%s", item_id)
        return None, None
