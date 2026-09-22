"""
Фоновый цикл: раз в 5 минут выбирает отслеживания, которым пора проверить
цену (по last_checked_at + check_interval_min), опрашивает нужный
маркетплейс и шлёт уведомление, если цена упала.
"""
import asyncio
import logging

from aiogram import Bot

import db
from services import marketplaces

_LOOP_INTERVAL_SEC = 5 * 60


def _format_price(kopecks: int) -> str:
    return f"{kopecks / 100:,.0f}".replace(",", " ")


async def _check_one(bot: Bot, watch) -> None:
    parser = next(
        (p for p in marketplaces.PARSERS if p.MARKETPLACE == watch["marketplace"]), None
    )
    if parser is None:
        return

    title, price = await parser.fetch_price(watch["url"])

    if price is None:
        await db.update_watch_price(watch["id"], watch["last_price"], ok=False)
        return

    await db.update_watch_price(watch["id"], price, ok=True)

    old_price = watch["last_price"]
    if old_price is not None and price < old_price:
        name = title or watch["title"] or watch["url"]
        try:
            await bot.send_message(
                watch["user_id"],
                f"📉 Подешевело!\n{name}\n"
                f"{_format_price(old_price)}₽ → {_format_price(price)}₽\n{watch['url']}",
            )
        except Exception:
            logging.exception("Не удалось отправить уведомление user_id=%s", watch["user_id"])


async def run_price_checker(bot: Bot) -> None:
    while True:
        try:
            await db.downgrade_expired_subscriptions()
            due = await db.watches_due_for_check()
            for watch in due:
                await _check_one(bot, watch)
        except Exception:
            logging.exception("Ошибка в цикле проверки цен")
        await asyncio.sleep(_LOOP_INTERVAL_SEC)
