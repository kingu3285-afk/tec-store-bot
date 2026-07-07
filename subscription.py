import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)

CHANNELS = [
    {"username": "@Tec_store",  "url": "https://t.me/Tec_store",  "title": "Tec Store"},
    {"username": "@TECstore9",  "url": "https://t.me/TECstore9",  "title": "TEC Store 9"},
]

SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}


async def check_subscription(bot: Bot, user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            if member.status not in SUBSCRIBED_STATUSES:
                return False
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"تعذّر التحقق من القناة {channel['username']}: {e}")
            return False
        except Exception as e:
            logger.exception(f"خطأ غير متوقع عند التحقق من القناة {channel['username']}: {e}")
            return False
    return True


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"📢 {ch['title']}", url=ch["url"])]
        for ch in CHANNELS
    ]
    buttons.append([
        InlineKeyboardButton(text="✅ تحققت من اشتراكي", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


SUBSCRIPTION_MESSAGE = (
    "🔒 <b>للمتابعة، يرجى الاشتراك في القنوات التالية:</b>\n\n"
    + "\n".join(f"• <a href='{ch['url']}'>{ch['title']}</a>" for ch in CHANNELS)
    + "\n\n"
    "بعد الاشتراك، اضغط على الزر أدناه للتحقق ✅"
)
