import asyncio
import logging
import os
import re as _re

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN
from handlers import common, generate, admin, chat

PORT = int(os.environ.get("PORT", 6000))
BASE_PATH = "/api"
WEBHOOK_PATH = f"{BASE_PATH}/webhook"
_raw_secret = os.environ.get("SESSION_SECRET", "artify-webhook-secret-2026")
WEBHOOK_SECRET = _re.sub(r"[^A-Za-z0-9_-]", "", _raw_secret)[:256] or "artify-webhook-2026"


def _get_webhook_url() -> str:
    domains = os.environ.get("REPLIT_DOMAINS", "")
    if not domains:
        return ""
    host = domains.split(",")[0].strip()
    return f"https://{host}{WEBHOOK_PATH}"


async def _on_startup(bot: Bot) -> None:
    logger = logging.getLogger(__name__)
    url = _get_webhook_url()
    if url:
        await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
        logger.info("✅ Webhook registered: %s", url)
    else:
        logger.warning("⚠️  REPLIT_DOMAINS not set — webhook not registered (dev mode)")


async def _on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(generate.router)
    dp.include_router(chat.router)

    dp.startup.register(_on_startup)
    dp.shutdown.register(_on_shutdown)

    app = web.Application()

    async def health(_req: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot": "running"})

    app.router.add_get(f"{BASE_PATH}/healthz", health)
    app.router.add_get(f"{BASE_PATH}/health", health)
    app.router.add_get("/", health)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    ).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info("🚀 Bot webhook server running on port %d", PORT)
    logger.info("🔗 Webhook path: %s", WEBHOOK_PATH)

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⛔ Bot stopped.")
