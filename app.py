import sys
import os
import traceback
import random
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
print("--- КОНЕЦ ДИАГНОСТИКИ ---")

# ---------- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ----------
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["GROUP_CHAT_ID"]
RSS_URL = os.environ["PINTEREST_RSS"]
APP_URL = os.environ.get("APP_URL", "")

# ---------- ЗАЩИТА ОТ ПОВТОРОВ (RSS) ----------
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

# ---------- RSS ОБРАБОТКА (без изменений) ----------
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

# ========== БОЛЬШИЕ ЛОКАЛЬНЫЕ МАССИВЫ ==========

LOCAL_FACTS = [
    "Шанс родиться 29 февраля — примерно 1 к 1461.",
    "В Австралии кенгуру больше, чем людей.",
    "Мёд — единственная еда, которая не портится. В египетских гробницах находили съедобный мёд.",
    "Одиссей был первым, кто использовал «троянского коня» — буквально.",
    "В Норвегии можно сесть в тюрьму за незаконное хранение уличной мебели.",
    "Бананы радиоактивны (из-за калия-40), но абсолютно безопасны.",
    "Самая короткая война — между Англией и Занзибаром — длилась 38 минут.",
    "Сердце синего кита настолько велико, что человек мог бы проплыть по его артериям.",
    "Кошки мяукают только для общения с людьми, друг с другом они не мяукают.",
    "В Японии снеговиков лепят из двух шаров, а не из трёх.",
    "Клубника — не ягода, а разросшееся цветоложе (многоорешек).",
    "Среднее облако весит около 500 тонн.",
    "Отпечаток языка у каждого человека уникален, как отпечатки пальцев.",
    "Лимон содержит больше сахара, чем клубника.",
    "Улитка может спать до трёх лет.",
    "Слоны — единственные животные, которые не умеют прыгать.",
    "В Швейцарии запрещено держать дома только одну морскую свинку — им нужна компания.",
    "Самый долгий полёт курицы — 13 секунд.",
    "В среднем человек проводит 6 месяцев жизни, ожидая зелёный свет светофора.",
    "Во время Второй мировой войны американские солдаты использовали клейкую ленту (скотч) для починки буквально всего.",
    "В Австралии была война с эму: люди с пулемётами проиграли птицам.",
    "Крокодилы не умеют высовывать язык.",
    "Молния нагревает воздух до 30 000°C — это в пять раз горячее поверхности Солнца.",
    "Самый большой живой организм на Земле — гриб в Орегоне, занимающий 9 кв. км.",
    "В Древнем Риме стоматологи использовали мочу для отбеливания зубов.",
    "Средневековые врачи лечили мигрень, просверливая дырку в черепе.",
    "В Финляндии чемпионат по метанию мобильных телефонов.",
    "Глаз страуса больше, чем его мозг.",
    "В Саудовской Аравии нет рек.",
    "Панды не имеют определённого времени для сна — они спят когда захотят.",
    "В NASA работает человек, чья должность называется «планетарный защитник».",
    "Существует вид медуз (Turritopsis dohrnii), который считается бессмертным.",
    "В Антарктиде есть водопад «Кровавый» красного цвета из-за оксида железа.",
    "В Японии есть кафе, где можно погладить сов.",
    "Самая старая жвачка найдена в Финляндии — ей около 5000 лет.",
    "Миф о том, что человек использует только 10% мозга, не соответствует действительности.",
    "В Бразилии существует остров, где так много змей, что людям туда запрещён вход.",
    "Голубые глаза у всех людей произошли от одного предка 6000–10000 лет назад.",
    "Самая высокая гора в Солнечной системе — Олимп на Марсе (27 км).",
    "В космосе нельзя плакать: слёзы не текут вниз, а собираются в шарики.",
    "Книга рекордов Гиннесса сама является рекордсменом — самой продаваемой книгой, защищённой авторским правом.",
    "Слово «копейка» произошло от изображения всадника с копьём на монетах.",
    "Матрёшка появилась под влиянием японской игрушки-дарумы.",
    "Первый блин всегда комом — изначально означало «богам», а не неудачу.",
    "В русском языке слово «неделя» раньше означало воскресенье (день отдыха).",
    "Московский Кремль — самая большая сохранившаяся крепость в Европе.",
    "Транссибирская магистраль пересекает 8 часовых поясов.",
    "Озеро Байкал содержит около 20% всей пресной воды планеты.",
    "Самовар в старину использовали не только для чая, но и для варки супа.",
    "В России находится самый большой в мире лесной массив — сибирская тайга.",
    "В Антарктиде есть православная церковь.",
    "Россия — единственная страна, омываемая 12 морями.",
    "Санкт-Петербург называют Северной Венецией из-за 342 мостов.",
    "В России более 100 заповедников и 50 национальных парков.",
    "Первый полёт человека в космос совершил Юрий Гагарин 12 апреля 1961 года.",
    "Сибирский тигр — крупнейший представитель семейства кошачьих.",
    "Глубина Кольской сверхглубокой скважины — более 12 км.",
    "Эрмитаж — один из крупнейших художественных музеев мира.",
    "В России изобрели тетрис, радиоприемник и наркоз в полевых условиях.",
]

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
    "Идёт медведь по лесу, видит — машина горит. Сел в неё и сгорел.",
    "Колобок повесился.",
    "— Ты кто? — Дед Пихто.",
    "— Почему у тебя руки в муке? — Тесто месил. — А почему в крови? — А оно сопротивлялось.",
    "Встречаются два программиста. Один спрашивает: «Как жизнь?» Второй: «Да как обычно — виснет, глючит, но работает».",
    "— Девушка, вы замужем? — Нет. — Тогда разрешите представить вам мою жену.",
    "— Ты почему вчера на работу не пришёл? — Так я же в отпуске! — А почему в отпуске на работу пришёл? — Поздороваться.",
    "— Шеф, мне нужно уйти пораньше. — Почему? — У меня гости. — Какие ещё гости? — Печень, почки…",
    "— Почему женщины плохо водят машину? — Потому что дороги строят мужчины, и они не могут объяснить, куда ехать.",
    "Блондинка подходит к автомату с газировкой, кидает монетку, автомат выдаёт банку. Она снова кидает. И так 10 раз. Подходит мужик: «Девушка, что вы делаете?» «Как что? Выигрываю!»",
    "Новости науки: учёные скрестили слона с ротвейлером. Теперь слон не только нападает, но и объясняет, за что.",
    "— Ты знаешь, я теперь вегетарианец. — И как? — Нормально. Вчера картошку с мясом ел. Картошку ел, а мясо выкинул.",
    "Чтобы узнать характер человека, дай ему власть. И интернет.",
    "В аптеке: — У вас есть валерьянка? — Да, в таблетках и в настойке. — Давайте в таблетках, а то я за рулём.",
    "Чукча приходит в магазин: «Чукча хочет купить телевизор». Продавец: «Вам какой?» Чукча: «Чукча хочет цветной!» Продавец: «Вот, пожалуйста». Чукча: «Чукча выбирает зелёный!»",
    "— Я вчера так напился, что даже не помню, как домой попал. — А у меня хуже: я вчера так напился, что помню, как домой попал.",
    "Милиционер останавливает машину: «Ваши права?» Водитель: «Какие права? У нас коммунизм».",
    "Сидят два рыбака, пьют водку. Один: «Что-то не клюёт». Второй: «Так ты червяка на крючок насади». Первый: «Я думал, он сам заползёт».",
    "— Папа, а что такое «парадокс»? — Ну вот смотри: если я тебе скажу, что я тебе вру, я тебе вру или говорю правду?",
    "Приходит студент к профессору: «Профессор, поставьте мне зачёт, а я вам бутылку коньяка». Профессор: «Нет, я взяток не беру». Студент: «А если я поставлю бутылку на стол и выйду?» Профессор: «Ну, если ты выйдешь, я могу и не заметить, что ты вернулся».",
    "— Почему у тебя подушка в крови? — Зуб выпал. — Так надо было к врачу идти! — А он тут при чём?",
    "— Ты веришь в любовь с первого взгляда? — Да. — Тогда почему ты на меня так смотришь? — Потому что я тебя вижу во второй раз.",
    "— Дорогой, ты меня любишь? — Конечно, я же на тебе женился. — Ну и что, я тоже на тебе женилась.",
]


