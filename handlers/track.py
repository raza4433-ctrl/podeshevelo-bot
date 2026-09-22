import logging
import re

import httpx
from aiogram import F, Router
from aiogram.types import Message

import db
from config import config
from services import marketplaces

router = Router()

_DOMAIN_RE = re.compile(r"(wildberries\.ru|ozon\.ru|avito\.ru)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_RESOLVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _format_price(kopecks: int) -> str:
    return f"{kopecks / 100:,.0f}".replace(",", " ")


async def _resolve_redirect(url: str) -> str:
    """Короткие ссылки (ozon.ru/t/..., ссылки из "Поделиться") редиректят на
    настоящую страницу товара с числовым id в адресе — переходим по ним."""
    try:
        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True, headers=_RESOLVE_HEADERS
        ) as client:
            resp = await client.get(url)
            return str(resp.url)
    except Exception:
        logging.exception("Не удалось развернуть короткую ссылку %s", url)
        return url


@router.message(F.text.regexp(_DOMAIN_RE, search=True))
async def handle_url(message: Message) -> None:
    text = message.text.strip()
    # Сообщение может быть не голой ссылкой, а текстом из "Поделиться"
    # ("Посмотри объявление ... на Авито: \n https://...") — вытаскиваем URL.
    url_match = _URL_RE.search(text)
    if url_match:
        raw_url = url_match.group(0).rstrip(").,!?\"'")
    else:
        raw_url = text
        if not raw_url.lower().startswith("http"):
            raw_url = "https://" + raw_url.lstrip("/")
    user_id = message.from_user.id
    await db.ensure_user(user_id, message.from_user.username)

    parser = marketplaces.detect_marketplace(raw_url)
    if parser is None:
        await message.answer(
            "Пока умею только Wildberries и Ozon (Avito временно отключён). "
            "Пришли ссылку на товар оттуда."
        )
        return

    url = raw_url
    item_id = parser.extract_item_id(url)
    if item_id is None:
        # короткая/share-ссылка без id в адресе — пробуем развернуть редирект
        url = await _resolve_redirect(raw_url)
        item_id = parser.extract_item_id(url)

    if item_id is None:
        await message.answer("Не смог найти id товара в этой ссылке, попробуй скопировать ссылку заново.")
        return

    existing = await db.find_watch(user_id, parser.MARKETPLACE, item_id)
    if existing:
        await message.answer("Этот товар уже у меня в списке — смотри /list")
        return

    user = await db.get_user(user_id)
    is_paid = bool(user["is_paid"]) if user else False
    if not is_paid:
        count = await db.count_active_watches(user_id)
        if count >= config.free_watch_limit:
            await message.answer(
                f"На бесплатном тарифе можно отслеживать до {config.free_watch_limit} товаров. "
                "Освободи слот через /list или подключи /subscribe."
            )
            return

    await message.answer("Проверяю цену...")
    title, price = await parser.fetch_price(url)

    await db.add_watch(user_id, parser.MARKETPLACE, item_id, url, title, price)

    if price is None:
        await message.answer(
            "Добавил в отслеживание, но текущую цену получить не удалось — "
            "попробую ещё раз в следующем цикле проверки."
        )
    else:
        name = title or url
        await message.answer(f"Слежу за ценой ✅\n{name}\nТекущая цена: {_format_price(price)}₽")
