from json.tool import main
import os
import logging
import sqlite3
import asyncio
import base64
import random
import re
from urllib.parse import quote
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
from PIL import Image
import io
import json

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота
from config import BOT_TOKEN
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# База данных SQLite
def init_db():
    conn = sqlite3.connect('realtor_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            price TEXT,
            location TEXT,
            area TEXT,
            rooms TEXT,
            completion_date TEXT,
            broker_phone TEXT,
            broker_email TEXT,
            broker_tg TEXT,
            style_used TEXT,
            html_content TEXT,
            media_files TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица лидов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            tg_user_id INTEGER,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            email TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def fix_database():
    """Добавляет недостающие колонки в существующую базу"""
    try:
        conn = sqlite3.connect('realtor_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='websites'")
        if not cursor.fetchone():
            conn.close()
            return
            
        cursor.execute("PRAGMA table_info(websites)")
        columns = [column[1] for column in cursor.fetchall()]
        
        missing_columns = []
        required_columns = ['price', 'location', 'area', 'rooms', 'completion_date', 
                          'broker_phone', 'broker_email', 'broker_tg', 'style_used', 'media_files']
        
        for column in required_columns:
            if column not in columns:
                missing_columns.append(column)
        
        if missing_columns:
            for column in missing_columns:
                try:
                    cursor.execute(f'ALTER TABLE websites ADD COLUMN {column} TEXT')
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
    finally:
        conn.close()

# Исправляем базу перед созданием
fix_database()
init_db()

# Хранение временных данных
user_sessions = {}

# Клавиатуры
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 Создать сайт")],
            [KeyboardButton(text="📚 Мои сайты")],
            [KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )

def get_yes_no_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )

def get_media_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📷 Фото"), KeyboardButton(text="🎥 Видео")],
            [KeyboardButton(text="✅ Завершить загрузку")]
        ],
        resize_keyboard=True
    )

def get_style_choice_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌆 Пиксельный город"), KeyboardButton(text="🌃 Неон-сити")],
            [KeyboardButton(text="🅽 Neo-премиум"), KeyboardButton(text="🏠 Живой домик")],
            [KeyboardButton(text="🌴 Тропический рай"), KeyboardButton(text="🚀 Космическая станция")],
            [KeyboardButton(text="🎮 Ретро 80-х"), KeyboardButton(text="⚡ Киберпанк")],
            [KeyboardButton(text="🧠 Авто по описанию")]
        ],
        resize_keyboard=True
    )

# ===== ОБРАБОТКА МЕДИА =====

async def download_photo(photo_id):
    """Скачивает и обрабатывает фото"""
    try:
        file = await bot.get_file(photo_id)
        photo_data = await bot.download_file(file.file_path)
        
        image = Image.open(io.BytesIO(photo_data.read()))
        image.thumbnail((1200, 800))
        
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=90)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        return None

async def download_video(video_id):
    """Обработка видео - возвращает file_id для скачивания"""
    try:
        return video_id  # Возвращаем file_id для последующей обработки
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        return None

def get_google_maps_url(location):
    """Генерирует URL для Google Maps на основе локации"""
    if not location:
        return None
    
    # Очищаем location от лишних символов
    clean_location = re.sub(r'[^\w\sа-яА-ЯёЁ,-]', '', location)
    encoded_location = quote(clean_location)
    
    # Без API ключа (простая версия)
    return f"https://www.google.com/maps?q={encoded_location}&output=embed"

def detect_style_from_description(description):
    """Определяет стиль сайта на основе описания"""
    desc_lower = description.lower()
    
    styles = {
        "luxury": {
            "name": "Роскошный", 
            "color": "#d4af37", 
            "secondary": "#2c3e50", 
            "accent": "#8b4513",
            "background": None,
            "animation": None,
            "keywords": ["элит", "премиум", "люкс", "penthouse", "дизайнерский", "эксклюзив", "роскош"]
        },
        "modern": {
            "name": "Современный", 
            "color": "#34495e", 
            "secondary": "#e74c3c", 
            "accent": "#3498db",
            "background": None,
            "animation": None,
            "keywords": ["modern", "современ", "студ", "новострой", "ремонт", "евро", "minimal", "лофт", "хайтек"]
        },
        "classic": {
            "name": "Классический", 
            "color": "#8b4513", 
            "secondary": "#d4af37", 
            "accent": "#2c3e50",
            "background": None,
            "animation": None,
            "keywords": ["классик", "сталин", "кирпич", "дерево", "камин", "антик", "исторический", "царский"]
        },
        "beach": {
            "name": "Пляжный", 
            "color": "#0077be", 
            "secondary": "#f4a460", 
            "accent": "#87ceeb",
            "background": None,
            "animation": None,
            "keywords": ["пляж", "море", "курорт", "отпуск", "отпускной", "вилла", "шале"]
        },
        "urban": {
            "name": "Урбан", 
            "color": "#2c3e50", 
            "secondary": "#7f8c8d", 
            "accent": "#e74c3c",
            "background": None,
            "animation": None,
            "keywords": ["урбан", "город", "метро", "центр", "студ", "апартаменты", "biznes", "офис"]
        },
        "pixel_luxury": {
            "name": "🏰 Пиксельный Люкс", 
            "color": "#ff6b35", 
            "secondary": "#2c3e50", 
            "accent": "#f7c59f",
            "background": "pixel",
            "animation": "heavy",
            "keywords": ["пиксель", "pixel", "люкс", "премиум", "игра", "гейм"]
        },
        "neo_futuristic": {
            "name": "🚀 Нео-Футуристический", 
            "color": "#00ff88", 
            "secondary": "#0a0a2a", 
            "accent": "#ff0080",
            "background": "futuristic", 
            "animation": "extreme",
            "keywords": ["нео", "футуро", "кибер", "техно", "будущее", "космос"]
        }
    }

    # Логика поиска подходящего стиля
    for style_key, style_data in styles.items():
        if any(kw in desc_lower for kw in style_data["keywords"]):
            return style_data
    
    return {
        "name": "Универсальный", 
        "color": "#95a5a6", 
        "secondary": "#7f8c8d", 
        "accent": "#bdc3c7",
        "background": None,
        "animation": None
    }




