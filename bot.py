import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
import db
from handlers import start, track, list as list_handler, subscribe
from services.price_checker import run_price_checker

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await db.init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # Порядок важен: команды и ссылки раньше — на будущее, если появится общий текстовый хендлер
    dp.include_router(start.router)
    dp.include_router(list_handler.router)
    dp.include_router(track.router)
    dp.include_router(subscribe.router)

    asyncio.create_task(run_price_checker(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
