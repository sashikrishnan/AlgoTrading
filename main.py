import os
import logging
import yfinance as yf
import pandas as pd
import ta
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Telegram secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# List of stock symbols to monitor
symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

def fetch_data(symbol, interval="30m", period="30d"):
    df = yf.download(symbol, interval=interval, period=period)
    df.dropna(inplace=True)
    return df

def add_indicators(df):
    df["ema_12"] = ta.trend.ema_indicator(df["Close"], window=12)
    df["ema_26"] = ta.trend.ema_indicator(df["Close"], window=26)
    df["rsi"] = ta.momentum.rsi(df["Close"], window=14)
    macd = ta.trend.macd(df["Close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    return df

def generate_signal(df):
    latest = df.iloc[-1]
    previous = df.iloc[-2]
    if previous["macd"] < previous["macd_signal"] and latest["macd"] > latest["macd_signal"] and latest["rsi"] < 70:
        return "BUY"
    elif previous["macd"] > previous["macd_signal"] and latest["macd"] < latest["macd_signal"] and latest["rsi"] > 30:
        return "SELL"
    else:
        return "HOLD"

def send_telegram_message(text):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    response = requests.post(TELEGRAM_URL, data=payload)
    if response.status_code != 200:
        logger.error(f"Failed to send message: {response.text}")

if __name__ == "__main__":
    logger.info("📊 Starting analysis...")
    for symbol in symbols:
        try:
            df = fetch_data(symbol)
            df = add_indicators(df)
            signal = generate_signal(df)
            message = f"*{symbol}* → 📈 *{signal}*"
            send_telegram_message(message)
            logger.info(message)
        except Exception as e:
            logger.error(f"❌ Error processing {symbol}: {e}")

