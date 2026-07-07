import logging
from collections import defaultdict, deque

from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state
from aiogram.types import Message

from services.chat_api import generate_reply
from utils.subscription import check_subscription, get_subscription_keyboard, SUBSCRIPTION_MESSAGE

logger = logging.getLogger(__name__)
router = Router(name="chat_handler")

_MAX_HISTORY = 5
_user_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=_MAX_HISTORY * 2))


@router.message(StateFilter(default_state), F.text)
async def handle_chat(message: Message, bot: Bot) -> None:
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            SUBSCRIPTION_MESSAGE,
            reply_markup=get_subscription_keyboard(),
            disable_web_page_preview=True,
        )
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    uid = message.from_user.id
    history = _user_history[uid]

    history.append({"role": "user", "content": message.text})

    reply = await generate_reply(list(history))

    history.append({"role": "assistant", "content": reply})

    await message.answer(f"🤖 {reply}")
