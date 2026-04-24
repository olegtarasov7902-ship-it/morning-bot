import os
import random
import traceback
import requests
from flask import Flask, request
import feedparser
import telegram

app = Flask(__name__)

# Переменные окружения (должны быть заданы на Render)
TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("GROUP_CHAT_ID")
RSS_URL = os.environ.get("PINTEREST_RSS")

# Простая проверка, чтобы сразу увидеть проблему, если переменные не заданы
if not TOKEN or not CHAT_ID or not RSS_URL:
    raise RuntimeError("Не задана одна из переменных окружения: BOT_TOKEN, GROUP_CHAT_ID, PINTEREST_RSS")

bot = telegram.Bot(token=TOKEN)

def get_random_pinterest_image(rss_url):
    """Парсим RSS и возвращаем URL случайной картинки."""
    feed = feedparser.parse(rss_url)
    images = []
    # Иногда feedparser возвращает ошибку, это нормально, но картинок может не быть
    if feed.entries:
        for entry in feed.entries:
            if "description" in entry and "img src" in entry.description:
                start = entry.description.find('src="') + 5
                end = entry.description.find('"', start)
                if start > 4 and end > 0:
                    img_url = entry.description[start:end]
                    images.append(img_url)
    if not images:
        raise Exception("Не удалось найти изображения в RSS-ленте. Проверьте ссылку и парсинг.")
    return random.choice(images)

def send_greeting(caption):
    """Получает случайную картинку и отправляет в чат."""
    img_url = get_random_pinterest_image(RSS_URL)
    bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption)

@app.route("/morning")
def morning():
    try:
        send_greeting("Доброе утро! 🌅")
        return "Утро отправлено", 200
    except Exception as e:
        # Возвращаем traceback, чтобы увидеть ошибку прямо в браузере
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/afternoon")
def afternoon():
    try:
        send_greeting("Добрый день! ☀️")
        return "День отправлен", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/evening")
def evening():
    try:
        send_greeting("Добрый вечер! 🌙")
        return "Вечер отправлен", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
