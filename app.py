import sys
import os
import traceback
import random
import json
import requests
from flask import Flask, request
import feedparser

app = Flask(__name__)

# ---------- ДИАГНОСТИКА ----------
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
APP_URL = os.environ.get("APP_URL", "")     # https://yourapp.onrender.com

# ---------- ЗАЩИТА ОТ ПОВТОРОВ (для RSS) ----------
recent_images = []
MAX_RECENT = 10

# ---------- TELEGRAM ОТПРАВКА ----------
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def send_telegram_photo(image_url, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    params = {"chat_id": CHAT_ID, "photo": image_url, "caption": caption}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    recent_images.append(image_url)
    if len(recent_images) > MAX_RECENT:
        recent_images.pop(0)
    return r.json()

def send_telegram_animation(animation_url, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendAnimation"
    params = {"chat_id": CHAT_ID, "animation": animation_url, "caption": caption}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    recent_images.append(animation_url)
    if len(recent_images) > MAX_RECENT:
        recent_images.pop(0)
    return r.json()

def send_telegram_video(video_url, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
    params = {"chat_id": CHAT_ID, "video": video_url, "caption": caption}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    recent_images.append(video_url)
    if len(recent_images) > MAX_RECENT:
        recent_images.pop(0)
    return r.json()

# ---------- RSS ОБРАБОТКА ----------
def clean_image_url(url):
    if 'preview.redd.it' in url:
        url = url.replace('preview.redd.it', 'i.redd.it')
        if '?' in url:
            url = url.split('?')[0]
    return url

def get_random_pinterest_image(rss_url):
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

# ---------- ПОГОДА ----------
def get_weather_kamyshin():
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

# ---------- КОНТЕНТ: МЕМЫ, ФАКТЫ, ШУТКИ ----------
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_meme_media():
    """
    Возвращает словарь {'type': 'photo'/'animation'/'video', 'url': ...} из r/memes.
    При ошибке возвращает None.
    """
    url = "https://www.reddit.com/r/memes/hot.json?limit=50"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Meme fetch error: {e}")
        return None

    items = []
    for post in data["data"]["children"]:
        post_data = post["data"]
        if post_data.get("stickied"):
            continue

        # Картинки и GIF
        img_url = post_data.get("url_overridden_by_dest") or post_data.get("url")
        if img_url:
            lower = img_url.lower()
            if any(domain in lower for domain in ["i.redd.it", "imgur.com", "i.imgur.com"]):
                if lower.endswith('.gif'):
                    items.append({'type': 'animation', 'url': img_url})
                elif any(lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    items.append({'type': 'photo', 'url': img_url})
                # без расширения тоже пробуем как фото
                elif not any(lower.endswith(ext) for ext in ['.gif','.mp4','.webm']):
                    items.append({'type': 'photo', 'url': img_url})

        # Видео (Reddit hosted)
        if post_data.get("is_video") and "media" in post_data:
            video_data = post_data["media"].get("reddit_video")
            if video_data and video_data.get("fallback_url"):
                items.append({'type': 'video', 'url': video_data["fallback_url"]})

    if not items:
        return None
    return random.choice(items)

# Локальные русские факты (запас)
LOCAL_FACTS = [
    "Шанс родиться 29 февраля составляет примерно 1 к 1461.",
    "В Австралии официально больше кенгуру, чем людей.",
    "Мёд — единственная еда, которая никогда не портится.",
    "Одиссей был первым, кто использовал «троянского коня» — буквально.",
    "В Норвегии можно получить срок за незаконное хранение уличной мебели.",
    "Бананы радиоактивны, но в безопасной дозе.",
    "Самая короткая война длилась 38 минут (между Англией и Занзибаром).",
    "Сердце синего кита настолько велико, что человек мог бы проплыть по его артериям."
]

def get_random_fact():
    """
    Пытается взять факт из r/funfacts.
    При неудаче — случайный русский факт из LOCAL_FACTS.
    """
    url = "https://www.reddit.com/r/funfacts/hot.json?limit=50"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
        if posts:
            post = random.choice(posts)["data"]
            title = post.get("title", "").strip()
            selftext = post.get("selftext", "").strip()
            if selftext and len(selftext) > 300:
                selftext = selftext[:300] + "..."
            if selftext and selftext != title:
                return f"📚 {title}\n\n{selftext}"
            else:
                return f"📚 {title}"
    except Exception as e:
        print(f"Fact fetch error: {e}")
    # fallback
    return "📚 " + random.choice(LOCAL_FACTS)

# Локальные русские шутки (запас)
LOCAL_JOKES = [
    "Купил мужик шляпу, а она ему как раз.",
    "— Почему ты не работаешь? — Я жду обновления.",
    "— Сынок, тебя в школе вызывали к доске? — Вызывали. — И что? — Не дозвонились",
    "Объявление: «Требуется уборщица с чувством юмора. Смех в зале приветствуется».",
    "Если жизнь подкинула лимон — сделай лимонад. Если жизнь подкинула asyncio — лучше смени тему.",
    "Оптимист — это человек, который на последние деньги покупает кошелёк.",
    "— Почему программисты не ходят в лес? — Боятся бесконечного цикла «заблудился — нашёл дорогу».",
    "Умный в гору не пойдёт, умный гору обойдёт. А потом вызовет такси.",
    "— Ваш кот любит спать на клавиатуре? — Нет, он предпочитает ходить по кнопке Delete.",
    "— Доктор, у меня стресс. — А вы пробовали ничего не делать? — Пробовал, но совесть не даёт.",
    "Настоящая дружба — это когда ты открываешь холодильник у друга и он тебе не говорит: «Ты чё пришёл?»",
    "Самый страшный вопрос на собеседовании: «Кем вы видите себя через 5 лет?» после вопроса «Расскажите о себе».",
    "Жизнь — как велосипед: чтобы не упасть, надо крутить педали. И лучше, если велосипед электрический.",
    "Извините, я сегодня не в ресурсе. Мой внутренний хомяк обиделся и не хочет бежать в колесе.",
    "— Почему ты такой грустный? — Да вот, вчера удалил Telegram, а сегодня пришлось обратно ставить.",
]

def get_reddit_joke():
    """
    Пытается взять шутку из r/Jokes.
    При ошибке — случайная русская из LOCAL_JOKES.
    """
    url = "https://www.reddit.com/r/Jokes/hot.json?limit=50"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
        if posts:
            post = random.choice(posts)["data"]
            title = post.get("title", "").strip()
            body = post.get("selftext", "").strip()
            if body:
                if len(body) > 500:
                    body = body[:500] + "..."
                return f"😄 {title}\n\n{body}"
            else:
                return f"😄 {title}"
    except Exception as e:
        print(f"Joke fetch error: {e}")
    # fallback
    return "😄 " + random.choice(LOCAL_JOKES)

# ---------- ОСНОВНЫЕ МАРШРУТЫ ----------
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

# ---------- WEBHOOK ----------
def set_webhook():
    if not APP_URL:
        print("⚠️ APP_URL не задан, вебхук не установлен")
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
    if not data or "message" not in data:
        return "OK", 200

    msg = data["message"]
    text = msg.get("text", "").strip().lower()
    chat_id = str(msg["chat"]["id"])

    if chat_id != CHAT_ID:
        return "OK", 200

    if text.startswith("/forecast"):
        reply = get_forecast_message()
        send_telegram_message(reply)
    elif text.startswith("/weather"):
        w = get_weather_kamyshin()
        send_telegram_message(w if w else "Погода недоступна")
    elif text.startswith("/meme"):
        media = get_meme_media()
        if not media:
            send_telegram_message("Мемы временно недоступны 😔")
        else:
            caption = "🔥 Мем дня"
            if media["type"] == "photo":
                send_telegram_photo(media["url"], caption)
            elif media["type"] == "animation":
                send_telegram_animation(media["url"], caption)
            elif media["type"] == "video":
                send_telegram_video(media["url"], caption)
    elif text.startswith("/joke"):
        joke = get_reddit_joke()
        send_telegram_message(joke)
    elif text.startswith("/fact"):
        fact = get_random_fact()
        send_telegram_message(fact)
    elif text.startswith("/start") or text.startswith("/help"):
        help_text = (
            "👋 Я бот-компаньон. Что умею:\n"
            "/forecast – прогноз на сегодня\n"
            "/weather – текущая погода\n"
            "/meme – свежий мем (картинка/гиф/видео)\n"
            "/joke – случайная шутка (Reddit/русский архив)\n"
            "/fact – интересный факт\n"
            "Утро/день/вечер – автоматическая рассылка с погодой."
        )
        send_telegram_message(help_text)
    return "OK", 200

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    print("Запуск Flask...")
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
