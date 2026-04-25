import sys
import os
import traceback
import random
import requests
from flask import Flask
import feedparser

# ---------- ДИАГНОСТИКА (видна в логах Render) ----------
print("--- НАЧАЛО ДИАГНОСТИКИ ---")
print(f"Python version: {sys.version}")
print(f"Рабочая директория: {os.getcwd()}")
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

# ---------- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ----------
TOKEN = os.environ["BOT_TOKEN"]           # токен Telegram-бота
CHAT_ID = os.environ["GROUP_CHAT_ID"]     # ID вашей группы
RSS_URL = os.environ["PINTEREST_RSS"]     # RSS-лента (сейчас Reddit r/streetwear)

# ---------- ЗАЩИТА ОТ ПОВТОРОВ ----------
recent_images = []  # список недавно отправленных URL
MAX_RECENT = 10     # сколько последних фото исключать из выбора

# ---------- ФУНКЦИИ ДЛЯ ПРЯМОЙ ОТПРАВКИ В TELEGRAM ----------
def send_telegram_message(text):
    """Отправка простого текста через Telegram API."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def send_telegram_photo(image_url, caption):
    """Отправка фото + запоминание URL в истории для избежания повторов."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    params = {"chat_id": CHAT_ID, "photo": image_url, "caption": caption}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    # Сохраняем URL в истории
    recent_images.append(image_url)
    if len(recent_images) > MAX_RECENT:
        recent_images.pop(0)
    return r.json()

# ---------- ОБРАБОТКА RSS ----------
def clean_image_url(url):
    """Превращает превью Reddit (preview.redd.it) в полноразмерное (i.redd.it) и удаляет параметры."""
    if 'preview.redd.it' in url:
        url = url.replace('preview.redd.it', 'i.redd.it')
        if '?' in url:
            url = url.split('?')[0]
    return url

def get_random_pinterest_image(rss_url):
    """Парсит RSS и возвращает URL случайной картинки, которая ещё не была в recent_images."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
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
        img_url = None
        # Способ 1: media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                url = media.get('url')
                if url and url.startswith('http'):
                    img_url = url
                    break
        # Способ 2: enclosures
        if not img_url and hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                href = enc.get('href') or enc.get('url')
                if href and href.startswith('http'):
                    img_url = href
                    break
        # Способ 3: поиск <img src...> в описании
        if not img_url and 'description' in entry:
            desc = entry.description
            start = desc.find('src="')
            if start != -1:
                start += 5
                end = desc.find('"', start)
                if end > 0:
                    img_url = desc[start:end]
        if img_url:
            img_url = clean_image_url(img_url)
            images.append(img_url)

    if not images:
        raise Exception("Не удалось найти изображения в RSS-ленте.")

    # Исключаем недавно отправленные, чтобы не повторяться
    fresh_images = [img for img in images if img not in recent_images]
    if not fresh_images:   # если все уже были — берём любую
        fresh_images = images

    return random.choice(fresh_images)

# ---------- ПОГОДА ДЛЯ КАМЫШИНА (Open-Meteo) ----------
def get_weather_kamyshin():
    """Актуальная погода в Камышине на момент запроса."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 50.0531,
        "longitude": 45.3761,
        "current_weather": "true",
        "timezone": "Europe/Moscow"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()["current_weather"]
        weather_codes = {
            0: "Ясно", 1: "Малооблачно", 2: "Облачно", 3: "Пасмурно",
            45: "Туман", 48: "Изморозь", 51: "Морось", 53: "Морось",
            55: "Ледяная морось", 61: "Дождь", 63: "Дождь", 65: "Ливень",
            71: "Снег", 73: "Снегопад", 75: "Сильный снег", 95: "Гроза"
        }
        desc = weather_codes.get(data["weathercode"], "Непонятно")
        return f"🌤 Сейчас в Камышине: {desc}, {data['temperature']}°C\n💨 Ветер: {data['windspeed']} км/ч"
    except Exception as e:
        print(f"Ошибка получения погоды: {e}")
        return None

# ---------- ОСНОВНЫЕ МАРШРУТЫ С ПОГОДОЙ ----------
@app.route("/morning")
def morning():
    try:
        img_url = get_random_pinterest_image(RSS_URL)
        weather = get_weather_kamyshin()
        caption = "Доброе утро! 🌅"
        if weather:
            caption += "\n\n" + weather
        send_telegram_photo(img_url, caption)
        return "Утро отправлено", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/afternoon")
def afternoon():
    try:
        img_url = get_random_pinterest_image(RSS_URL)
        weather = get_weather_kamyshin()
        caption = "Добрый день! ☀️"
        if weather:
            caption += "\n\n" + weather
        send_telegram_photo(img_url, caption)
        return "День отправлен", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/evening")
def evening():
    try:
        img_url = get_random_pinterest_image(RSS_URL)
        weather = get_weather_kamyshin()
        caption = "Добрый вечер! 🌙"
        if weather:
            caption += "\n\n" + weather
        send_telegram_photo(img_url, caption)
        return "Вечер отправлен", 200
    except Exception as e:
        return f"<pre>{traceback.format_exc()}</pre>", 500

# ---------- ТЕСТОВЫЕ И СЛУЖЕБНЫЕ МАРШРУТЫ ----------
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

@app.route("/ping")
def ping():
    """Служебный маршрут для пробуждения Render."""
    return "OK", 200

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    print("Запуск Flask...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
