from telegram import Bot
import os

import logging
logging.basicConfig(level=logging.INFO)

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if bot_token and chat_id:
    logging.info("✅ Secrets loaded successfully.")
else:
    logging.error("❌ Missing bot token or chat ID.")

# inside script:
logger.info("Sending message")
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
bot.send_message(chat_id=os.getenv("TELEGRAM_CHAT_ID"), text="📈 Hello from GitHub Actions!")
