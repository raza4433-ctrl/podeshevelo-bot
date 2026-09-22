"""
Хранилище на SQLite (aiosqlite — асинхронно, без блокировки event loop).
"""
import aiosqlite

from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    is_paid INTEGER NOT NULL DEFAULT 0,
    paid_until TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    marketplace TEXT NOT NULL,
    item_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    last_price INTEGER,
    last_checked_at TEXT,
    check_interval_min INTEGER NOT NULL,
    last_check_ok INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def ensure_user(user_id: int, username: str | None) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username),
        )
        await db.commit()


async def get_user(user_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()


def _check_interval_for(is_paid: bool) -> int:
    return config.paid_check_interval_min if is_paid else config.free_check_interval_min


async def count_active_watches(user_id: int) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM watches WHERE user_id = ? AND active = 1", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0]


async def add_watch(
    user_id: int, marketplace: str, item_id: str, url: str, title: str | None, price: int | None
) -> int:
    user = await get_user(user_id)
    is_paid = bool(user["is_paid"]) if user else False
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute(
            "INSERT INTO watches "
            "(user_id, marketplace, item_id, url, title, last_price, last_checked_at, check_interval_min) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (user_id, marketplace, item_id, url, title, price, _check_interval_for(is_paid)),
        )
        await db.commit()
        return cursor.lastrowid


async def find_watch(user_id: int, marketplace: str, item_id: str) -> aiosqlite.Row | None:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM watches WHERE user_id = ? AND marketplace = ? AND item_id = ? AND active = 1",
            (user_id, marketplace, item_id),
        )
        return await cursor.fetchone()


async def list_watches(user_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM watches WHERE user_id = ? AND active = 1 ORDER BY created_at DESC",
            (user_id,),
        )
        return await cursor.fetchall()


async def deactivate_watch(user_id: int, watch_id: int) -> bool:
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute(
            "UPDATE watches SET active = 0 WHERE id = ? AND user_id = ?", (watch_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def watches_due_for_check() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM watches WHERE active = 1 AND ("
            "  last_checked_at IS NULL OR "
            "  datetime(last_checked_at, '+' || check_interval_min || ' minutes') <= datetime('now')"
            ")"
        )
        return await cursor.fetchall()


async def set_subscription(user_id: int, days: int) -> None:
    """Активирует/продлевает подписку и разгоняет проверку уже добавленных
    отслеживаний до платного интервала."""
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "UPDATE users SET is_paid = 1, paid_until = datetime('now', ?) WHERE user_id = ?",
            (f"+{days} days", user_id),
        )
        await db.execute(
            "UPDATE watches SET check_interval_min = ? WHERE user_id = ? AND active = 1",
            (config.paid_check_interval_min, user_id),
        )
        await db.commit()


async def downgrade_expired_subscriptions() -> None:
    """Раз в цикл проверки цен: у кого подписка истекла — снимаем is_paid
    и возвращаем бесплатный (более редкий) интервал проверки."""
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE is_paid = 1 AND paid_until < datetime('now')"
        )
        expired = [row["user_id"] for row in await cursor.fetchall()]
        if not expired:
            return
        await db.execute(
            "UPDATE users SET is_paid = 0 WHERE is_paid = 1 AND paid_until < datetime('now')"
        )
        placeholders = ",".join("?" * len(expired))
        await db.execute(
            f"UPDATE watches SET check_interval_min = ? WHERE user_id IN ({placeholders}) AND active = 1",
            (config.free_check_interval_min, *expired),
        )
        await db.commit()


async def update_watch_price(watch_id: int, price: int, ok: bool) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        if ok:
            await db.execute(
                "UPDATE watches SET last_price = ?, last_checked_at = CURRENT_TIMESTAMP, "
                "last_check_ok = 1 WHERE id = ?",
                (price, watch_id),
            )
        else:
            await db.execute(
                "UPDATE watches SET last_checked_at = CURRENT_TIMESTAMP, last_check_ok = 0 "
                "WHERE id = ?",
                (watch_id,),
            )
        await db.commit()
