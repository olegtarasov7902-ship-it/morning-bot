import os
import random
import traceback
import requests
from flask import Flask
import feedparser
import telegram

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("GROUP_CHAT_ID")
RSS_URL = os.environ.get("PINTEREST_RSS")

if not TOKEN or not CHAT_ID or not RSS_URL:
    raise RuntimeError("Не задана одна из переменных окружения: BOT_TOKEN, GROUP_CHAT_ID, PINTEREST_RSS")

bot = telegram.Bot(token=TOKEN)

def get_random_pinterest_image(rss_url):
    """Парсим RSS от RSS.app и возвращаем URL случайной картинки."""
    feed = feedparser.parse(rss_url)
    images = []

    if not feed.entries:
        raise Exception("RSS-лента пуста или недоступна. Проверьте ссылку.")

    for entry in feed.entries:
        # Способ 1: media_content (основной для RSS.app)
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                url = media.get('url')
                if url and url.startswith('http'):
                    images.append(url)
                    break  # берём только первую картинку из media_content

        # Если в media_content не нашли — пробуем enclosures
        if not images and hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                href = enc.get('href') or enc.get('url')
                if href and href.startswith('http'):
                    images.append(href)
                    break

        # Способ 3: старый поиск в description (на всякий случай)
        if not images and 'description' in entry:
            desc = entry.description
            start = desc.find('src="')
            if start != -1:
                start += 5
                end = desc.find('"', start)
                if end > 0:
                    img_url = desc[start:end]
                    images.append(img_url)

    if not images:
        raise Exception(
            "Не удалось найти изображения в RSS-ленте. "
            "Возможно, лента не содержит картинок или изменилась структура. "
            "Проверьте RSS-ссылку."
        )
    return random.choice(images)

def send_greeting(caption):
    img_url = get_random_pinterest_image(RSS_URL)
    bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption)

@app.route("/morning")
def morning():
    try:
        send_greeting("Доброе утро! 🌅")
        return "Утро отправлено", 200
    except Exception as e:
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
