# Диагностика перед импортами
import sys, os, traceback
print("--- НАЧАЛО ДИАГНОСТИКИ ---")
print(f"Python version: {sys.version}")
print(f"cwd: {os.getcwd()}")
print(f"files in cwd: {os.listdir('.')}")

# Проверяем переменные окружения (без раскрытия секретов)
for var in ['BOT_TOKEN', 'GROUP_CHAT_ID', 'PINTEREST_RSS']:
    val = os.environ.get(var)
    print(f"{var} задан: {'Да' if val else 'НЕТ'} (длина {len(val) if val else 0})")

# Проверяем импорты библиотек по очереди
for lib in ['flask', 'telegram', 'feedparser', 'requests']:
    try:
        __import__(lib)
        print(f"Библиотека '{lib}' импортирована успешно")
    except Exception as e:
        print(f"!!! ОШИБКА импорта '{lib}': {e}")
        traceback.print_exc()

print("--- КОНЕЦ ДИАГНОСТИКИ ---")
import requests
import random
import feedparser
import os

def get_random_pinterest_image(rss_url):
    """
    Скачиваем RSS с правильными заголовками и парсим.
    В случае неудачи возвращаем fallback-изображение.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })

    try:
        resp = session.get(rss_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise Exception(f"Не удалось загрузить RSS-ленту: {e}")

    feed = feedparser.parse(resp.content)
    images = []

    if not feed.entries:
        raise Exception("RSS-лента пуста или недоступна. Проверьте ссылку и авторизацию.")

    for entry in feed.entries:
        # Способ 1: media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                url = media.get('url')
                if url and url.startswith('http'):
                    images.append(url)
                    break
        # Способ 2: enclosures
        if not images and hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                href = enc.get('href') or enc.get('url')
                if href and href.startswith('http'):
                    images.append(href)
                    break
        # Способ 3: поиск <img src...>
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
            "Не удалось найти изображения в RSS-ленте. Возможно, RSS.app изменил формат."
        )
    return random.choice(images)
