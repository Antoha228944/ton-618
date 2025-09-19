import os
import logging
import sqlite3
import asyncio
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
import textwrap
import re
from PIL import Image
import io

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = "8358851724:AAEVVzB4EqDqmWNLjrAnW2mZVnALCzPqWzw"
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Функция для исправления существующей базы
def fix_database():
    """Добавляет недостающие колонки в существующую базу"""
    try:
        conn = sqlite3.connect('realtor_bot.db')
        cursor = conn.cursor()
        
        # Проверяем есть ли таблица websites
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='websites'")
        if not cursor.fetchone():
            print("📊 Таблицы еще не созданы, создадим новые")
            conn.close()
            return
            
        # Проверяем есть ли колонка price
        cursor.execute("PRAGMA table_info(websites)")
        columns = [column[1] for column in cursor.fetchall()]
        
        missing_columns = []
        required_columns = ['price', 'location', 'area', 'rooms', 'completion_date', 
                          'broker_phone', 'broker_email', 'broker_tg', 'style_used']
        
        for column in required_columns:
            if column not in columns:
                missing_columns.append(column)
        
        if missing_columns:
            print(f"🔄 Добавляю недостающие колонки: {missing_columns}")
            for column in missing_columns:
                try:
                    cursor.execute(f'ALTER TABLE websites ADD COLUMN {column} TEXT')
                except sqlite3.OperationalError:
                    print(f"Колонка {column} уже существует")
            conn.commit()
            print("✅ База данных обновлена!")
        else:
            print("✅ Все колонки на месте")
            
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

# ===== ГЕНЕРАЦИЯ САЙТА =====

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

def detect_style_from_description(description):
    """Определяет стиль сайта на основе описания"""
    desc_lower = description.lower()
    
    styles = {
        "luxury": {"name": "Роскошный", "color": "#d4af37", "secondary": "#2c3e50", "accent": "#8b4513"},
        "modern": {"name": "Современный", "color": "#34495e", "secondary": "#e74c3c", "accent": "#3498db"},
        "classic": {"name": "Классический", "color": "#8b4513", "secondary": "#d4af37", "accent": "#2c3e50"},
        "beach": {"name": "Пляжный", "color": "#0077be", "secondary": "#f4a460", "accent": "#87ceeb"},
        "urban": {"name": "Урбан", "color": "#2c3e50", "secondary": "#7f8c8d", "accent": "#e74c3c"},
    }
    
    for style, data in styles.items():
        if style in desc_lower:  # проверка ключевого слова
            return data
    
    # Стиль по умолчанию
    return {"name": "Премиум", "color": "#2c3e50", "secondary": "#3498db", "accent": "#e74c3c"}