# ---------- ФУНКЦИИ КОМАНД (чистые локальные данные) ----------
def get_random_fact():
    return "📚 " + random.choice(LOCAL_FACTS)

def get_random_joke():
    return "😄 " + random.choice(LOCAL_JOKES)

def get_meme_url():
    """
    Получает случайный мем через meme-api.com.
    Возвращает URL картинки или None при ошибке.
    """
    try:
        resp = requests.get("https://meme-api.com/gimme", timeout=8)
        resp.raise_for_status()
        data = resp.json()
        return data["url"]  # прямая ссылка, например https://i.redd.it/...
    except Exception as e:
        print(f"Meme API error: {e}")
        return None

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
        meme_url = get_meme_url()
        if meme_url:
            send_telegram_photo(meme_url, "🔥 Мем дня")
        else:
            send_telegram_message("Мемы временно недоступны 😔")
    elif text.startswith("/joke"):
        joke = get_random_joke()
        send_telegram_message(joke)
    elif text.startswith("/fact"):
        fact = get_random_fact()
        send_telegram_message(fact)
    elif text.startswith("/start") or text.startswith("/help"):
        help_text = (
            "👋 Я бот-компаньон. Что умею:\n"
            "/forecast – прогноз на сегодня\n"
            "/weather – текущая погода\n"
            "/meme – смешная картинка\n"
            "/joke – русская шутка\n"
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
