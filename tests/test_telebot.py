import requests

TELEGRAM_BOT_TOKEN="8609329859:AAGvv0O2Pvwoa_ZXQOnef7aqO6Evq1F8wc4"
TELEGRAM_CHAT_ID="5880878517"

message = "Hello, this is a test message from the Telegram bot!"

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

payload = {
    "chat_id": TELEGRAM_CHAT_ID,
    "text": message
}

response = requests.post(url, json=payload)
