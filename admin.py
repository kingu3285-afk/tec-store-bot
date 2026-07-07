import logging

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import utils.stats as stats

logger = logging.getLogger(__name__)
router = Router(name="admin_handler")

ADMIN_ID = 7233186756


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🛠 <b>لوحة الإدارة</b>\n\n"
        f"🖼 الصور المُولَّدة: <b>{stats.images_generated}</b>\n"
        f"👥 المستخدمون النشطون: <b>{len(stats.users)}</b>\n\n"
        "📢 للإذاعة: <code>/broadcast رسالتك هنا</code>"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("⚠️ اكتب الرسالة بعد الأمر:\n<code>/broadcast نص الرسالة</code>")
        return

    if not stats.users:
        await message.answer("⚠️ لا يوجد مستخدمون بعد.")
        return

    sent, failed = 0, 0
    status = await message.answer(f"⏳ جاري الإرسال لـ {len(stats.users)} مستخدم...")

    for user_id in list(stats.users):
        try:
            await bot.send_message(user_id, f"📢 <b>رسالة من الإدارة:</b>\n\n{text}")
            sent += 1
        except Exception:
            failed += 1

    await status.edit_text(
        f"✅ <b>اكتملت الإذاعة</b>\n\n"
        f"• أُرسلت: {sent}\n"
        f"• فشلت: {failed} (محظور أو غير موجود)"
    )
    logger.info(f"Broadcast: sent={sent}, failed={failed}")
