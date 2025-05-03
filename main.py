from telegram import Bot
import os

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
bot.send_message(chat_id=os.getenv("TELEGRAM_CHAT_ID"), text="📈 Hello from GitHub Actions!")
