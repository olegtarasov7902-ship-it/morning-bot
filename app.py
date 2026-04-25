import sys
import os
import traceback
import random
import requests
from flask import Flask
import feedparser

# ---------- ДИАГНОСТИКА ----------
print("--- НАЧАЛО ДИАГНОСТИКИ ---")
print(f"Python version: {sys.version}")
print(f"cwd: {os.getcwd()}")
for var in ['BOT_TOKEN', 'GROUP_CHAT_ID', 'PINTEREST_RSS']:
    val = os.environ.get(var)
    print(f"{var} задан: {'Да' if val else 'НЕТ'} (длина {len(val) if val else 0})")
for lib in ['flask', 'feedparser', 'requests']:
    try:
        __import__(lib)
        print(f"Библиотека '{lib}' импортирована успешно")
    except Exception as e:
        print(f"!!! ОШИБКА импорта '{lib}': {e}")
print("--- КОНЕЦ ДИАГНОСТИКИ ---")

app = Flask(__name__)

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["GROUP_CHAT_ID"]
RSS_URL = os.environ["PINTEREST_RSS"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def send_telegram_message(text):
    """Отправка простого текста через прямой вызов API."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def send_telegram_photo(image_url, caption):
    """Отправка фото через прямой вызов API."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    params = {"chat_id": CHAT_ID, "photo": image_url, "caption": caption}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def get_random_pinterest_image(rss_url):
    """Парсим RSS и возвращаем URL случайной картинки."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get(rss_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise Exception(f"Не удалось загрузить RSS-ленту: {e}")

    feed = feedparser.parse(resp.content)
    images = []

    if not feed.entries:
        raise Exception("RSS-лента пуста или недоступна.")

    for entry in feed.entries:
        # media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                url = media.get('url')
                if url and url.startswith('http'):
                    images.append(url)
                    break
        # enclosures
        if not images and hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                href = enc.get('href') or enc.get('url')
                if href and href.startswith('http'):
                    images.append(href)
                    break
        # img src
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
        raise Exception("Не удалось найти изображения в RSS-ленте.")
    return random.choice(images)

# ---------- Основные маршруты ----------
@app.route("/morning")
def morning():
    try:
        img_url = get_random_pinterest_image(RSS_URL)
        send_telegram_photo(img_url, "Доброе утро! 🌅")
        return "Утро отправлено", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/afternoon")
def afternoon():
    try:
        img_url = get_random_pinterest_image(RSS_URL)
        send_telegram_photo(img_url, "Добрый день! ☀️")
        return "День отправлен", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/evening")
def evening():
    try:
        img_url = get_random_pinterest_image(RSS_URL)
        send_telegram_photo(img_url, "Добрый вечер! 🌙")
        return "Вечер отправлен", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

# ---------- Тестовые маршруты ----------
@app.route("/test")
def test():
    try:
        result = send_telegram_message("Тест: бот работает!")
        return f"Тестовое сообщение отправлено: {result}", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/testphoto")
def testphoto():
    try:
        test_url = "https://telegram.org/img/t_logo.png"
        result = send_telegram_photo(test_url, "Тестовая картинка")
        return f"Тестовое фото отправлено: {result}", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/testdirect")
def testdirect():
    """Супер-прямой вызов API, идентичный ручному тесту из браузера."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": "hello_world_direct"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("ok"):
            return f"Прямой тест пройден: {data}", 200
        else:
            return f"Ошибка Telegram: {data}", 500
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

if __name__ == "__main__":
    print("Запуск Flask...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
