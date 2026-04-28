import sys
import os
import traceback
import random
import json
import requests
from flask import Flask, request
import feedparser

app = Flask(__name__)

# ---------- ДИАГНОСТИКА (видна в логах Render) ----------
print("--- НАЧАЛО ДИАГНОСТИКИ ---")
print(f"Python version: {sys.version}")
print(f"Рабочая директория: {os.getcwd()}")
for var in ['BOT_TOKEN', 'GROUP_CHAT_ID', 'PINTEREST_RSS', 'APP_URL']:
    val = os.environ.get(var)
    print(f"{var} задан: {'Да' if val else 'НЕТ'} (длина {len(val) if val else 0})")
for lib in ['flask', 'feedparser', 'requests']:
    try:
        __import__(lib)
        print(f"Библиотека '{lib}' импортирована успешно")
    except Exception as e:
        print(f"!!! ОШИБКА импорта '{lib}': {e}")
print("--- КОНЕЦ ДИАГНОСТИКИ ---")

# ---------- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ----------
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["GROUP_CHAT_ID"]
RSS_URL = os.environ["PINTEREST_RSS"]       # RSS-лента (сейчас Reddit r/streetwear)
APP_URL = os.environ.get("APP_URL")         # https://yourapp.onrender.com

# ---------- ЗАЩИТА ОТ ПОВТОРОВ ----------
recent_images = []
MAX_RECENT = 10

# ---------- ФУНКЦИИ ДЛЯ ОТПРАВКИ В TELEGRAM ----------
def send_telegram_message(text):
    """Отправка простого текста через Telegram API."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def send_telegram_photo(image_url, caption):
    """Отправка фото и сохранение URL в историю."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    params = {"chat_id": CHAT_ID, "photo": image_url, "caption": caption}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    recent_images.append(image_url)
    if len(recent_images) > MAX_RECENT:
        recent_images.pop(0)
    return r.json()

# ---------- ОБРАБОТКА RSS ----------
def clean_image_url(url):
    if 'preview.redd.it' in url:
        url = url.replace('preview.redd.it', 'i.redd.it')
        if '?' in url:
            url = url.split('?')[0]
    return url

def get_random_pinterest_image(rss_url):
    """Парсит RSS и возвращает URL случайной картинки."""
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
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                url = media.get('url')
                if url and url.startswith('http'):
                    img_url = url
                    break
        if not img_url and hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                href = enc.get('href') or enc.get('url')
                if href and href.startswith('http'):
                    img_url = href
                    break
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

    fresh_images = [img for img in images if img not in recent_images]
    if not fresh_images:
        fresh_images = images
    return random.choice(fresh_images)

# ---------- ПОГОДА (Open-Meteo) ----------
def get_weather_kamyshin():
    """Текущая погода в Камышине."""
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

