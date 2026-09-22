"""
Общий headless-браузер (Playwright/Chromium) для сайтов с сильным
антиботом (сейчас — Ozon), которые блокируют обычные HTTP-запросы
JS-челленджем. Браузер поднимается один раз и переиспользуется —
запуск нового процесса Chromium на каждую проверку цены был бы слишком
медленным и прожорливым.
"""
import asyncio
import logging

from playwright.async_api import async_playwright, Browser, Playwright

_playwright: Playwright | None = None
_browser: Browser | None = None
_lock = asyncio.Lock()

_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def _get_browser() -> Browser:
    global _playwright, _browser
    async with _lock:
        if _browser is None or not _browser.is_connected():
            if _playwright is None:
                _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
        return _browser


async def fetch_rendered_html(url: str, wait_selector: str | None = None, timeout_ms: int = 25000) -> str | None:
    """Открывает страницу в headless-браузере и возвращает итоговый HTML
    (после выполнения JS/антибот-челленджа). None при ошибке/таймауте."""
    try:
        browser = await _get_browser()
        context = await browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        await context.add_init_script(_STEALTH_INIT_SCRIPT)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    pass
            else:
                await page.wait_for_timeout(3000)
            html = await page.content()
            return html
        finally:
            await context.close()
    except Exception:
        logging.exception("Headless-браузер не смог открыть %s", url)
        return None


async def shutdown() -> None:
    global _playwright, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None
