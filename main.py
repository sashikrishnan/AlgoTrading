import yfinance as yf
import pandas as pd
import json
import os
import logging

from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import pytz

# Constants
SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
INTERVAL = "30m"
PERIOD = "30d"
REPORT_JSON = "prediction_report.json"
REPORT_PDF = "prediction_report.pdf"
BOUGHT_JSON = "bought_signals.json"
STOP_LOSS_PCT = 0.03
PROFIT_BOOK_PCT = 0.06
BROKERAGE_FEE = 20  # Groww delivery trade fee per order in INR
STT_PCT = 0.001  # 0.1% STT
GST_PCT = 0.18  # GST on brokerage
TRANSACTION_CHARGES_PCT = 0.0000325  # 0.00325% Transaction charges

# Set up logging
logging.basicConfig(
    level=logging.INFO,  # You can change the level to DEBUG, WARNING, etc.
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]  # This will output logs to console
)

# Fetch data from Yahoo Finance
def fetch_data(symbol):
    return yf.download(symbol, interval=INTERVAL, period=PERIOD)

# Compute indicators
def compute_indicators(df):
    df["EMA12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA26"] = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

# Generate BUY/SELL signals
def generate_signal(df):
    df = compute_indicators(df)
    predictions = []

    if len(df) < 2:
        return predictions

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    '''if (float(prev["MACD"]) < float(prev["Signal"]) and
        float(curr["MACD"]) > float(curr["Signal"]) and
        float(curr["RSI"]) < 70):'''

    # RSI has fallen below 30 and then becomes >= 30 and MACD crosover has not yet taken place(laggy indicator)
    if (float(prev["RSI"]) < 30 and 
        float(curr["RSI"]) >= 30 and 
        float(prev["MACD"]) < float(prev["Signal"]) and
        float(curr["MACD"]) < float(curr["Signal"])): 
        predictions.append({
            "symbol": df.name,
            "price": float(curr["Close"]),
            "macd": float(curr["MACD"]),
            "rsi": float(curr["RSI"]),
            "prediction": "BUY",
            "date": curr.name.strftime("%Y-%m-%d %H:%M")
        })
    else:
        predictions.append({
            "symbol": df.name,
            "price": float(curr["Close"]),
            "macd": float(curr["MACD"]),
            "rsi": float(curr["RSI"]),
            "prediction": "NONE",
            "date": curr.name.strftime("%Y-%m-%d %H:%M")
        })

    return predictions

# Load or initialize bought signals
def load_bought_signals():
    if os.path.exists(BOUGHT_JSON):
        try:
            with open(BOUGHT_JSON, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error("❌ Error reading {BOUGHT_JSON}. File is corrupted or not properly formatted.", BOUGHT_JSON)
            return []  # Return an empty list if the file is invalid
    return []

def save_bought_signals(data):
    with open(BOUGHT_JSON, "w") as f:
        json.dump(data, f, indent=4)
    logging.info("✅ %s saved.", BOUGHT_JSON)

# Generate SELL signals based on criteria and include brokerage calculation
def check_sell_signals(bought_signals, latest_prices):
    sell_signals = []
    updated_bought = []

    for entry in bought_signals:
        symbol = entry["symbol"]
        buy_price = entry["price"]
        buy_date = entry["date"]
        units = entry["units"]  # Fetch the number of units
        current_price = latest_prices.get(symbol)

        if current_price:
            # Brokerage Calculation (Groww-style) 
            turnover = (buy_price * units) + (current_price * units)
            brokerage = 20 * 2
            stt = turnover * (0.1/100)
            exchange_charges = turnover * (0.0035/100)
            sebi_turnover_fee = turnover * (0.0001/100)
            gst = (brokerage + exchange_charges + sebi_turnover_fee) * (18/100)
            stamp_duty = (buy_price * units) * (0.015/100) 
            dp_charges = 18.25 + (18.25 * (18/100)) 
            total_charges = brokerage + stt + exchange_charges + sebi_turnover_fee + gst + stamp_duty + dp_charges 

            # Profit after brokerage
            profit_after_brokerage = (current_price * units) - (buy_price * units) - total_charges
            profit_pct = profit_after_brokerage/(buy_price * units) * 100

            if current_price <= buy_price * (1 - STOP_LOSS_PCT):
                sell_signals.append({
                    "symbol": symbol,
                    "action": "SELL (Stop Loss)",
                    "buy_price": buy_price,
                    "sell_price": current_price,
                    "units": entry.get("units", 1),
                    "profit_pct": round(profit_pct),
                    "profit_after_brokerage": round(profit_after_brokerage, 2),
                    "date": buy_date
                })
            elif current_price >= buy_price * (1 + PROFIT_BOOK_PCT):
                sell_signals.append({
                    "symbol": symbol,
                    "action": "SELL (Profit Book)",
                    "buy_price": buy_price,
                    "sell_price": current_price,
                    "units": entry.get("units", 1),
                    "profit_pct": round(profit_pct),
                    "profit_after_brokerage": round(profit_after_brokerage, 2),
                    "date": buy_date
                })
            else:
                updated_bought.append(entry)
        else:
            updated_bought.append(entry)

    save_bought_signals(updated_bought)
    return sell_signals

def save_report_to_json(report_data, report_file=REPORT_JSON):
    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=4)
    logging.info("✅ %s saved.", report_file)

