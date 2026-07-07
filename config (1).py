import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

IMAGE_API_KEY: str = os.getenv("IMAGE_API_KEY", "")

POLLINATIONS_BASE_URL: str = "https://image.pollinations.ai/prompt"

if not BOT_TOKEN:
    raise ValueError(
        "❌ لم يتم العثور على BOT_TOKEN! "
        "تأكد من إنشاء ملف .env ووضع التوكن بداخله."
    )
