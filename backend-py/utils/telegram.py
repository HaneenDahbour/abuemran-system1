import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "")


async def notify_admin(message: str):
    if not TELEGRAM_TOKEN or not MANAGER_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": MANAGER_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
    except Exception:
        pass