async def generate_website_html(user_data, media_files):
    """Генерирует профессиональный HTML сайт с видео и картами"""
    
    # Fallback: derive style from description if not already set
    style = user_data.get('style') or detect_style_from_description(user_data.get('description', '') or '')
    photos = [m for m in media_files if m['type'] == 'photo']
    videos = [m for m in media_files if m['type'] == 'video']
    
    # Формируем галерею фото
    gallery_html = ""
    for i, media in enumerate(photos):
        if media.get('data'):
            gallery_html += f'''
            <div class="gallery-item">
                <img src="{media['data']}" alt="Фото объекта {i+1}" loading="lazy">
                <div class="gallery-overlay">
                    <span class="gallery-number">{i+1}</span>
                </div>
            </div>'''

    # Формируем секцию видео
    videos_html = ""
    if videos:
        videos_html += '''
        <section id="videos" class="section">
            <div class="container">
                <h2 class="section-title">Видеообзор</h2>
                <div class="videos-grid">'''
        for i, video in enumerate(videos):
            videos_html += f'''
                <div class="video-item">
                    <div class="video-wrapper">
                        <video controls preload="metadata" playsinline controlslist="nodownload noremoteplayback">
                            <source src="{video['file_id']}" type="video/mp4">
                            Ваш браузер не поддерживает видео.
                        </video>
                    </div>
                    <div class="video-caption">Видео обзор {i+1}</div>
                </div>'''
        videos_html += '''
            </div>
        </section>'''

    # Спец-оформление для новых стилей
    special_bg = ""
    special_classes = ""
    if style.get('key') == 'pixel_city':
        special_classes = "pixel-city"
        special_bg = """
        .pixel-city .header { position: relative; }
        .pixel-city .header::after {
            content: '';
            position: absolute;
            left: 0; right: 0; bottom: -30px; height: 60px;
            background: repeating-linear-gradient(90deg, rgba(0,0,0,0.08) 0 10px, rgba(0,0,0,0.12) 10px 20px);
            filter: blur(3px);
        }
        .pixel-skyline { position: absolute; inset: 0; pointer-events: none; overflow: hidden; z-index: 1; }
        .pixel-building { position: absolute; bottom: -16px; width: 100px; height: 120px; background: #1f2937; box-shadow: 0 0 0 4px #000 inset; image-rendering: pixelated; border-radius: 4px; opacity: .9; }
        .pixel-building .pixel-window { position: absolute; width: 8px; height: 8px; background: #ffd166; box-shadow: 0 0 0 2px #000 inset; }
        .pixel-bird { position: absolute; width: 14px; height: 10px; background: #fff; box-shadow: 0 0 0 2px #000 inset; transform: rotate(-8deg); animation: birdFly 10s linear infinite; opacity: .8; }
        @keyframes birdFly { 0%{ transform: translateX(-10vw) translateY(0) rotate(-8deg);} 50%{ transform: translateX(50vw) translateY(-10px) rotate(4deg);} 100%{ transform: translateX(110vw) translateY(0) rotate(-8deg);} }
        @keyframes floatHouse { 0%{ transform: translateY(0);} 50%{ transform: translateY(-10px);} 100%{ transform: translateY(0);} }
        .flying-house { position: absolute; top: 20%; left: 10%; width: 120px; height: 80px; background: #ff6b35; box-shadow: 0 0 0 4px #000 inset; border-radius: 6px; animation: floatHouse 4s ease-in-out infinite; }
        .flying-house::before { content: ''; position: absolute; bottom: -20px; left: 40px; width: 40px; height: 20px; background: #00000033; filter: blur(6px); border-radius: 50%; }
        .pixel-cloud { position: absolute; top: 10%; width: 120px; height: 40px; background: #ffffffcc; box-shadow: 0 0 0 4px #000 inset; border-radius: 6px; animation: floatHouse 6s ease-in-out infinite; }
        .pixel-stars { position:absolute; inset:0; pointer-events:none; z-index:0; }
        .pixel-star { position:absolute; width:4px; height:4px; background:#fff; box-shadow:0 0 0 2px #000 inset; opacity:.9; animation: twinkle 2.2s ease-in-out infinite; }
        @keyframes twinkle { 0%,100%{ transform: scale(0.9); opacity:.5;} 50%{ transform: scale(1.2); opacity:1; } }
        .btn { position: relative; overflow: hidden; }
        .btn::after { content:''; position:absolute; inset:auto -20% -20% -20%; height:200%; width: 40%; transform: rotate(25deg) translateX(-120%); background:linear-gradient(90deg, transparent, rgba(255,255,255,.28), transparent); transition: transform .6s ease; }
        .btn:hover::after { transform: rotate(25deg) translateX(260%); }
        """
    elif style.get('key') == 'neon_city':
        special_classes = "neon-city"
        special_bg = """
        .neon-city body { background: radial-gradient(1200px 600px at 10% 10%, #1a0033, #020010 60%); }
        .neon-glow { position: fixed; inset: -20%; background: radial-gradient(circle at 20% 30%, #ff00cc22, transparent 30%), radial-gradient(circle at 80% 40%, #00e6ff22, transparent 30%), radial-gradient(circle at 50% 80%, #6600ff22, transparent 30%); pointer-events: none; z-index: 0; }
        .header .property-title { text-shadow: 0 0 10px var(--accent), 0 0 20px var(--accent); }
        .neon-scan { position: absolute; inset: 0; background: linear-gradient(transparent, rgba(255,255,255,0.06), transparent); animation: scan 4s linear infinite; pointer-events: none; }
        @keyframes scan { 0%{ transform: translateY(-100%);} 100%{ transform: translateY(100%);} }
        .neon-grid { position: absolute; left: 0; right: 0; bottom: 0; height: 220px; background: linear-gradient(transparent, rgba(0,230,255,0.05)); backdrop-filter: blur(2px); }
        .neon-grid::before { content: ''; position: absolute; inset: 0; background-image: linear-gradient(rgba(0,230,255,0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(0,230,255,0.2) 1px, transparent 1px); background-size: 20px 20px; }
        .neon-particle { position: absolute; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 10px var(--accent), 0 0 20px var(--accent); animation: fly 8s linear infinite; }
        @keyframes fly { 0%{ transform: translate(-10vw, 0);} 100%{ transform: translate(110vw, -20vh);} }
        .btn { position: relative; border: 2px solid var(--accent); box-shadow: 0 0 12px var(--accent), inset 0 0 12px rgba(255,255,255,0.06); text-shadow: 0 0 8px var(--accent); }
        .btn:hover { box-shadow: 0 0 18px var(--accent), inset 0 0 18px rgba(255,255,255,0.08); filter: saturate(1.2); }
        .gallery-item { border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 0 12px rgba(0,230,255,0.12); }
        .gallery-item:hover { box-shadow: 0 0 22px rgba(255,0,204,0.18); }
        .section-title { text-shadow: 0 0 10px rgba(0,230,255,0.4); }
        """
    elif style.get('key') == 'neo_premium':
        special_classes = "neo"
        special_bg = """
        body.neo { background:#0f0f0f; color:#ffffff; }
        .header { position:relative; overflow:hidden }
        .neon-gradient { position:absolute; inset:-30%; background:radial-gradient(800px 400px at 10% 10%, rgba(138,43,226,.25), transparent 40%), radial-gradient(900px 600px at 90% 20%, rgba(0,229,255,.20), transparent 50%); filter: blur(20px); }
        .property-title { font-family:'Space Grotesk', Inter, sans-serif; font-weight:800; letter-spacing:-.02em; text-shadow: 0 0 10px rgba(255,0,102,.4); }
        .btn { border:none; border-radius:14px; background: linear-gradient(135deg, #ff7a18, #ff0066); box-shadow: 0 10px 30px rgba(255,0,102,.2) }
        .gallery-item, .video-item, .map-container { background: rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.08) }
        .section-title { font-family:'Space Grotesk', Inter, sans-serif; text-shadow: 0 0 10px rgba(0,229,255,.3) }
        """
    elif style.get('key') == 'living_house':
        special_classes = "living-house"
        special_bg = """
        .living-house .header { position: relative; overflow: hidden; }
        .living-house .flying-house { position: fixed; top: 20%; left: 10%; width: 120px; height: 90px; background: #ff9f1c; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.3); z-index: 9999; animation: flyPath 12s ease-in-out infinite; }
        .living-house .flying-house::before { content:''; position:absolute; bottom:-18px; left: 40px; width: 50px; height: 20px; background: rgba(0,0,0,.15); filter: blur(6px); border-radius: 50%; }
        .living-house .house-eye { position:absolute; width: 10px; height: 10px; background:#fff; border-radius:50%; top: 28px; left: 28px; box-shadow: 0 0 0 2px #000 inset; }
        .living-house .house-eye.right { left: 52px; }
        .living-house .house-smile { position:absolute; width: 36px; height: 12px; border-bottom: 4px solid #000; border-radius: 0 0 36px 36px; top: 50px; left: 28px; }
        @keyframes flyPath { 0%{ transform: translate(0,0) rotate(-2deg);} 25%{ transform: translate(40vw,-6vh) rotate(2deg);} 50%{ transform: translate(68vw,2vh) rotate(-1deg);} 75%{ transform: translate(30vw,8vh) rotate(3deg);} 100%{ transform: translate(0,0) rotate(-2deg);} }
        .living-house .spark { position: fixed; width: 6px; height: 6px; background: #e71d36; border-radius: 50%; box-shadow: 0 0 10px #e71d36; animation: spark 1.6s linear infinite; }
        @keyframes spark { 0%{ transform: translateY(0); opacity:1 } 100%{ transform: translateY(-40px); opacity:0 } }
        .living-house .gallery-item:hover { transform: translateY(-6px) rotate(-.4deg) scale(1.02); box-shadow: var(--shadow-hover); }
        .living-house .btn { position:relative; overflow:hidden }
        .living-house .btn::after { content:''; position:absolute; inset:auto -20% -20% -20%; height:200%; width:40%; transform: rotate(25deg) translateX(-120%); background:linear-gradient(90deg, transparent, rgba(255,255,255,.28), transparent); transition: transform .6s ease; }
        .living-house .btn:hover::after { transform: rotate(25deg) translateX(260%); }
        """
    elif style.get('key') == 'tropical_paradise':
        special_classes = "tropical"
        special_bg = """
        body.tropical { background: linear-gradient(135deg, #ff7e5f, #feb47b); }
        .header { background: url('tropical.jpg') no-repeat center center; background-size: cover; }
        """
    elif style.get('key') == 'space_station':
        special_classes = "space"
        special_bg = """
        body.space { background: radial-gradient(circle at center, #000428, #004e92); }
        .header { background: url('space.jpg') no-repeat center center; background-size: cover; }
        """
    elif style.get('key') == 'retro_80s':
        special_classes = "retro"
        special_bg = """
        body.retro { background: linear-gradient(135deg, #ff6a00, #ee0979); }
        .header { background: url('retro.jpg') no-repeat center center; background-size: cover; }
        """
    elif style.get('key') == 'cyberpunk':
        special_classes = "cyber"
        special_bg = """
        body.cyber { background: linear-gradient(135deg, #0f0c29, #302b63); }
        .header { background: url('cyberpunk.jpg') no-repeat center center; background-size: cover; }
        """

    # Google Maps
    maps_html = ""
    maps_url = get_google_maps_url(user_data.get('location'))
    if maps_url:
        maps_html = f'''
        <section id="map" class="section">
            <div class="container">
                <h2 class="section-title">Расположение на карте</h2>
                <div class="map-container">
                    <iframe 
                        src="{maps_url}"
                        width="100%" 
                        height="450" 
                        style="border:0; border-radius: var(--radius);" 
                        allowfullscreen="" 
                        loading="lazy" 
                        referrerpolicy="no-referrer-when-downgrade">
                    </iframe>
                    <div class="map-address">
                        <h3>📍 Адрес объекта</h3>
                        <p>{user_data.get('location', 'Адрес уточняется')}</p>
                    </div>
                </div>
            </div>
        </section>'''
    else:
        maps_html = f'''
        <section id="location" class="section">
            <div class="container">
                <h2 class="section-title">Расположение</h2>
                <div class="about-content">
                    <h3>{user_data.get('location', 'Престижный район')}</h3>
                    <p>Объект расположен в одном из самых престижных и развитых районов города. Отличная транспортная доступность, развитая инфраструктура, близость к парковым зонам и основным магистралям.</p>
                </div>
            </div>
        </section>'''

    # Контактная информация
    contacts_html = ""
    if user_data.get('broker_phone'):
        contacts_html += f'''
        <div class="contact-item">
            <div class="contact-icon">📞</div>
            <div class="contact-info">
                <h4>Телефон</h4>
                <p>{user_data['broker_phone']}</p>
            </div>
        </div>'''
    
    if user_data.get('broker_email'):
        contacts_html += f'''
        <div class="contact-item">
            <div class="contact-icon">📧</div>
            <div class="contact-info">
                <h4>Email</h4>
                <p>{user_data['broker_email']}</p>
            </div>
        </div>'''
    
    if user_data.get('broker_tg'):
        contacts_html += f'''
        <div class="contact-item">
            <div class="contact-icon">✈️</div>
            <div class="contact-info">
                <h4>Telegram</h4>
                <p>@{user_data['broker_tg']}</p>
            </div>
        </div>'''
    
    # Характеристики
    specs_html = ""
    specs = [
        ("💰 Цена", user_data.get('price')),
        ("📍 Локация", user_data.get('location')),
        ("📐 Площадь", user_data.get('area')),
        ("🚪 Комнаты", user_data.get('rooms')),
        ("📅 Срок сдачи", user_data.get('completion_date')),
    ]
    
    for icon, value in specs:
        if value and value not in ['Не указана', 'Не указано', 'Не указан']:
            specs_html += f'''
            <div class="spec-item">
                <div class="spec-icon">{icon.split()[0]}</div>
                <div class="spec-content">
                    <h4>{icon}</h4>
                    <p>{value}</p>
                </div>
            </div>'''

    # CTA кнопки
    cta_buttons_html = ""
    if user_data.get('broker_phone') or user_data.get('broker_tg'):
        cta_buttons_html += '<div class="cta-buttons">'
        if user_data.get('broker_phone'):
            cta_buttons_html += f'<a href="tel:{user_data["broker_phone"]}" class="btn"><i class="fas fa-phone"></i> Позвонить сейчас</a>'
        if user_data.get('broker_tg'):
            cta_buttons_html += f'<a href="https://t.me/{user_data["broker_tg"]}" class="btn btn-outline"><i class="fab fa-telegram"></i> Написать в Telegram</a>'
        # Кнопка лида в Telegram с плейсхолдером (подменим позже на реальную ссылку)
        cta_buttons_html += '<a href="LEAD_PLACEHOLDER" class="btn btn-outline"><i class="fab fa-telegram"></i> Оставить заявку в Telegram</a>'
        cta_buttons_html += '</div>'
    else:
        # Если контактов нет — всё равно добавим кнопку лида
        cta_buttons_html += '<div class="cta-buttons">'
        cta_buttons_html += '<a href="LEAD_PLACEHOLDER" class="btn"><i class="fab fa-telegram"></i> Оставить заявку в Telegram</a>'
        cta_buttons_html += '</div>'

    html_content = f'''<!DOCTYPE html>
<html lang="ru" class="{special_classes}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{user_data['title']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {{
            --primary: {style['color']};
            --secondary: {style['secondary']};
            --accent: {style['accent']};
            --dark: #2c3e50;
            --light: #ecf0f1;
            --text: #2c3e50;
            --text-light: #7f8c8d;
            --shadow: 0 25px 50px rgba(0,0,0,0.15);
            --shadow-hover: 0 35px 70px rgba(0,0,0,0.25);
            --radius: 20px;
            --transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }}
        {special_bg}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; line-height: 1.7; color: var (--text); background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); min-height: 100vh; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 0 20px; }}
        
        .header {{ background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); color: white; padding: 80px 0; text-align: center; position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="50" cy="50" r="1" fill="rgba(255,255,255,0.1)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>'); opacity: 0.1; }}
        .header-content {{ position: relative; z-index: 2; }}
        .property-badge {{ background: rgba(255,255,255,0.2); backdrop-filter: blur(10px); padding: 12px 25px; border-radius: 50px; display: inline-block; margin-bottom: 30px; font-weight: 600; font-size: 0.9rem; letter-spacing: 1px; text-transform: uppercase; }}
        .property-title {{ font-size: 4rem; font-weight: 800; margin-bottom: 20px; line-height: 1.2; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }}
        .property-description {{ font-size: 1.4rem; margin-bottom: 40px; opacity: 0.95; max-width: 800px; margin-left: auto; margin-right: auto; line-height: 1.6; }}
        .property-price {{ font-size: 2.5rem; font-weight: 700; margin-bottom: 40px; color: var(--accent); text-shadow: 1px 1px 2px rgba(0,0,0,0.2); }}
        
        .nav-scroll {{ background: white; padding: 25px 0; position: sticky; top: 0; z-index: 1000; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }}
        .nav-container {{ display: flex; justify-content: center; gap: 40px; }}
        .nav-item {{ color: var(--text); text-decoration: none; font-weight: 600; font-size: 1.1rem; padding: 10px 20px; border-radius: 25px; transition: var(--transition); position: relative; }}
        .nav-item:hover {{ color: var(--primary); transform: translateY(-2px); }}
        .nav-item::after {{ content: ''; position: absolute; bottom: 0; left: 50%; width: 0; height: 3px; background: var(--primary); transition: var(--transition); transform: translateX(-50%); border-radius: 3px; }}
        .nav-item:hover::after {{ width: 60%; }}
        
        .section {{ padding: 100px 0; }}
        .section-title {{ font-size: 3rem; font-weight: 700; text-align: center; margin-bottom: 60px; color: var(--dark); position: relative; }}
        .section-title::after {{ content: ''; position: absolute; bottom: -15px; left: 50%; transform: translateX(-50%); width: 80px; height: 4px; background: linear-gradient(90deg, var(--primary), var(--accent)); border-radius: 2px; }}
        
                .about-content {{ 
            background: white; 
            padding: 60px; 
            border-radius: var(--radius); 
            box-shadow: var(--shadow); 
            margin-bottom: 60px; 
            line-height: 1.8; 
            font-size: 1.2rem; 
        }}
        
        .specs-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); 
            gap: 30px; 
            margin-bottom: 60px; 
        }}
        
        .spec-item {{ 
            background: white; 
            padding: 40px; 
            border-radius: var(--radius); 
            box-shadow: var(--shadow); 
            display: flex; 
            align-items: center; 
            gap: 25px; 
            transition: var(--transition); 
        }}
        
        .spec-item:hover {{ 
            transform: translateY(-8px); 
            box-shadow: var(--shadow-hover); 
        }}
        
        .spec-icon {{ 
            font-size: 2.5rem; 
            color: var (--primary); 
            flex-shrink: 0; 
        }}
        
        .spec-content h4 {{ 
            font-size: 1.3rem; 
            font-weight: 600; 
            margin-bottom: 8px; 
            color: var (--dark); 
        }}
        
        .spec-content p {{ 
            color: var(--text-light); 
            font-size: 1.1rem; 
        }}
        
        .gallery {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); 
            gap: 25px; 
            margin-bottom: 60px; 
        }}
        
        .gallery-item {{ 
            position: relative; 
            border-radius: var (--radius); 
            overflow: hidden; 
            box-shadow: var(--shadow); 
            transition: var (--transition); 
            height: 350px; 
        }}
        
        .gallery-item:hover {{ 
            transform: scale(1.03); 
            box-shadow: var(--shadow-hover); 
        }}
        
        .gallery-item img {{ 
            width: 100%; 
            height: 100%; 
            object-fit: cover; 
            transition: var(--transition); 
        }}
        
        .gallery-item:hover img {{ 
            transform: scale(1.1); 
        }}
        
        .gallery-overlay {{ 
            position: absolute; 
            top: 20px; 
            right: 20px; 
            background: rgba(0,0,0,0.8); 
            color: white; 
            padding: 10px 15px; 
            border-radius: 20px; 
            font-weight: 600; 
        }}
        
        .videos-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); 
            gap: 30px; 
            margin-bottom: 60px; 
        }}
        
        .video-item {{ 
            background: white; 
            padding: 20px; 
            border-radius: var(--radius); 
            box-shadow: var (--shadow); 
        }}
        
        .video-wrapper {{ 
            position: relative; 
            padding-bottom: 56.25%; 
            height: 0; 
            overflow: hidden; 
            border-radius: 15px; 
        }}
        
        .video-wrapper video {{ 
            position: absolute; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            object-fit: cover; 
        }}
        
        .video-caption {{ 
            text-align: center; 
            margin-top: 15px; 
            color: var(--text-light); 
            font-weight: 600; 
        }}
        
        .map-container {{ 
            background: white; 
            padding: 30px; 
            border-radius: var(--radius); 
            box-shadow: var (--shadow); 
        }}
        
        .map-container iframe {{ 
            border-radius: 15px; 
        }}
        
        .map-address {{ 
            margin-top: 20px; 
            text-align: center; 
        }}
        
        .map-address h3 {{ 
            color: var(--primary); 
            margin-bottom: 10px; 
        }}
        
        .contact-section {{ 
            background: linear-gradient(135deg, var(--dark) 0%, #34495e 100%); 
            color: white; 
            padding: 100px 0; 
        }}
        
        .contact-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 40px; 
            margin-bottom: 60px; 
        }}
        
        .contact-item {{ 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            padding: 40px; 
            border-radius: var(--radius); 
            text-align: center; 
            transition: var(--transition); 
        }}
        
        .contact-item:hover {{ 
            background: rgba(255,255,255,0.15); 
            transform: translateY(-5px); 
        }}
        
        .contact-icon {{ 
            font-size: 3rem; 
            margin-bottom: 20px; 
            color: var(--accent); 
        }}
        
        .contact-info h4 {{ 
            font-size: 1.4rem; 
            margin-bottom: 15px; 
            color: white; 
        }}
        
        .contact-info p {{ 
            font-size: 1.2rem; 
            opacity: 0.9; 
        }}
        
        .cta-buttons {{ 
            display: flex; 
            justify-content: center; 
            gap: 20px; 
            flex-wrap: wrap; 
        }}
        
        .btn {{ 
            background: linear-gradient(135deg, var(--primary), var(--accent)); 
            color: white; 
            padding: 20px 40px; 
            border: none; 
            border-radius: 50px; 
            font-size: 1.2rem; 
            font-weight: 600; 
            text-decoration: none; 
            display: inline-flex; 
            align-items: center; 
            gap: 12px; 
            transition: var(--transition); 
            cursor: pointer; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
        }}
        
        .btn:hover {{ 
            transform: translateY(-3px); 
            box-shadow: 0 15px 40px rgba(0,0,0,0.3); 
            color: white; 
        }}
        
        .btn-outline {{ 
            background: transparent; 
            border: 2px solid var(--accent); 
            color: var(--accent); 
        }}
        
        .btn-outline:hover {{ 
            background: var(--accent); 
            color: white; 
        }}
        
        .footer {{ 
            background: var(--dark); 
            color: white; 
            padding: 60px 0 30px; 
            text-align: center; 
        }}
        
        .watermark {{ 
            opacity: 0.7; 
            font-size: 0.9rem; 
            margin-top: 40px; 
            color: var(--light); 
        }}
        
        @keyframes fadeInUp {{ 
            from {{ 
                opacity: 0; 
                transform: translateY(50px); 
            }}
            to {{ 
                opacity: 1; 
                transform: translateY(0); 
            }}
        }}
        
        .animate {{ 
            animation: fadeInUp 1s ease-out; 
        }}
        
        /* Responsive Design */
        @media (max-width: 1200px) {{
            .property-title {{ font-size: 3rem; }}
            .section-title {{ font-size: 2.5rem; }}
        }}
        
        @media (max-width: 992px) {{
            .header {{ padding: 60px 0; }}
            .property-title {{ font-size: 2.5rem; }}
            .property-description {{ font-size: 1.2rem; }}
            .section {{ padding: 80px 0; }}
        }}
        
        @media (max-width: 768px) {{
            .property-title {{ font-size: 2.2rem; }}
            .property-description {{ font-size: 1.1rem; }}
            .property-price {{ font-size: 1.8rem; }}
            .section-title {{ font-size: 2rem; }}
            .section {{ padding: 60px 0; }}
            .gallery, .videos-grid {{ grid-template-columns: 1fr; }}
            .specs-grid {{ grid-template-columns: 1fr; }}
            .contact-grid {{ grid-template-columns: 1fr; }}
            .cta-buttons {{ flex-direction: column; }}
            .nav-container {{ flex-wrap: wrap; gap: 20px; }}
            .about-content {{ padding: 30px; }}
            .spec-item, .contact-item {{ padding: 30px; }}
        }}
        
        @media (max-width: 576px) {{
            .property-title {{ font-size: 1.8rem; }}
            .header {{ padding: 40px 0; }}
            .section {{ padding: 40px 0; }}
            .gallery-item {{ height: 300px; }}
            .btn {{ padding: 15px 30px; font-size: 1rem; }}
        }}
        
        /* Additional styles for empty states */
        .no-specs, .no-photos, .no-videos {{ 
            text-align: center; 
            color: var (--text-light); 
            font-size: 1.2rem; 
            padding: 40px; 
            grid-column: 1 / -1; 
        }}
        
        /* Loading states */
        .loading {{ 
            display: inline-block; 
            width: 20px; 
            height: 20px; 
            border: 3px solid rgba(255,255,255,.3); 
            border-radius: 50%; 
            border-top-color: #fff; 
            animation: spin 1s ease-in-out infinite; 
        }}
        
        @keyframes spin {{ 
            to {{ transform: rotate(360deg); }} 
        }}
        
        /* Accessibility */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }}
        }}
        
        /* Focus styles for accessibility */
        a:focus, button:focus, input:focus, textarea:focus {{
            outline: 2px solid var(--accent);
            outline-offset: 2px;
        }}
        
        /* High contrast mode support */
        @media (prefers-contrast: high) {{
            :root {{
                --text: #000000;
                --text-light: #333333;
                --light: #ffffff;
            }}
            
            .header {{
                background: var(--primary);
            }}
            
            .spec-item, .about-content {{
                border: 2px solid var (--primary);
            }}
        }}
        
        /* Dark mode support */
        @media (prefers-color-scheme: dark) {{
            body {{
                background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                color: #ffffff;
            }}
            
            .about-content, .spec-item, .gallery-item, .video-item, .map-container {{
                background: #2d2d2d;
                color: #ffffff;
            }}
            
            .spec-content h4, .spec-content p {{
                color: #ffffff;
            }}
            
            .nav-scroll {{
                background: #1a1a1a;
            }}
            
            .nav-item {{
                color: #ffffff;
            }}
        }}
    </style>
</head>
<body>
    {"<div class='neon-gradient'></div>" if style.get('key') == 'neo_premium' else ''}
    <header class="header">
        <div class="container">
            <div class="header-content animate">
                <div class="property-badge">Элитная недвижимость</div>
                <h1 class="property-title">{user_data['title']}</h1>
                <p class="property-description">{user_data['description']}</p>
                <div class="property-price">{user_data.get('price', 'Цена по запросу')}</div>
                {cta_buttons_html}
            </div>
            {"<div class='neon-scan'></div><div class='neon-grid'></div>" if style.get('key') == 'neon_city' else ''}
        </div>
    </header>

    <nav class="nav-scroll">
        <div class="container">
            <div class="nav-container">
                <a href="#about" class="nav-item">О проекте</a>
                <a href="#specs" class="nav-item">Характеристики</a>
                <a href="#gallery" class="nav-item">Галерея</a>
                {"<a href=\"#videos\" class=\"nav-item\">Видео</a>" if videos_html else ''}
                <a href="#map" class="nav-item">Карта</a>
                {"<a href=\"#contact\" class=\"nav-item\">Контакты</a>" if contacts_html else ''}
            </div>
        </div>
    </nav>

    <section id="about" class="section">
        <div class="container">
            <h2 class="section-title">О проекте</h2>
            <div class="about-content animate">
                <p>{user_data['description']}</p>
            </div>
        </div>
    </section>

    <section id="specs" class="section" style="background: #f8f9fa;">
        <div class="container">
            <h2 class="section-title">Характеристики</h2>
            <div class="specs-grid">
                {specs_html if specs_html else '<p class="no-specs">Характеристики не указаны</p>'}
            </div>
        </div>
    </section>

    <section id="gallery" class="section">
        <div class="container">
            <h2 class="section-title">Фотогалерея</h2>
            <div class="gallery">
                {gallery_html if gallery_html else '<p class="no-photos">Фотографии не добавлены</p>'}
            </div>
        </div>
    </section>

    {videos_html if videos_html else ''}

    {maps_html if maps_html else f'''
    <section id="location" class="section">
        <div class="container">
            <h2 class="section-title">Расположение</h2>
            <div class="about-content">
                <h3>{user_data.get('location', 'Престижный район')}</h3>
                <p>Объект расположен в одном из самых престижных и развитых районов города. Отличная транспортная доступность, развитая инфраструктура, близость к парковым зонам и основным магистралям.</p>
            </div>
        </div>
    </section>'''}

    {f'''
    <section id="contact" class="contact-section">
        <div class="container">
            <h2 class="section-title" style="color: white;">Контакты</h2>
            <div class="contact-grid">{contacts_html}</div>
            {cta_buttons_html}
        </div>
    </section>
    ''' if contacts_html else ''}

    <footer class="footer">
        <div class="container">
            <p>© 2024 {user_data['title']}. Все права защищены.</p>
            <div class="watermark">Сайт создан через @ANton618_bot</div>
        </div>
    </footer>

    <script>
        // Плавная прокрутка
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {{
                    target.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'start'
                    }});
                }}
            }});
        }});

        // Анимации при скролле
        const observerOptions = {{
            threshold: 0.1,
            rootMargin: '0px 0px -100px 0px'
        }};

        const observer = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    entry.target.classList.add('animate');
                }}
            }});
        }}, observerOptions);

        document.querySelectorAll('.spec-item, .gallery-item, .video-item, .contact-item, .about-content').forEach(el => {{
            observer.observe(el);
        }});

        // Фиксированная навигация
        window.addEventListener('scroll', () => {{
            const nav = document.querySelector('.nav-scroll');
            if (window.scrollY > 200) {{
                nav.style.position = 'fixed';
                nav.style.width = '100%';
                nav.style.top = '0';
            }} else {{
                nav.style.position = 'static';
            }}
        }});

        // Lazy loading для изображений
        if ('loading' in HTMLImageElement.prototype) {{
            const images = document.querySelectorAll('img[loading="lazy"]');
            images.forEach(img => {{
                img.src = img.dataset.src;
            }});
        }}

        // Обработка видео
        const videos = document.querySelectorAll('video');
        videos.forEach(video => {{
            video.addEventListener('click', function() {{
                if (this.paused) {{
                    this.play();
                }} else {{
                    this.pause();
                }}
            }});
        }});

        // Параллакс эффект для header
        window.addEventListener('scroll', () => {{
            const scrolled = window.pageYOffset;
            const parallax = document.querySelector('.header');
            if (parallax) {{
                parallax.style.backgroundPositionY = -(scrolled * 0.5) + 'px';
            }}
        }});

        // Обработка ошибок загрузки медиа
        document.addEventListener('error', function(e) {{
            if (e.target.tagName === 'IMG') {{
                e.target.style.display = 'none';
            }} else if (e.target.tagName === 'VIDEO') {{
                e.target.parentElement.innerHTML = '<p>Не удалось загрузить видео</p>';
            }}
        }}, true);

        // Аналитика просмотров
        window.addEventListener('load', function() {{
            const timeSpent = Date.now();
            window.addEventListener('beforeunload', function() {{
                const totalTime = Date.now() - timeSpent;
                console.log('Время на сайте:', Math.round(totalTime/1000), 'секунд');
            }});
        }});

        // Оптимизация производительности
        let resizeTimer;
        window.addEventListener('resize', function() {{
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {{
                document.body.classList.add('resize-animation-stopper');
                setTimeout(function() {{
                    document.body.classList.remove('resize-animation-stopper');
                }}, 400);
            }}, 400);
        }});
    </script>
</body>
</html>'''
    return html_content