def get_forecast_message():
    """Прогноз на текущий день."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 50.0531,
        "longitude": 45.3761,
        "daily": ["temperature_2m_max", "temperature_2m_min",
                  "precipitation_sum", "snowfall_sum", "weathercode"],
        "timezone": "Europe/Moscow",
        "forecast_days": 1
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()["daily"]
        max_t = data['temperature_2m_max'][0]
        min_t = data['temperature_2m_min'][0]
        precip = data['precipitation_sum'][0]
        snow = data['snowfall_sum'][0]
        code = data['weathercode'][0]

        weather_map = {
            0: "Ясно", 1: "Малооблачно", 2: "Облачно", 3: "Пасмурно",
            45: "Туман", 48: "Изморозь", 51: "Морось", 53: "Морось",
            55: "Ледяная морось", 61: "Небольшой дождь", 63: "Дождь",
            65: "Сильный дождь", 71: "Небольшой снег", 73: "Снег",
            75: "Сильный снег", 95: "Гроза"
        }
        desc = weather_map.get(code, "Непонятно")

        lines = [f"🌤 Прогноз на сегодня в Камышине:",
                 f"• {desc}",
                 f"• Температура: от {min_t}°C до {max_t}°C"]
        if precip > 0:
            lines.append(f"• Осадки (дождь): {precip} мм")
        if snow > 0:
            lines.append(f"• Снег: {snow} см")
        return "\n".join(lines)
    except Exception as e:
        print(f"Forecast error: {e}")
        return "Не могу получить прогноз 😔"

# ---------- КОНТЕНТ ----------
def get_russian_joke():
    """Случайная шутка с r/russian_jokes."""
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.reddit.com/r/russian_jokes/hot.json?limit=30"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
        if not posts:
            return None
        text_posts = [p for p in posts
                      if p["data"].get("selftext", "").strip()
                      and not p["data"].get("stickied")]
        if not text_posts:
            return None
        post = random.choice(text_posts)["data"]
        title = post["title"].strip()
        body = post["selftext"].split("http")[0].strip()
        return f"😄 {title}\n\n{body}"
    except Exception as e:
        print(f"Joke error: {e}")
        return None

def get_random_fact():
    """Случайный факт (русский, randstuff)."""
    try:
        resp = requests.get("https://randstuff.ru/api/fact/", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        fact_text = data["fact"]["text"]
        return f"📚 Факт дня:\n\n{fact_text}"
    except Exception as e:
        print(f"Fact error: {e}")
        return "Не получилось загрузить факт 😢"

def get_meme_url():
    """Случайный мем с r/memes."""
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.reddit.com/r/memes/hot.json?limit=50"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
        image_urls = []
        for p in posts:
            data = p["data"]
            if data.get("stickied"):
                continue
            img_url = data.get("url_overridden_by_dest") or data.get("url")
            if not img_url:
                continue
            if any(domain in img_url for domain in ["i.redd.it", "imgur.com", "i.imgur.com"]):
                image_urls.append(img_url)
        if not image_urls:
            return None
        return random.choice(image_urls)
    except Exception as e:
        print(f"Meme error: {e}")
        return None

# ---------- МАРШРУТЫ ПО ВРЕМЕНИ (оставлены без изменений) ----------
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
    return "OK", 200

# ---------- WEBHOOK И ОБРАБОТКА КОМАНД ----------
def set_webhook():
    if not APP_URL:
        print("⚠️ APP_URL не задан, вебхук не будет установлен")
        return
    webhook_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    params = {"url": f"{APP_URL}/webhook"}
    try:
        r = requests.get(webhook_url, params=params, timeout=10)
        print(f"Webhook set: {r.json()}")
    except Exception as e:
        print(f"❌ Failed to set webhook: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "OK", 200

    if "message" not in data:
        return "OK", 200

    msg = data["message"]
    text = msg.get("text", "").strip().lower()
    chat_id = str(msg["chat"]["id"])

    # Игнорируем сообщения не из нашей группы
    if chat_id != CHAT_ID:
        return "OK", 200

    # Определяем команду (допустимо с указанием бота)
    if text.startswith("/forecast"):
        reply = get_forecast_message()
        send_telegram_message(reply)
    elif text.startswith("/joke"):
        joke = get_russian_joke()
        if joke:
            send_telegram_message(joke)
        else:
            send_telegram_message("Не удалось добыть шутку 😢")
    elif text.startswith("/fact"):
        fact = get_random_fact()
        send_telegram_message(fact)
    elif text.startswith("/meme"):
        meme_url = get_meme_url()
        if meme_url:
            send_telegram_photo(meme_url, "🔥 Мем дня")
        else:
            send_telegram_message("Мемы закончились 😔")
    elif text.startswith("/weather"):
        w = get_weather_kamyshin()
        send_telegram_message(w if w else "Погода недоступна")
    elif text.startswith("/start") or text.startswith("/help"):
        help_text = (
            "👋 Я бот-компаньон. Что умею:\n"
            "/forecast – прогноз на сегодня (дождь, снег, ветер)\n"
            "/joke – случайная русская шутка с Reddit\n"
            "/fact – интересный факт\n"
            "/meme – свежий мем (картинка)\n"
            "/weather – текущая погода\n"
            "Каждое утро/день/вечер присылаю подборку автоматически."
        )
        send_telegram_message(help_text)
    # Неизвестные команды игнорируем

    return "OK", 200

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    print("Запуск Flask...")
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
