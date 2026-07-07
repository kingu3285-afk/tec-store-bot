import logging

from aiogram import Router, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery

from utils.subscription import (
    check_subscription,
    get_subscription_keyboard,
    SUBSCRIPTION_MESSAGE,
)

logger = logging.getLogger(__name__)
router = Router(name="common_handler")


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    subscribed = await check_subscription(bot, user.id)

    if not subscribed:
        await message.answer(
            SUBSCRIPTION_MESSAGE,
            reply_markup=get_subscription_keyboard(),
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        f"👋 أهلاً بك <b>{user.full_name}</b>!\n\n"
        "أنا <b>AI Creative Bot</b> 🎨 — بوت متخصص بتوليد الصور بالذكاء الاصطناعي.\n\n"
        "الأوامر المتاحة:\n"
        "/generate — لتوليد صورة جديدة من وصف نصي\n"
        "/help — لعرض المساعدة"
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    subscribed = await check_subscription(bot, message.from_user.id)

    if not subscribed:
        await message.answer(
            SUBSCRIPTION_MESSAGE,
            reply_markup=get_subscription_keyboard(),
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        "📖 <b>طريقة الاستخدام:</b>\n\n"
        "1️⃣ أرسل الأمر /generate\n"
        "2️⃣ اكتب وصفاً للصورة التي تريدها\n"
        "3️⃣ انتظر قليلاً وستصلك الصورة جاهزة ✅\n\n"
        "مثال على وصف جيد:\n"
        "<i>a cute robot reading a book, digital art, 4k</i>\n\n"
        "💡 يمكنك الوصف بالعربية أيضاً والبوت سيفهمه تلقائياً!"
    )


@router.callback_query(lambda c: c.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer("جاري التحقق من اشتراكك...")

    subscribed = await check_subscription(bot, callback.from_user.id)

    if not subscribed:
        await callback.message.edit_text(
            SUBSCRIPTION_MESSAGE + "\n\n⚠️ <b>لم يتم التحقق بعد. تأكد من الاشتراك في جميع القنوات.</b>",
            reply_markup=get_subscription_keyboard(),
            disable_web_page_preview=True,
        )
        return

    await callback.message.delete()
    await callback.message.answer(
        f"✅ <b>تم التحقق من اشتراكك بنجاح!</b>\n\n"
        f"أهلاً بك <b>{callback.from_user.full_name}</b> 🎨\n\n"
        "الأوامر المتاحة:\n"
        "/generate — لتوليد صورة جديدة من وصف نصي\n"
        "/help — لعرض المساعدة"
    )