# ===== ОСНОВНЫЕ ОБРАБОТЧИКИ =====

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('realtor_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
        (user_id, message.from_user.username, message.from_user.first_name)
    )
    conn.commit()
    conn.close()
    
    # Обработка deep-link: /start lead_<site_id>
    payload = None
    if message.text and ' ' in message.text:
        try:
            payload = message.text.split(' ', 1)[1].strip()
        except Exception:
            payload = None
    if payload and payload.startswith('lead_'):
        try:
            site_id = int(payload.split('_')[1])
            user_sessions[user_id] = { 'state': 'lead_collect', 'lead_site_id': site_id }
            await message.answer(
                "📩 <b>Заявка по объекту принята!</b>\n\n"
                "Оставьте, пожалуйста, контакт: \n"
                "Телефон: +7 ... или Email: name@mail.com"
            )
            return
        except Exception:
            pass
    
    welcome_text = f"""
<b>🏆 ПРОФЕССИОНАЛЬНЫЙ ГЕНЕРАТОР САЙТОВ</b>

💎 <i>Создаю сайты премиум-класса для элитной недвижимости</i>

✨ <b>НОВЫЕ ВОЗМОЖНОСТИ:</b>
• 📷 Фотографии в HD качестве
• 🎥 Видеообзоры объектов  
• 🗺️ Интерактивные Google карты
• 💰 Умное определение стиля
• 📱 Адаптивный дизайн
• ⚡ Быстрая генерация

<code>Начните с кнопки «Создать сайт» 👇</code>
"""
    
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(F.text == "🌐 Создать сайт")
async def start_creation(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id] = {
        'state': 'waiting_media_type',
        'media': [],
        'title': '',
        'description': '',
        'price': '',
        'location': '',
        'area': '',
        'rooms': '',
        'completion_date': '',
        'broker_phone': '',
        'broker_email': '',
        'broker_tg': '',
        'style': {}
    }
    await message.answer(
        "📸 <b>ШАГ 1: Медиафайлы объекта</b>\n\n"
        "Выберите тип медиа для загрузки:\n"
        "• 📷 Фото - для галереи изображений\n"
        "• 🎥 Видео - для видеообзоров\n\n"
        "<i>Можно загружать оба типа файлов!</i>",
        reply_markup=get_media_type_keyboard()
    )

