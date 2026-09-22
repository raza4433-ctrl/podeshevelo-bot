from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db

router = Router()


def _format_price(kopecks: int | None) -> str:
    if kopecks is None:
        return "неизвестно"
    return f"{kopecks / 100:,.0f}₽".replace(",", " ")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    watches = await db.list_watches(message.from_user.id)
    if not watches:
        await message.answer("Пока ничего не отслеживаю. Пришли ссылку на товар.")
        return

    for watch in watches:
        status = "" if watch["last_check_ok"] else " (не удалось проверить последний раз)"
        text = (
            f"{watch['title'] or watch['url']}\n"
            f"Цена: {_format_price(watch['last_price'])}{status}\n"
            f"{watch['url']}"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Убрать из отслеживания", callback_data=f"untrack:{watch['id']}")]
            ]
        )
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("untrack:"))
async def handle_untrack(callback: CallbackQuery) -> None:
    watch_id = int(callback.data.split(":", 1)[1])
    removed = await db.deactivate_watch(callback.from_user.id, watch_id)
    if removed:
        await callback.message.edit_text("Убрано из отслеживания ✅")
    else:
        await callback.answer("Не нашёл это отслеживание", show_alert=True)
        return
    await callback.answer()
