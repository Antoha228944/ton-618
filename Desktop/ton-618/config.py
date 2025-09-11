import os

# Telegram bot token is loaded from environment; falls back to provided test token
# To override: export BOT_TOKEN="123:ABC"
BOT_TOKEN = os.getenv("BOT_TOKEN", "8358851724:AAEVVzB4EqDqmWNLjrAnW2mZVnALCzPqWzw")

if not BOT_TOKEN:
    print("⚠️ BOT_TOKEN is not set. Please export BOT_TOKEN in your environment.")