async def generate_website_html(user_data, photo_urls):
    """Генерирует профессиональный HTML сайт"""
    
    style = user_data['style']
    photos = photo_urls[:12]  # Максимум 12 фото
    
    # Формируем галерею
    gallery_html = ""
    for i, photo_data in enumerate(photos):
        if photo_data:
            gallery_html += f'''
            <div class="gallery-item">
                <img src="{photo_data}" alt="Фото объекта {i+1}" loading="lazy">
                <div class="gallery-overlay">
                    <span class="gallery-number">{i+1}</span>
                </div>
            </div>'''
        else:
            gallery_html += f'<div class="gallery-item placeholder">Фото {i+1}</div>'
    
    # Контактная информация (только если есть данные)
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
    
    # Дополнительные контакты (офис и часы работы)
    if user_data.get('broker_office'):
        contacts_html += f'''
        <div class="contact-item">
            <div class="contact-icon">🏢</div>
            <div class="contact-info">
                <h4>Офис</h4>
                <p>{user_data['broker_office']}</p>
            </div>
        </div>'''
    
    if user_data.get('broker_hours'):
        contacts_html += f'''
        <div class="contact-item">
            <div class="contact-icon">⏰</div>
            <div class="contact-info">
                <h4>Часы работы</h4>
                <p>{user_data['broker_hours']}</p>
            </div>
        </div>'''
    
    # Характеристики (только заполненные)
    specs_html = ""
    specs = [
        ("💰 Цена", user_data.get('price')),
        ("📍 Локация", user_data.get('location')),
        ("📐 Площадь", user_data.get('area')),
        ("🚪 Комнаты", user_data.get('rooms')),
        ("📅 Срок сдачи", user_data.get('completion_date')),
        ("🛋️ Отделка", user_data.get('decoration')),
        ("🌳 Инфраструктура", user_data.get('infrastructure')),
        ("🚗 Парковка", user_data.get('parking'))
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

    # Формируем CTA кнопки (только если есть контакты)
    cta_buttons_html = ""
    if user_data.get('broker_phone') or user_data.get('broker_tg'):
        cta_buttons_html += '<div class="cta-buttons">'
        
        if user_data.get('broker_phone'):
            cta_buttons_html += f'''
            <a href="tel:{user_data['broker_phone']}" class="btn">
                <i class="fas fa-phone"></i> Позвонить сейчас
            </a>'''
        
        if user_data.get('broker_tg'):
            cta_buttons_html += f'''
            <a href="https://t.me/{user_data['broker_tg']}" class="btn btn-outline">
                <i class="fab fa-telegram"></i> Написать в Telegram
            </a>'''
        
        cta_buttons_html += '</div>'

    html_content = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{user_data['title']} - Профессиональная презентация</title>
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
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            line-height: 1.7;
            color: var(--text);
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            min-height: 100vh;
            overflow-x: hidden;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            padding: 80px 0;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="50" cy="50" r="1" fill="rgba(255,255,255,0.1)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
            opacity: 0.1;
        }}
        
        .header-content {{
            position: relative;
            z-index: 2;
        }}
        
        .property-badge {{
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(10px);
            padding: 12px 25px;
            border-radius: 50px;
            display: inline-block;
            margin-bottom: 30px;
            font-weight: 600;
            font-size: 0.9rem;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        
        .property-title {{
            font-size: 4rem;
            font-weight: 800;
            margin-bottom: 20px;
            line-height: 1.2;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .property-description {{
            font-size: 1.4rem;
            margin-bottom: 40px;
            opacity: 0.95;
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
            line-height: 1.6;
        }}
        
        .property-price {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 40px;
            color: var(--accent);
            text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
        }}
        
        /* Navigation */
        .nav-scroll {{
            background: white;
            padding: 25px 0;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        
        .nav-container {{
            display: flex;
            justify-content: center;
            gap: 40px;
        }}
        
        .nav-item {{
            color: var(--text);
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            padding: 10px 20px;
            border-radius: 25px;
            transition: var(--transition);
            position: relative;
        }}
        
        .nav-item:hover {{
            color: var(--primary);
            transform: translateY(-2px);
        }}
        
        .nav-item::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            width: 0;
            height: 3px;
            background: var(--primary);
            transition: var(--transition);
            transform: translateX(-50%);
            border-radius: 3px;
        }}
        
        .nav-item:hover::after {{
            width: 60%;
        }}
        
        /* Sections */
        .section {{
            padding: 100px 0;
        }}
        
        .section-title {{
            font-size: 3rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 60px;
            color: var(--dark);
            position: relative;
        }}
        
        .section-title::after {{
            content: '';
            position: absolute;
            bottom: -15px;
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--accent));
            border-radius: 2px;
        }}
        
        /* About Section */
        .about-content {{
            background: white;
            padding: 60px;
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            margin-bottom: 60px;
            line-height: 1.8;
            font-size: 1.2rem;
        }}
        
        /* Specifications */
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
            color: var(--primary);
            flex-shrink: 0;
        }}
        
        .spec-content h4 {{
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--dark);
        }}
        
        .spec-content p {{
            color: var(--text-light);
            font-size: 1.1rem;
        }}
        
        /* Gallery */
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            margin-bottom: 60px;
        }}
        
        .gallery-item {{
            position: relative;
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow);
            transition: var(--transition);
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
        
        .gallery-item.placeholder {{
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.3rem;
            font-weight: 600;
        }}
        
        /* Contact Section */
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
        
        /* CTA Buttons */
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
        
        /* Footer */
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
        
        /* Animations */
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
        
        /* Responsive */
        @media (max-width: 1200px) {{
            .property-title {{ font-size: 3rem; }}
            .section-title {{ font-size: 2.5rem; }}
        }}
        
        @media (max-width: 768px) {{
            .property-title {{ font-size: 2.2rem; }}
            .property-description {{ font-size: 1.1rem; }}
            .property-price {{ font-size: 1.8rem; }}
            .section-title {{ font-size: 2rem; }}
            .section {{ padding: 60px 0; }}
            .gallery {{ grid-template-columns: 1fr; }}
            .specs-grid {{ grid-template-columns: 1fr; }}
            .contact-grid {{ grid-template-columns: 1fr; }}
            .cta-buttons {{ flex-direction: column; }}
            .nav-container {{ flex-wrap: wrap; gap: 20px; }}
            .about-content {{ padding: 30px; }}
        }}
        
        @media (max-width: 480px) {{
            .property-title {{ font-size: 1.8rem; }}
            .header {{ padding: 60px 0; }}
            .section {{ padding: 40px 0; }}
        }}
        
        /* Additional styles for empty states */
        .no-specs, .no-photos {{
            text-align: center;
            color: var(--text-light);
            font-size: 1.2rem;
            padding: 40px;
            grid-column: 1 / -1;
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content animate">
                <div class="property-badge">Элитная недвижимость</div>
                <h1 class="property-title">{user_data['title']}</h1>
                <p class="property-description">{user_data['description']}</p>
                <div class="property-price">{user_data.get('price', 'Цена по запросу')}</div>
                
                {cta_buttons_html if cta_buttons_html else ''}
            </div>
        </div>
    </header>

    <!-- Navigation -->
    <nav class="nav-scroll">
        <div class="container">
            <div class="nav-container">
                <a href="#about" class="nav-item">О проекте</a>
                <a href="#specs" class="nav-item">Характеристики</a>
                <a href="#gallery" class="nav-item">Галерея</a>
                <a href="#location" class="nav-item">Расположение</a>
                { '<a href="#contact" class="nav-item">Контакты</a>' if contacts_html else '' }
            </div>
        </div>
    </nav>

    <!-- About Section -->
    <section id="about" class="section">
        <div class="container">
            <h2 class="section-title">О проекте</h2>
            <div class="about-content animate">
                <p>{user_data['description']}</p>
            </div>
        </div>
    </section>

    <!-- Specifications -->
    <section id="specs" class="section" style="background: #f8f9fa;">
        <div class="container">
            <h2 class="section-title">Характеристики</h2>
            <div class="specs-grid">
                {specs_html if specs_html else '<p class="no-specs">Характеристики не указаны</p>'}
            </div>
        </div>
    </section>

    <!-- Gallery -->
    <section id="gallery" class="section">
        <div class="container">
            <h2 class="section-title">Фотогалерея</h2>
            <div class="gallery">
                {gallery_html if gallery_html else '<p class="no-photos">Фотографии не добавлены</p>'}
            </div>
        </div>
    </section>

    <!-- Location -->
    <section id="location" class="section" style="background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); color: white;">
        <div class="container">
            <h2 class="section-title" style="color: white;">Расположение</h2>
            <div class="about-content" style="background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); color: white;">
                <h3 style="margin-bottom: 20px; color: white;">{user_data.get('location', 'Престижный район')}</h3>
                <p>Объект расположен в одном из самых престижных и развитых районов города. Отличная транспортная доступность, развитая инфраструктура, близость к парковым зонам и основным магистралям.</p>
            </div>
        </div>
    </section>

 contacts_html = ""
for contact in contacts_list:  # допустим, у тебя список контактов
    cont   <div class="contact-item">
# Формируем HTML контактов
contacts_html = ""
for contact in contacts_list:  # contacts_list — список словарей с контактами
    contacts_html += f'''
# Список контактов (пример)
# Пример списка контактов
contacts_list = [
    {"name": "Антон", "phone": "+79161234567"},
    {"name": "Ирина", "phone": "+79169876543"}
]

# Формируем HTML контактов
contacts_html = ""
for contact in contacts_list:
    contacts_html += f'''
    <div class="contact-item">
        <p>Имя контакта: {contact.get("name", "")}</p>
        <p>Телефон: {contact.get("phone", "")}</p>
    </div>
    '''

# Основной шаблон страницы
full_html = f'''
<section id="contact" class="contact-section">
    <div class="container">
        <h2 class="section-title" style="color: white;">Контакты</h2>
        <div class="contact-grid">
            {contacts_html}
        </div>
    </div>
</section>

<footer class="footer">
    <div class="container">
        <p>© 2024 {user_data['title']}. Все права защищены.</p>
        <div class="watermark">
            Сайт создан через @ANton618_bot
        </div>
    </div>
</footer>
''' 

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
    
    welcome_text = f"""
<b>🏆 ПРОФЕССИОНАЛЬНЫЙ ГЕНЕРАТОР САЙТОВ</b>

💎 <i>Создаю сайты премиум-класса для элитной недвижимости</i>

✨ <b>ПОЛНЫЙ КОНТРОЛЬ:</b>
• 📷 Ваши реальные фото в HD качестве
• 💰 Указание цены и сроков сдачи
• 📍 Точное местоположение объекта
• 👤 Контакты брокера (по желанию)
• 🎨 Профессиональный адаптивный дизайн
• ⚡ Современные анимации и эффекты

<code>Начните с кнопки «Создать сайт» 👇</code>
"""
    
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(F.text == "🌐 Создать сайт")
async def start_creation(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id] = {
        'state': 'waiting_photos',
        'photos': [],
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
        "📸 <b>ШАГ 1 из 8: Фотографии объекта</b>\n\n"
        "Отправьте от 1 до 12 фотографий высокого качества\n"
        "Эти фото будут использованы на сайте в HD качестве\n\n"
        "<i>Отправляйте по одной фотографии за раз. Когда закончите, напишите «Готово»</i>"
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    if len(user_sessions[user_id]['photos']) >= 12:
        await message.answer(
            "✅ <b>Максимум 12 фото достигнут</b>\n\n"
            "Напишите «Готово» чтобы перейти к следующему шагу"
        )
        return
    
    user_sessions[user_id]['photos'].append(message.photo[-1].file_id)
    count = len(user_sessions[user_id]['photos'])
    
    if count == 1:
        await message.answer("✅ <b>Первое фото получено</b>\nПродолжайте отправлять фото или напишите «Готово»")
    elif count == 3:
        await message.answer("✅ <b>3 фото получено</b>\nМожно остановиться (напишите «Готово») или добавить еще")
    elif count == 6:
        await message.answer("✅ <b>6 фото получено</b>\nОтличное количество для сайта! Можно писать «Готово»")
    elif count == 12:
        await message.answer("✅ <b>12 фото - максимум!</b>\nНапишите «Готово» чтобы продолжить")

@dp.message(F.text == "Готово")
async def handle_done(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions: return
    
    if user_sessions[user_id]['state'] == 'waiting_photos':
        if len(user_sessions[user_id]['photos']) == 0:
            await message.answer("❌ <b>Нужно отправить хотя бы 1 фото</b>\n\nОтправьте фотографии объекта")
            return
        
        await ask_for_description(message)
    else:
        await message.answer("Неизвестная команда")

async def ask_for_description(message):
    user_id = message.from_user.id
    user_sessions[user_id]['state'] = 'waiting_description'
    await message.answer(
        "📝 <b>ШАГ 2 из 8: Описание объекта</b>\n\n"
        "Напишите подробное описание объекта недвижимости:\n"
        "• Архитектура и стиль\n• Особенности планировки\n• Уникальные характеристики\n• Преимущества расположения\n\n"
        "<i>Чем подробнее описание, тем лучше сайт!</i>"
    )

@dp.message(F.text, lambda msg: user_sessions.get(msg.from_user.id, {}).get('state') == 'waiting_description')
async def handle_description(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]['description'] = message.text
    user_sessions[user_id]['style'] = detect_style_from_description(message.text)
    user_sessions[user_id]['state'] = 'waiting_title'
    
    await message.answer(
        "✅ <b>Описание сохранено!</b>\n\n"
        "📝 <b>ШАГ 3 из 8: Название объекта</b>\n\n"
        "Придумайте краткое и запоминающееся название:\n"
        "<i>Пример: «Элитный комплекс RiverSide Residence»</i>"
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
    text = message.text
    
    # Парсим контакты из текста
    if 'Телефон:' in text:
        user_sessions[user_id]['broker_phone'] = text.split('Телефон:')[1].split('\n')[0].strip()
    if 'Email:' in text:
        user_sessions[user_id]['broker_email'] = text.split('Email:')[1].split('\n')[0].strip()
    if 'Telegram:' in text:
        user_sessions[user_id]['broker_tg'] = text.split('Telegram:')[1].split('\n')[0].strip().replace('@', '')
    
    user_sessions[user_id]['state'] = 'generating'
    await generate_website(message)

async def generate_website(message: types.Message):
    user_id = message.from_user.id
    user_data = user_sessions[user_id]
    
    await message.answer("⏳ <b>Создаю профессиональный сайт...</b>\n\nЭто займет 1-2 минуты")
    
    try:
        # Скачиваем и обрабатываем фото
        photo_urls = []
        for photo_id in user_data['photos']:
            photo_url = await download_photo(photo_id)
            if photo_url:
                photo_urls.append(photo_url)
        
        # Генерируем HTML
        html_content = await generate_website_html(user_data, photo_urls)
        
        # Сохраняем в базу
        conn = sqlite3.connect('realtor_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO websites 
            (user_id, title, description, price, location, area, rooms, completion_date, 
             broker_phone, broker_email, broker_tg, style_used, html_content) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, user_data['title'], user_data['description'], user_data['price'], 
             user_data['location'], user_data['area'], user_data['rooms'], user_data['completion_date'],
             user_data.get('broker_phone'), user_data.get('broker_email'), user_data.get('broker_tg'),
             user_data['style']['name'], html_content)
        )
        conn.commit()
        conn.close()
        
        # Сохраняем HTML в файл и сразу отправляем
        filename = f"site_{user_data['title'].replace(' ', '_')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        with open(filename, 'rb') as f:
            await message.answer_document(
                types.BufferedInputFile(
                    f.read(),
                    filename=filename
                ),
                caption=f"🎉 <b>Сайт успешно создан!</b>\n\n"
                       f"🏠 <b>Название:</b> {user_data['title']}\n"
                       f"🎨 <b>Стиль:</b> {user_data['style']['name']}\n"
                       f"📷 <b>Фото:</b> {len(photo_urls)} из {len(user_data['photos'])}\n\n"
                       f"💾 <b>Сохраните файл и откройте в браузере</b>\n"
                       f"📚 <b>Сайт также сохранен в вашей истории</b>",
                reply_markup=get_main_menu()
            )
        
        # Удаляем временный файл
        os.remove(filename)
        
    except Exception as e:
        logger.error(f"Ошибка генерации сайта: {e}")
        await message.answer("❌ <b>Ошибка при создании сайта</b>\n\nПопробуйте еще раз")
    
    # Очищаем сессию
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
    
    response = "📚 <b>Ваши созданные сайты:</b>\n\n"
    for i, (site_id, title, created_at) in enumerate(websites, 1):
        response += f"{i}. <b>{title}</b>\n   📅 {created_at[:10]}\n\n"
    
    response += f"<b>Всего сайтов:</b> {len(websites)}"
    await message.answer(response)

@dp.message(F.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    await message.answer(
        "⚙️ <b>Настройки бота</b>\n\n"
        "• Минимум фото: 1\n• Максимум фото: 12\n"
        "• Автоматический подбор стиля\n"
        "• Профессиональный HTML/CSS\n"
        "• Адаптивный дизайн\n"
        "• Современные анимации\n\n"
        "<i>Все настройки оптимизированы для лучшего качества</i>"
    )

async def main():
    print("🚀 ПРОФЕССИОНАЛЬНЫЙ бот запускается...")
    print("💎 Генератор сайтов премиум-класса готов")
    print("🎯 Полный контроль над контентом и дизайном")
    
    from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.utils.webhook import start_webhook
from config import BOT_TOKEN  # <- твой токен здесь

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

WEBHOOK_URL = "https://ТВОЙ_СЕРВИС.onrender.com/webhook"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8000

async def on_startup(dispatcher: Dispatcher):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dispatcher: Dispatcher):
    await bot.delete_webhook()

# Пример обработчика сообщений
@dp.message()
async def echo(message: Message):
    await message.answer(f"Вы сказали: {message.text}")

if __name__ == "__main__":
    start_webhook(
        dispatcher=dp,
        webhook_path="/webhook",
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
