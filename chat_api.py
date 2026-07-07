import logging
import urllib.parse
import aiohttp

logger = logging.getLogger(__name__)

CHAT_API_BASE = "https://text.pollinations.ai"

SYSTEM_PROMPT = (
    "أنت Artify AI، مساعد ذكي مبتكر تم تطويره بواسطة ريان. "
    "أجب دائماً بـ 3 إلى 6 جمل فقط، موجزة ومفيدة. "
    "إذا سألك المستخدم بالعربية أجب بالعربية، وإذا بالإنجليزية أجب بالإنجليزية. "
    "تتقن: الشخصيات والمشاهير، الدول والجغرافيا، الاقتصاد والمال، التاريخ، العلوم، "
    "الثقافة، الرياضة، والدردشة العامة. "
    "لا تذكر أي جهة خارجية أو نموذج لغوي. أنت Artify AI فقط، تصرف كصديق خبير ودود."
)

FALLBACK_REPLY = "أنا هنا، كيف أقدر أساعدك اليوم؟ 😊"


async def generate_reply(history: list[dict]) -> str:
    last_user_msg = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), ""
    )
    if not last_user_msg:
        return FALLBACK_REPLY

    encoded_prompt = urllib.parse.quote(last_user_msg, safe="")
    encoded_system = urllib.parse.quote(SYSTEM_PROMPT, safe="")
    url = f"{CHAT_API_BASE}/{encoded_prompt}?model=openai&system={encoded_system}&seed=42"

    print(f"[DEBUG] Chat API URL: {url[:120]}...")
    print(f"[DEBUG] User message: {last_user_msg}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=25),
                headers={"Accept": "text/plain"},
            ) as response:
                print(f"[DEBUG] API status: {response.status}")
                text = await response.text()
                print(f"[DEBUG] API raw reply: {text[:200]}")

                if response.status != 200 or not text.strip():
                    logger.warning("Chat API returned HTTP %s or empty body", response.status)
                    return FALLBACK_REPLY

                return text.strip()

    except Exception as e:
        print(f"[DEBUG] Exception: {e}")
        logger.exception("خطأ في الاتصال بـ chat API")
        return FALLBACK_REPLY