def save_report_to_pdf(report_data, report_file=REPORT_PDF):
    tz_ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz_ist).strftime("%Y-%m-%d %H:%M:%S")

    doc = SimpleDocTemplate(report_file, pagesize=letter)
    styles = getSampleStyleSheet()
    content = [Paragraph("<b>Stock Prediction Report</b>", styles["Title"]), Spacer(1, 12)]

    table_data = [["Symbol", "Price", "MACD", "RSI", "Prediction"]]
    for entry in report_data:
        table_data.append([
            entry["symbol"],
            f'{entry["price"]:.2f}',
            f'{entry["macd"]:.2f}',
            f'{entry["rsi"]:.2f}',
            entry["prediction"]
        ])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
    ]))

    content.append(table)
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Generated on: {now_ist} IST", styles["Normal"]))

    doc.build(content)
    logging.info("✅ %s saved.", report_file)

# Save sell signal report
def save_sell_signal_report_to_json(sell_signals):
    with open("sell_signals.json", "w") as f:
        json.dump(sell_signals, f, indent=4)
    logging.info("✅ sell_signals.json saved.")

def save_sell_signal_report_to_pdf(sell_signals):
    tz_ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz_ist).strftime("%Y-%m-%d %H:%M:%S")

    doc = SimpleDocTemplate("sell_signals.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    content = [Paragraph("<b>Sell Signal Report</b>", styles["Title"]), Spacer(1, 12)]

    table_data = [["Symbol", "Action", "Buy Price", "Sell Price", "Units", "Profit Pct", "Profit Value", "Date"]]
    for entry in sell_signals:
        table_data.append([
            entry["symbol"],
            entry["action"],
            f'{entry["buy_price"]:.2f}',
            f'{entry["sell_price"]:.2f}',
            entry["units"],
            f'{entry["profit_pct"]:.2f}',  # Display profit as actual value
            f'{entry["profit_after_brokerage"]:.2f}',  # Display profit as actual value
            entry["date"]
        ])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
    ]))

    content.append(table)
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Generated on: {now_ist} IST", styles["Normal"]))

    doc.build(content)
    logging.info("✅ Sell Signal PDF saved.")

# Main
def main():
    all_predictions = []
    latest_prices = {}

    for symbol in SYMBOLS:
        df = fetch_data(symbol)
        df.name = symbol
        predictions = generate_signal(df)
        all_predictions.extend(predictions)

        if predictions:
            latest_prices[symbol] = predictions[-1]["price"]

    # Combine prediction and sell signals for report
    save_report_to_json(all_predictions)  # Prediction Report
    save_report_to_pdf(all_predictions)  # Prediction PDF

    # Unit Test
    #latest_prices = {
    #"RELIANCE.NS": 2400.0,  # ↓ 4% (trigger stop loss, 3% threshold)
    #"TCS.NS": 3850.0        # ↑ 6.9% (trigger profit booking, 6% threshold)
    #}

    bought_signals = load_bought_signals()

    # Update bought list with new buys
    new_buys = [p for p in all_predictions if p["prediction"] == "BUY"]
    bought_signals.extend(new_buys)
    save_bought_signals(bought_signals)

    # After selling signals have been identified
    sell_signals = check_sell_signals(bought_signals, latest_prices)

    if sell_signals:
        save_sell_signal_report_to_json(sell_signals)  # Sell Signal Report
        save_sell_signal_report_to_pdf(sell_signals)  # Sell Signal PDF
    else:
        # Remove old file if no new sell signals
        if os.path.exists("sell_signals.json"):
            os.remove("sell_signals.json")
            logging.info("✅ Old Sell Signal json removed.")

        if os.path.exists("sell_signals.pdf"):
            os.remove("sell_signals.pdf")
            logging.info("✅ Old Sell Signal pdf removed.")

if __name__ == "__main__":
    main()
