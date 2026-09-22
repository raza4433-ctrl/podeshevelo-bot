"""
Общий диспетчер: определяем маркетплейс по ссылке и отдаём нужный парсер.

Каждый парсер экспортирует:
  MARKETPLACE: str
  matches(url) -> bool
  extract_item_id(url) -> str | None
  async fetch_price(url) -> tuple[title: str | None, price_kopecks: int | None]
"""
from . import wildberries, ozon, avito

# Avito временно отключён: банит по IP почти сразу, без прокси/живой сессии
# не работает. Модуль оставлен нетронутым — включить обратно, когда будут
# прокси, достаточно вернуть avito в этот список.
PARSERS = [wildberries, ozon]


def detect_marketplace(url: str):
    for parser in PARSERS:
        if parser.matches(url):
            return parser
    return None
