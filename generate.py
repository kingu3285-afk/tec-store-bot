import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatAction
from aiogram.types import Message, BufferedInputFile

import utils.stats as stats
from services.image_api import generate_image, ImageGenerationError, is_arabic
from utils.states import GenerateImageStates
from utils.subscription import (
    check_subscription,
    get_subscription_keyboard,
    SUBSCRIPTION_MESSAGE,
)

logger = logging.getLogger(__name__)
router = Router(name="generate_handler")


async def _require_subscription(message: Message, bot: Bot) -> bool:
    subscribed = await check_subscription(bot, message.from_user.id)
    if not subscribed:
        await message.answer(
            SUBSCRIPTION_MESSAGE,
            reply_markup=get_subscription_keyboard(),
            disable_web_page_preview=True,
        )
    return subscribed


@router.message(Command("generate"))
async def cmd_generate(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _require_subscription(message, bot):
        return

    await message.answer(
        "🎨 حسناً! أرسل لي الآن وصفاً للصورة التي تريد توليدها.\n\n"
        "مثال:\n"
        "<i>a futuristic city at sunset, cinematic lighting</i>\n\n"
        "💡 يمكنك الكتابة بالعربية أو الإنجليزية والبوت سيفهمك!"
    )
    await state.set_state(GenerateImageStates.waiting_for_prompt)


@router.message(StateFilter(GenerateImageStates.waiting_for_prompt), F.text)
async def process_prompt(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _require_subscription(message, bot):
        await state.clear()
        return

    prompt = message.text.strip()

    if len(prompt) < 3:
        await message.answer("⚠️ الرجاء إرسال وصف أوضح للصورة (3 أحرف على الأقل).")
        return

    lang_note = "🌐 تم اكتشاف وصف عربي وسيتم معالجته تلقائياً." if is_arabic(prompt) else ""
    status_text = f"⏳ جاري توليد الصورة، قد يستغرق هذا بضع ثوانٍ...{chr(10) + lang_note if lang_note else ''}"
    status_message = await message.answer(status_text)
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)

    stats.users.add(message.from_user.id)

    try:
        image_bytes = await generate_image(prompt)

        photo_file = BufferedInputFile(image_bytes, filename="ai_creative_bot.png")

        await message.answer_photo(
            photo=photo_file,
            caption=f"✅ تم توليد الصورة بنجاح!\n\n📝 الوصف: <i>{prompt}</i>"
        )
        stats.images_generated += 1

    except ImageGenerationError as e:
        logger.error(f"فشل توليد الصورة للمستخدم {message.from_user.id}: {e}")
        await message.answer(
            "❌ عذراً، حدث خطأ أثناء توليد الصورة. حاول مرة أخرى بوصف مختلف."
        )

    finally:
        await status_message.delete()
        await state.clear()
