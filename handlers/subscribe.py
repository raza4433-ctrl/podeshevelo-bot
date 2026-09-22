"""
Платная подписка через Telegram Stars — встроенная валюта Telegram.
Не требует ИП/самозанятости и эквайринга: Telegram сам выступает продавцом,
боту достаточно вызвать send_invoice с currency="XTR".
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

import db
from config import config

router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    await message.answer_invoice(
        title="Подписка «Подешевело!»",
        description=(
            f"{config.subscription_days} дней: безлимит отслеживаний и проверка цены "
            f"раз в {config.paid_check_interval_min} минут вместо "
            f"{config.free_check_interval_min // 60} часов на бесплатном тарифе."
        ),
        payload="subscribe",
        currency="XTR",
        prices=[LabeledPrice(label=f"Подписка на {config.subscription_days} дней", amount=config.stars_price)],
    )


@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def handle_successful_payment(message: Message) -> None:
    await db.set_subscription(message.from_user.id, config.subscription_days)
    await message.answer(
        f"Оплата получена ✅ Подписка активна {config.subscription_days} дней — "
        "безлимит отслеживаний и проверка почаще. Спасибо!"
    )