@dp.message(F.text == "📷 Фото")
async def handle_photo_choice(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    user_sessions[user_id]['state'] = 'waiting_photo'
    await message.answer(
        "📸 Отправьте фотографию объекта\n\n"
        "<i>Фото будет использовано в галерее сайта</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Назад к выбору")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🎥 Видео")
async def handle_video_choice(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    user_sessions[user_id]['state'] = 'waiting_video'
    await message.answer(
        "🎥 Отправьте видео объекта\n\n"
        "<i>Видео будет добавлено в раздел видеообзоров</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Назад к выбору")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "◀️ Назад к выбору")
async def handle_back_to_choice(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    user_sessions[user_id]['state'] = 'waiting_media_type'
    await message.answer(
        "📸 Выберите тип медиа для загрузки:",
        reply_markup=get_media_type_keyboard()
    )

@dp.message(F.photo, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_photo')
async def handle_photo_upload(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    photo_data = await download_photo(message.photo[-1].file_id)
    if photo_data:
        user_sessions[user_id]['media'].append({
            'type': 'photo',
            'file_id': message.photo[-1].file_id,
            'data': photo_data
        })
        
        count = len([m for m in user_sessions[user_id]['media'] if m['type'] == 'photo'])
        await message.answer(
            f"✅ Фото #{count} добавлено!\n\n"
            f"Загружено: {count} фото, {len([m for m in user_sessions[user_id]['media'] if m['type'] == 'video'])} видео\n\n"
            "Продолжайте загружать медиа или нажмите «✅ Завершить загрузку»",
            reply_markup=get_media_type_keyboard()
        )
    else:
        await message.answer("❌ Ошибка обработки фото. Попробуйте еще раз.")

@dp.message(F.video, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_video')
async def handle_video_upload(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    video_data = await download_video(message.video.file_id)
    if video_data:
        user_sessions[user_id]['media'].append({
            'type': 'video',
            'file_id': message.video.file_id,
            'thumbnail': f"https://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg"  # Заглушка
        })
        
        count = len([m for m in user_sessions[user_id]['media'] if m['type'] == 'video'])
        await message.answer(
            f"✅ Видео #{count} добавлено!\n\n"
            f"Загружено: {len([m for m in user_sessions[user_id]['media'] if m['type'] == 'photo'])} фото, {count} видео\n\n"
            "Продолжайте загружать медиа или нажмите «✅ Завершить загрузку»",
            reply_markup=get_media_type_keyboard()
        )
    else:
        await message.answer("❌ Ошибка обработки видео. Попробуйте еще раз.")

@dp.message(F.text == "✅ Завершить загрузку")
async def handle_finish_media(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    if len(user_sessions[user_id]['media']) == 0:
        await message.answer(
            "❌ Нужно загрузить хотя бы одно медиа (фото или видео)\n\n"
            "Выберите тип медиа для загрузки:",
            reply_markup=get_media_type_keyboard()
        )
        return
    
    user_sessions[user_id]['state'] = 'waiting_description'
    await message.answer(
        "📝 <b>ШАГ 2 из 8: Описание объекта</b>\n\n"
        "Напишите подробное описание объекта недвижимости:\n"
        "• Архитектура и стиль\n• Особенности планировки\n• Уникальные характеристики\n• Преимущества расположения\n\n"
        "<i>Чем подробнее описание, тем лучше сайт!</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_description')
async def handle_description(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]['description'] = message.text
    user_sessions[user_id]['style'] = detect_style_from_description(message.text)
    # Добавляем шаг выбора продвинутых стилей
    user_sessions[user_id]['state'] = 'waiting_style_choice'

    await message.answer(
        "✅ <b>Описание сохранено!</b>\n\n"
        "🎨 <b>Выберите стиль сайта</b>\n\n"
        "Можно выбрать один из ярких анимированных стилей или оставить авто-выбор по описанию.",
        reply_markup=get_style_choice_keyboard()
    )

@dp.message(F.text.in_(["🌆 Пиксельный город", "🌃 Неон-сити", "🅽 Neo-премиум", "🏠 Живой домик", 
                        "🌴 Тропический рай", "🚀 Космическая станция", "🎮 Ретро 80-х", "⚡ Киберпанк", "🧠 Авто по описанию"]))
async def handle_style_choice(message: types.Message):
    user_id = message.from_user.id
    if user_sessions.get(user_id, {}).get('state') != 'waiting_style_choice':
        return

    choice = message.text
    if choice == "🌴 Тропический рай":
        user_sessions[user_id]['style'] = {
            "key": "tropical_paradise",
            "name": "🌴 Тропический рай",
            "color": "#ff7e5f",
            "secondary": "#feb47b",
            "accent": "#00c6ff",
            "background": "tropical",
            "animation": "smooth"
        }
    elif choice == "🚀 Космическая станция":
        user_sessions[user_id]['style'] = {
            "key": "space_station",
            "name": "🚀 Космическая станция",
            "color": "#000428",
            "secondary": "#004e92",
            "accent": "#ff00cc",
            "background": "space",
            "animation": "galactic"
        }
    elif choice == "🎮 Ретро 80-х":
        user_sessions[user_id]['style'] = {
            "key": "retro_80s",
            "name": "🎮 Ретро 80-х",
            "color": "#ff6a00",
            "secondary": "#ee0979",
            "accent": "#ffd700",
            "background": "retro",
            "animation": "vintage"
        }
    elif choice == "⚡ Киберпанк":
        user_sessions[user_id]['style'] = {
            "key": "cyberpunk",
            "name": "⚡ Киберпанк",
            "color": "#0f0c29",
            "secondary": "#302b63",
            "accent": "#e74c3c",
            "background": "cyber",
            "animation": "glitch"
        }
    elif choice == "🌆 Пиксельный город":
        user_sessions[user_id]['style'] = {
            "key": "pixel_city",
            "name": "🏙️ Пиксельный город",
            "color": "#ff6b35",
            "secondary": "#2c3e50",
            "accent": "#f7c59f",
            "background": "pixel-city",
            "animation": "extreme"
        }
    elif choice == "🌃 Неон-сити":
        user_sessions[user_id]['style'] = {
            "key": "neon_city",
            "name": "🌌 Неон-сити",
            "color": "#00e6ff",
            "secondary": "#0a0a2a",
            "accent": "#ff00cc",
            "background": "neon-city",
            "animation": "extreme"
        }
    elif choice == "🅽 Neo-премиум":
        user_sessions[user_id]['style'] = {
            "key": "neo_premium",
            "name": "🅽 Neo-премиум",
            "color": "#8a2be2",
            "secondary": "#00e5ff",
            "accent": "#ff0066",
            "background": "neo",
            "animation": "extreme"
        }
    elif choice == "🏠 Живой домик":
        user_sessions[user_id]['style'] = {
            "key": "living_house",
            "name": "🏠 Живой домик",
            "color": "#ff9f1c",
            "secondary": "#2ec4b6",
            "accent": "#e71d36",
            "background": "living-house",
            "animation": "ultra"
        }
    # если авто по описанию — стиль уже выставлен ранее detect_style_from_description

    user_sessions[user_id]['state'] = 'waiting_title'
    await message.answer(
        "📝 <b>ШАГ 3 из 8: Название объекта</b>\n\n"
        "Придумайте краткое и запоминающееся название:\n"
        "<i>Пример: «Элитный комплекс RiverSide Residence»</i>",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_title')
async def handle_title(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]['title'] = message.text
    user_sessions[user_id]['state'] = 'waiting_price'
    
    await message.answer(
        "✅ <b>Название сохранено!</b>\n\n"
        "💰 <b>ШАГ 4 из 8: Цена объекта</b>\n\n"
        "Укажите стоимость объекта:\n"
        "<i>Пример: «125 000 000 руб.» или «Цена по запросу»</i>"
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_price')
async def handle_price(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]['price'] = message.text
    user_sessions[user_id]['state'] = 'waiting_location'
    
    await message.answer(
        "✅ <b>Цена сохранена!</b>\n\n"
        "📍 <b>ШАГ 5 из 8: Местоположение</b>\n\n"
        "Укажите адрес или район расположения:\n"
        "<i>Пример: «Москва, Пресненская набережная, 12»</i>"
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_location')
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]['location'] = message.text
    user_sessions[user_id]['state'] = 'waiting_specs'
    
    await message.answer(
        "✅ <b>Локация сохранена!</b>\n\n"
        "📐 <b>ШАГ 6 из 8: Характеристики</b>\n\n"
        "Укажите через запятую:\n"
        "• Площадь (кв.м)\n• Количество комнат\n• Срок сдачи\n\n"
        "<i>Пример: «150 кв.м, 3 комнаты, сдача в 2024 году»</i>"
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_specs')
async def handle_specs(message: types.Message):
    user_id = message.from_user.id
    specs = message.text.split(',')
    
    if len(specs) >= 1:
        user_sessions[user_id]['area'] = specs[0].strip()
    if len(specs) >= 2:
        user_sessions[user_id]['rooms'] = specs[1].strip()
    if len(specs) >= 3:
        user_sessions[user_id]['completion_date'] = specs[2].strip()
    
    user_sessions[user_id]['state'] = 'waiting_contacts_choice'
    
    await message.answer(
        "✅ <b>Характеристики сохранены!</b>\n\n"
        "👤 <b>ШАГ 7 из 8: Контактная информация</b>\n\n"
        "Хотите добавить ваши контакты на сайт?",
        reply_markup=get_yes_no_keyboard()
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_contacts_choice')
async def handle_contacts_choice(message: types.Message):
    user_id = message.from_user.id
    
    if message.text == "✅ Да":
        user_sessions[user_id]['state'] = 'waiting_contacts'
        await message.answer(
            "📞 <b>Укажите контактные данные:</b>\n\n"
            "Отправьте в формате:\n"
            "Телефон: +7 XXX XXX XX XX\n"
            "Email: your@email.com\n"
            "Telegram: @username\n\n"
            "<i>Можно указать не все данные</i>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Пропустить контакты")]],
                resize_keyboard=True
            )
        )
    else:
        user_sessions[user_id]['state'] = 'generating'
        await generate_website(message)

@dp.message(F.text == "Пропустить контакты")
async def skip_contacts(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]['state'] = 'generating'
    await generate_website(message)

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_contacts')
async def handle_contacts(message: types.Message):
    user_id = message.from_user.id
    text = message.text or ""

    # Регулярные выражения для извлечения контактов
    phone_match = re.search(r"телефон\s*:\s*([+\d][\d\s()\-]{6,})", text, flags=re.IGNORECASE)
    email_match = re.search(r"email\s*:\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, flags=re.IGNORECASE)
    tg_match = re.search(r"telegram\s*:\s*@?([A-Za-z0-9_]{4,})", text, flags=re.IGNORECASE)

    if phone_match:
        user_sessions[user_id]['broker_phone'] = phone_match.group(1).strip()
    if email_match:
        user_sessions[user_id]['broker_email'] = email_match.group(1).strip()
    if tg_match:
        user_sessions[user_id]['broker_tg'] = tg_match.group(1).strip()

    user_sessions[user_id]['state'] = 'generating'
    await generate_website(message)

async def generate_website(message: types.Message):
    user_id = message.from_user.id
    user_data = user_sessions[user_id]
    
    await message.answer("⏳ <b>Создаю профессиональный сайт...</b>\n\nЭто займет 1-2 минуты")
    
    try:
        # Генерируем HTML с медиафайлами
        html_content = await generate_website_html(user_data, user_data['media'])
        
        # Сохраняем в базу
        conn = sqlite3.connect('realtor_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO websites 
            (user_id, title, description, price, location, area, rooms, completion_date, 
             broker_phone, broker_email, broker_tg, style_used, html_content, media_files) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, user_data['title'], user_data['description'], user_data['price'], 
             user_data['location'], user_data['area'], user_data['rooms'], user_data['completion_date'],
             user_data.get('broker_phone'), user_data.get('broker_email'), user_data.get('broker_tg'),
             (user_data.get('style') or {}).get('name', ''), html_content, json.dumps(user_data['media'], ensure_ascii=False))
        )
        site_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Подменяем ссылку для лида на реальную deep-link ссылку
        bot_username = "ANton618_bot"
        lead_link = f"https://t.me/{bot_username}?start=lead_{site_id}"
        html_content = html_content.replace('LEAD_PLACEHOLDER', lead_link)
        
        # Папка публикации
        publish_dir = os.path.join('sites', f'site_{site_id}')
        media_dir = os.path.join(publish_dir, 'media')
        os.makedirs(media_dir, exist_ok=True)
        
        # Сохранение фото как файлов и замена data:base64 на ссылки
        try:
            photo_index = 1
            for m in user_data['media']:
                if m.get('type') == 'photo' and m.get('data') and m['data'].startswith('data:image'):
                    try:
                        b64 = m['data'].split('base64,', 1)[1]
                        data_bytes = base64.b64decode(b64)
                        rel_path = f'media/photo_{photo_index}.jpg'
                        abs_path = os.path.join(publish_dir, rel_path)
                        with open(abs_path, 'wb') as imgf:
                            imgf.write(data_bytes)
                        # Заменяем base64 на относительный путь
                        m['data'] = rel_path
                        photo_index += 1
                    except Exception as ie:
                        logger.error(f"Ошибка сохранения фото: {ie}")
        except Exception as se:
            logger.error(f"Ошибка обработки медиа: {se}")
        
        # Сохранение видео как файлов
        try:
            video_index = 1
            for m in user_data['media']:
                if m.get('type') == 'video' and m.get('file_id'):
                    try:
                        file = await bot.get_file(m['file_id'])
                        video_data = await bot.download_file(file.file_path)
                        rel_path = f'media/video_{video_index}.mp4'
                        abs_path = os.path.join(publish_dir, rel_path)
                        with open(abs_path, 'wb') as vidf:
                            vidf.write(video_data.read())
                        # Заменяем file_id на относительный путь
                        m['file_id'] = rel_path
                        video_index += 1
                    except Exception as ve:
                        logger.error(f"Ошибка сохранения видео: {ve}")
        except Exception as se:
            logger.error(f"Ошибка обработки видео: {se}")
        
        # Публикация
        try:
            os.makedirs(publish_dir, exist_ok=True)
            publish_path = os.path.join(publish_dir, 'index.html')
            with open(publish_path, 'w', encoding='utf-8') as pf:
                pf.write(html_content)
        except Exception as pe:
            logger.error(f"Ошибка публикации сайта: {pe}")
        
        # Отправка файла пользователю
        filename = f"site_{user_data['title'].replace(' ', '_')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        with open(filename, 'rb') as f:
            await message.answer_document(
                types.BufferedInputFile(
                    f.read(),
                    filename=filename
                ),
                caption=(
                    f"🎉 <b>Сайт успешно создан!</b>\n\n"
                    f"🏠 <b>Название:</b> {user_data['title']}\n"
                    f"🎨 <b>Стиль:</b> {(user_data.get('style') or {}).get('name', 'Авто')}\n"
                    f"📷 <b>Медиа:</b> {len([m for m in user_data['media'] if m['type'] == 'photo'])} фото, {len([m for m in user_data['media'] if m['type'] == 'video'])} видео\n"
                    f"🗺️ <b>Карта:</b> {'Да' if user_data.get('location') else 'Нет'}\n\n"
                    f"🌐 <b>Путь публикации:</b> sites/site_{site_id}/index.html\n"
                    f"📩 <b>Лид-ссылка:</b> {lead_link}\n"
                    f"💾 <b>Сохраните файл и откройте в браузере</b>"
                ),
                reply_markup=get_main_menu()
            )
        
        os.remove(filename)
        
    except Exception as e:
        logger.error(f"Ошибка генерации сайта: {e}")
        await message.answer("❌ <b>Ошибка при создании сайта</b>\n\nПопробуйте еще раз")
    
    user_sessions.pop(user_id, None)

@dp.message(F.text == "📚 Мои сайты")
async def show_websites(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('realtor_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, title, created_at FROM websites WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
        (user_id,)
    )
    websites = cursor.fetchall()
    conn.close()
    
    if not websites:
        await message.answer("📭 <b>У вас еще нет созданных сайтов</b>\n\nНачните с кнопки «Создать сайт»")
        return
    
    # Сохраним список сайтов в сессию для последующего редактирования
    user_sessions[user_id] = user_sessions.get(user_id, {})
    user_sessions[user_id]['last_websites'] = websites
    
    response = "📚 <b>Ваши созданные сайты:</b>\n\n"
    for i, (site_id, title, created_at) in enumerate(websites, 1):
        response += f"{i}. <b>{title}</b>\n   📅 {created_at[:10]}\n\n"
    
    response += (
        f"<b>Всего сайтов:</b> {len(websites)}\n\n"
        f"Чтобы пересоздать сайт, отправьте: <code>Редактировать N</code> (например: Редактировать 1)"
    )
    await message.answer(response)

@dp.message(F.text.regexp(r'^Редактировать\s+(\d+)$'))
async def edit_website_quick(message: types.Message, regexp: types.Message):
    user_id = message.from_user.id
    idx_str = regexp.group(1)
    try:
        idx = int(idx_str)
        last = user_sessions.get(user_id, {}).get('last_websites')
        if not last or idx < 1 or idx > len(last):
            await message.answer("❌ Неверный номер. Откройте ‘Мои сайты' и повторите.")
            return
        site_id = last[idx-1][0]
        # Загрузим данные сайта
        conn = sqlite3.connect('realtor_bot.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT title, description, price, location, area, rooms, completion_date,
                                 broker_phone, broker_email, broker_tg, style_used, html_content, media_files
                          FROM websites WHERE id = ? AND user_id = ?''', (site_id, user_id))
        row = cursor.fetchone()
        conn.close()
        if not row:
            await message.answer("❌ Сайт не найден")
            return
        (title, description, price, location, area, rooms, completion_date,
         broker_phone, broker_email, broker_tg, style_used, html_content, media_files) = row
        # Подготовим user_data для регенерации
        try:
            media = json.loads(media_files) if media_files else []
        except Exception:
            media = []
        # Определим стиль (по имени сохранённого)
        style = {}
        if style_used:
            style = {"name": style_used, "key": ""}
        user_sessions[user_id] = {
            'state': 'generating',
            'media': media,
            'title': title,
            'description': description,
            'price': price,
            'location': location,
            'area': area,
            'rooms': rooms,
            'completion_date': completion_date,
            'broker_phone': broker_phone,
            'broker_email': broker_email,
            'broker_tg': broker_tg,
            'style': style,
            'regenerate_site_id': site_id
        }
        await generate_website(message)
    except Exception as e:
        logger.error(f"Ошибка редактирования: {e}")
        await message.answer("❌ Не удалось пересоздать сайт. Попробуйте позже.")

@dp.message(F.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    await message.answer(
        "⚙️ <b>Настройки бота</b>\n\n"
        "• Минимум фото: 1\n• Максимум фото: 12\n"
        "• Поддержка видео\n• Google Maps интеграция\n"
        "• Автоматический подбор стиля\n"
        "• Профессиональный HTML/CSS\n"
        "• Адаптивный дизайн\n"
        "• Современные анимации\n\n"
        "<i>Все настройки оптимизированы для лучшего качества</i>"
    )
    print("🗺️ Интеграция с Google Maps")
    print("💾 База данных SQLite")
    
    await dp.start_polling(bot)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())






