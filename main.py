import os
import requests

import logging
logging.basicConfig(level=logging.INFO)

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if bot_token and chat_id:
    logging.info("✅ Secrets loaded successfully.")
else:
    logging.error("❌ Missing bot token or chat ID.")

message = "📈 Hello from GitHub Actions!"

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
payload = {"chat_id": chat_id, "text": message}

logging.info("Sending message")
response = requests.post(url, data=payload)
print("Status code:", response.status_code)
print("Response:", response.text)

