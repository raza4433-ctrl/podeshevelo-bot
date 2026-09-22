import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    db_path: str
    free_watch_limit: int
    free_check_interval_min: int
    paid_check_interval_min: int
    stars_price: int
    subscription_days: int


config = Config(
    bot_token=os.environ["BOT_TOKEN"],
    db_path=os.getenv("DB_PATH", "podeshevelo.db"),
    free_watch_limit=int(os.getenv("FREE_WATCH_LIMIT", "3")),
    free_check_interval_min=int(os.getenv("FREE_CHECK_INTERVAL_MIN", "360")),
    paid_check_interval_min=int(os.getenv("PAID_CHECK_INTERVAL_MIN", "30")),
    stars_price=int(os.getenv("STARS_PRICE", "199")),
    subscription_days=int(os.getenv("SUBSCRIPTION_DAYS", "30")),
)
