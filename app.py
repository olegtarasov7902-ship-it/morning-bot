import os
import random
import requests
from flask import Flask
import feedparser
import telegram

app = Flask(__name__)

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["GROUP_CHAT_ID"]
RSS_URL = os.environ["PINTEREST_RSS"]  # одна доска для всех случаев

# Если позже захотите разные доски, можно добавить:
# MORNING_RSS = os.environ.get("MORNING_RSS", RSS_URL)
# AFTERNOON_RSS = os.environ.get("AFTERNOON_RSS", RSS_URL)
# EVENING_RSS = os.environ.get("EVENING_RSS", RSS_URL)

bot = telegram.Bot(token=TOKEN)

def get_random_pinterest_image(rss_url):
    """Парсим RSS и возвращаем URL случайной картинки."""
    feed = feedparser.parse(rss_url)
    images = []
    for entry in feed.entries:
        if "description" in entry and "img src" in entry.description:
            start = entry.description.find('src="') + 5
            end = entry.description.find('"', start)
            if start > 4 and end > 0:
                img_url = entry.description[start:end]
                images.append(img_url)
    if not images:
        raise Exception("Не удалось найти изображения в RSS")
    return random.choice(images)

def send_greeting(caption, rss_feed=None):
    """Общая функция: получает картинку и отправляет в чат."""
    if rss_feed is None:
        rss_feed = RSS_URL
    img_url = get_random_pinterest_image(rss_feed)
    bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption)

@app.route("/morning")
def morning():
    send_greeting("Доброе утро! 🌅")
    return "Morning sent", 200

@app.route("/afternoon")
def afternoon():
    send_greeting("Добрый день! ☀️")
    return "Afternoon sent", 200

@app.route("/evening")
def evening():
    send_greeting("Добрый вечер! 🌙")
    return "Evening sent", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
