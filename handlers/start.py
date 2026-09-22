from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import db

router = Router()

WELCOME = (
    "Привет! Я «Подешевело!» — слежу за ценой товаров на Wildberries "
    "и Ozon и пишу, когда цена падает.\n\n"
    "Просто пришли мне ссылку на товар.\n\n"
    "/list — что я сейчас отслеживаю\n"
    "/subscribe — платный тариф (безлимит и проверка почаще)"
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await db.ensure_user(message.from_user.id, message.from_user.username)
    await message.answer(WELCOME)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(WELCOME)
