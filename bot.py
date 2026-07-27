import asyncio
import logging
import html
import sys
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputMediaPhoto,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

# 🛠 ФИКС ДЛЯ WINDOWS (Убирает WinError 121 / Semaphore Timeout)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)

# 🔑 Твой токен от @BotFather
BOT_TOKEN = "8725774318:AAFeU98t4669xvRf21eeUmxAqyog-ExM0Fo"

# 👑 ID Администраторов
ADMIN_IDS = [8667346615]

# 📢 ID КАНАЛА ДЛЯ ПРОФИТОВ
PROFIT_CHANNEL_ID = -100123456789

# ==========================================
# 💾 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite)
# ==========================================
DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            approved INTEGER,
            joined_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            amount REAL,
            country TEXT,
            mentor TEXT,
            date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_mentors (
            user_id INTEGER PRIMARY KEY,
            mentor_username TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Функции работы с БД
def db_get_user(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT approved, joined_date, username FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"approved": bool(row[0]), "joined_date": datetime.fromisoformat(row[1]), "username": row[2]}
    return None

def db_save_user(user_id: int, username: str, approved: bool, joined_date: datetime):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, approved, joined_date)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            approved = excluded.approved
    ''', (user_id, username, int(approved), joined_date.isoformat()))
    conn.commit()
    conn.close()

def db_update_approval(user_id: int, approved: bool):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET approved = ?, joined_date = ? WHERE user_id = ?", 
                   (int(approved), datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def is_approved(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    user = db_get_user(user_id)
    return user.get("approved", False) if user else False

def db_add_profit(username: str, amount: float, country: str, mentor: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO profits (username, amount, country, mentor, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, amount, country, mentor, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def db_get_all_profits():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, amount, country, mentor, date FROM profits")
    rows = cursor.fetchall()
    conn.close()
    
    profits = []
    for r in rows:
        profits.append({
            "username": r[0],
            "amount": r[1],
            "country": r[2],
            "mentor": r[3],
            "date": datetime.fromisoformat(r[4])
        })
    return profits

def db_set_mentor(user_id: int, mentor_username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_mentors (user_id, mentor_username)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET mentor_username = excluded.mentor_username
    ''', (user_id, mentor_username))
    conn.commit()
    conn.close()

def db_get_mentor(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT mentor_username FROM user_mentors WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


# ==========================================
# 🖼 ССЫЛКИ И ПУТИ К КАРТИНКАМ
# ==========================================
IMAGES = {
    "main_menu": "main_menu.jpg",
    "profile": "profile.jpg",
    "top": "top.jpg",
    "info": "info.png",
    "cashdesk": "cashdesk.png",
    "mentors": "mentors.png",
    "manuals": "manuals.png",
    "market": "market.png",
    "profit_post": "profit.jpg"
}

# ==========================================
# 🔗 ССЫЛКИ И НАСТРОЙКИ
# ==========================================
INFO_URLS = {
    "training": "https://t.me/+OYQh5vBbiic4YmNh",
    "payouts": "https://t.me/+Xhf_GmNMOSVjYWYx"
}

MARKET_BUY_URL = "https://t.me/aIadin_work"

MARKET_ITEMS = {
    "esim": {
        "title": "E-sim",
        "price": "13",
        "description": "Быстрое подключение\n\nПодходит под любые платформы\n\nГотово к работе сразу"
    },
    "whatsapp": {
        "title": "Whatsapp",
        "price": "10",
        "description": "Качественные аккаунты Whatsapp\n\nВысокая отлёжка\n\nГотовы к работе"
    },
    "proxy": {
        "title": "Proxy",
        "price": "7",
        "description": "Приватные резидентские прокси\n\nВысокая скорость и анонимность\n\nПодходят под любые цели"
    }
}

MANUAL_URLS = {
    "romania": "https://t.me/+CV3VUPF2KdZhM2Ex",
    "bulgaria": "https://t.me/+RmdTi7KHVkQwNGNh",
    "portugal": "https://t.me/+Fd96y7MjAio4NjE5",
    "spain": "https://t.me/+uEBpspDx1tY3MTUx",
    "uk": "https://t.me/+HltLSd3hl_o1ZTBh",
    "poland": "https://t.me/+Xy3lynB05eljN2Ux",
}

COUNTRY_FLAGS = {
    "румыния": "🇷🇴", "болгария": "🇧🇬", "португалия": "🇵🇹",
    "испания": "🇪🇸", "великобритания": "🇬🇧", "англия": "🇬🇧", "польша": "🇵🇱",
}

MENTORS_DATA = {
    "aIadin_work": {"username": "aIadin_work", "percent": "15%", "description": "Профессиональный наставник"},
    "qwertyygod": {"username": "qwertyygod", "percent": "15%", "description": "Профессиональный наставник"}
}


# ==========================================
# 📐 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def filter_profits_by_period(period: str):
    now = datetime.now()
    profits_db = db_get_all_profits()
    filtered = []
    for p in profits_db:
        p_date = p["date"]
        if period == "day" and p_date.date() == now.date():
            filtered.append(p)
        elif period == "week" and p_date >= (now - timedelta(days=7)):
            filtered.append(p)
        elif period == "month" and p_date >= (now - timedelta(days=30)):
            filtered.append(p)
        elif period == "all":
            filtered.append(p)
    return filtered


def get_stats_for_period(period: str):
    profits = filter_profits_by_period(period)
    total_sum = sum(p["amount"] for p in profits)
    count = len(profits)
    return total_sum, count


def get_top_workers(period: str = "all", limit: int = 10):
    profits = filter_profits_by_period(period)
    workers = {}
    for p in profits:
        uname = p["username"]
        if uname not in workers:
            workers[uname] = {"sum": 0.0, "count": 0}
        workers[uname]["sum"] += p["amount"]
        workers[uname]["count"] += 1
    sorted_top = sorted(workers.items(), key=lambda x: x[1]["sum"], reverse=True)
    return sorted_top[:limit]


def get_mentor_stats(mentor_username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_mentors WHERE LOWER(mentor_username) = ?", (mentor_username.lower(),))
    students_ids = cursor.fetchall()
    conn.close()
    students_count = len(students_ids)

    profits_db = db_get_all_profits()
    mentor_profits = [p for p in profits_db if p.get("mentor", "").lower() == mentor_username.lower()]
    total_sum = sum(p["amount"] for p in mentor_profits)
    profits_count = len(mentor_profits)
    return students_count, profits_count, total_sum


def get_photo(photo_path: str):
    if photo_path.startswith("http://") or photo_path.startswith("https://"):
        return photo_path
    return FSInputFile(photo_path)


# ==========================================
# ⌨️ КЛАВИАТУРЫ
# ==========================================
def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
            [
                InlineKeyboardButton(text="🏆 Топ", callback_data="top_day"),
                InlineKeyboardButton(text="🎡 Информация", callback_data="info_menu"),
            ],
            [
                InlineKeyboardButton(text="💸 Касса", callback_data="cashdesk_all"),
                InlineKeyboardButton(text="👨‍🏫 Наставники", callback_data="mentors"),
            ],
            [
                InlineKeyboardButton(text="🎓 Мануалы", callback_data="manuals"),
                InlineKeyboardButton(text="🛒 Маркет", callback_data="market"),
            ],
        ]
    )


def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")]
        ]
    )


def get_top_keyboard(active_period: str = "day") -> InlineKeyboardMarkup:
    p = active_period
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{'•' if p == 'all' else ''} За все время", callback_data="top_all")],
            [
                InlineKeyboardButton(text=f"{'•' if p == 'day' else ''} День", callback_data="top_day"),
                InlineKeyboardButton(text=f"{'•' if p == 'week' else ''} Неделя", callback_data="top_week"),
                InlineKeyboardButton(text=f"{'•' if p == 'month' else ''} Месяц", callback_data="top_month"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")],
        ]
    )


def get_cashdesk_keyboard(active_period: str = "all") -> InlineKeyboardMarkup:
    p = active_period
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{'•' if p == 'day' else ''} День", callback_data="cash_day"),
                InlineKeyboardButton(text=f"{'•' if p == 'week' else ''} Неделя", callback_data="cash_week"),
                InlineKeyboardButton(text=f"{'•' if p == 'month' else ''} Месяц", callback_data="cash_month"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")],
        ]
    )


def get_manuals_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇴 Румыния ↗", url=MANUAL_URLS["romania"])],
            [InlineKeyboardButton(text="🇧🇬 Болгария ↗", url=MANUAL_URLS["bulgaria"])],
            [InlineKeyboardButton(text="🇵🇹 Португалия ↗", url=MANUAL_URLS["portugal"])],
            [InlineKeyboardButton(text="🇪🇸 Испания ↗", url=MANUAL_URLS["spain"])],
            [InlineKeyboardButton(text="🇬🇧 Великобритания ↗", url=MANUAL_URLS["uk"])],
            [InlineKeyboardButton(text="🇵🇱 Польша ↗", url=MANUAL_URLS["poland"])],
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")],
        ]
    )


def get_info_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обучение ↗", url=INFO_URLS["training"])],
            [InlineKeyboardButton(text="Канал с выплатами ↗", url=INFO_URLS["payouts"])],
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")],
        ]
    )


def get_mentors_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="■ @aIadin_work 15%", callback_data="mentor_view_aIadin_work"),
                InlineKeyboardButton(text="■ @qwertyygod 15%", callback_data="mentor_view_qwertyygod"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")],
        ]
    )


def get_mentor_card_keyboard(mentor_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📌 Закрепиться за этим наставником",
                                  callback_data=f"mentor_select_{mentor_username}")],
            [InlineKeyboardButton(text="« Назад", callback_data="mentors")],
        ]
    )


def get_market_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="E-sim — 13", callback_data="item_esim")],
            [InlineKeyboardButton(text="Whatsapp — 10", callback_data="item_whatsapp")],
            [InlineKeyboardButton(text="Proxy — 7", callback_data="item_proxy")],
            [InlineKeyboardButton(text="« Назад", callback_data="main_menu")],
        ]
    )


def get_item_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="☎️ Покупка и вопросы ↗", url=MARKET_BUY_URL)],
            [InlineKeyboardButton(text="« Назад", callback_data="market")],
        ]
    )


# ==========================================
# 📝 ТЕКСТЫ
# ==========================================
def get_main_text(username: str) -> str:
    total_sum, _ = get_stats_for_period("all")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE approved = 1")
    workers_count = cursor.fetchone()[0]
    conn.close()
    
    return (
        f"🎯<b>Добро пожаловать, воркер @{username}!</b>\n\n"
        f"• <b>Выплачено всего:</b> <code>{total_sum:,.2f}$</code>\n"
        f"• <b>Работаем с 2025 года</b>\n"
        f"• <b>Воркеров в нашем боте:</b> <code>{workers_count}</code>\n\n"
        f"<blockquote>💬 <i>Выберите нужный раздел из меню ниже:</i> ⌄</blockquote>"
    )


def get_profile_text(user_id: int, username: str) -> str:
    profits_db = db_get_all_profits()
    user_profits = [p for p in profits_db if p["username"].lower() == username.lower()]
    now = datetime.now()
    day_sum = sum(p["amount"] for p in user_profits if p["date"].date() == now.date())
    month_sum = sum(p["amount"] for p in user_profits if p["date"] >= (now - timedelta(days=30)))
    total_sum = sum(p["amount"] for p in user_profits)
    count = len(user_profits)

    user_data = db_get_user(user_id)
    joined_date = user_data.get("joined_date", datetime.now()) if user_data else datetime.now()
    days_in_team = (datetime.now() - joined_date).days

    return (
        f"— ℹ️️<b>Информация о профиле:</b>\n\n"
        f" • <b>ID:</b> <code>{user_id}</code>\n"
        f"• <b>Имя: @{username}</b>\n"
        f"• <b>Профитов:</b> {count}\n\n"
        f" ⌄ <b>Информация о профитах:</b>\n"
        f"• <b>День:</b><code> ${day_sum:,.2f} </code>\n"
        f"• <b>Месяц:</b><code> ${month_sum:,.2f} </code>\n"
        f"• <b>Всего:</b><code> ${total_sum:,.2f} </code>\n\n"
        f"❗️› <b>Дополнительная информация:</b>\n"
        f"• <b>Место в топе: Не в топе</b>\n"
        f"• <b>В тиме: {days_in_team} д</b>"
    )


def get_top_text(period: str = "day") -> str:
    period_names = {"day": "НА СЕГОДНЯ", "week": "ЗА НЕДЕЛЮ", "month": "ЗА МЕСЯЦ", "all": "ЗА ВСЕ ВРЕМЯ"}
    top_list = get_top_workers(period)
    total_all, _ = get_stats_for_period("all")

    text = f"— 🏆 <b>Топ воркеров {period_names.get(period, '')}:</b>\n\n"
    if not top_list:
        text += "<i>Список пока пуст... Стань первым!</i>\n\n"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for idx, (uname, stats) in enumerate(top_list):
            icon = medals[idx] if idx < 3 else "🕴️"
            text += f"{icon} @{uname} ✕ {stats['sum']:,.0f}$ ✕ {stats['count']} профитов\n"
        text += "\n"

    text += f"— 💼 <b>Общая касса за все время: {total_all:,.0f}$</b>"
    return text


def get_cashdesk_text(period: str = "all") -> str:
    total_all, count_all = get_stats_for_period("all")
    period_sum, period_count = get_stats_for_period(period)
    period_titles = {"day": "За сегодня:", "week": "За неделю:", "month": "За месяц:", "all": "За все время:"}

    return (
        f"— 🎭<b>Касса команды</b>\n\n"
        f"<blockquote><b>📊 – За все время:  ❞</b></blockquote>\n\n"
        f"• <b>Сумма:</b> {total_all:,.0f}$\n"
        f"• <b>Количество профитов:</b> {count_all}\n\n"
        f"<blockquote><b>📊 – {period_titles.get(period, 'За выбранный период:')}  ❞</b></blockquote>\n\n"
        f"• <b>Сумма:</b> {period_sum:,.0f}$\n"
        f"• <b>Количество профитов:</b> {period_count}"
    )


def get_mentors_main_text() -> str:
    return (
        f"🎓<b>Всем привет, если кто новичок и ничего не понимает что и как делать, "
        f"то берите одного из наставников, они вас доведут до первого депозита меньше чем за 3 дня.</b>\n\n"
        f"<blockquote><i>🤝 @aIadin_work 15%  ❞\n"
        f"🤝 @qwertyygod 15%</i></blockquote>\n\n"
        f"‼️ <b>Пишите только одному наставнику, всем не спамьте</b> ‼️"
    )


def get_mentor_card_text(mentor_username: str) -> str:
    students, profits, total_sum = get_mentor_stats(mentor_username)
    data = MENTORS_DATA.get(mentor_username, {"percent": "15%", "description": "Профессиональный наставник"})

    return (
        f"🎓<b>Информация о Наставнике</b>\n\n"
        f"<b>Юзернейм:</b> @{mentor_username}\n"
        f"<b>Процент:</b> {data['percent']}\n\n"
        f"<blockquote><i>💎 Статистика:  ❞\n"
        f"• На обучении: {students} учеников\n"
        f"• Профитов: {profits}\n"
        f"• Сумма: ${total_sum:,.0f}</i></blockquote>\n\n"
        f"🤖 <b>Описание:</b>\n"
        f"<blockquote><i>{data['description']}  ❞</i></blockquote>"
    )


def get_my_mentor_text(mentor_username: str) -> str:
    students, profits, total_sum = get_mentor_stats(mentor_username)
    data = MENTORS_DATA.get(mentor_username, {"percent": "15%", "description": "Профессиональный наставник"})

    return (
        f"🎓<b>Ваш Наставник</b>\n\n"
        f"@{mentor_username} {data['percent']}\n\n"
        f"🤖<b>Описание:</b>\n"
        f"<blockquote><i>{data['description']}  ❞</i></blockquote>\n\n"
        f"<blockquote><i>💎 Статистика:  ❞\n"
        f"• Учеников: {students}\n"
        f"• Профитов получено: {profits}\n"
        f"• Сумма: ${total_sum:,.0f}</i></blockquote>"
    )


def get_item_text(item_key: str) -> str:
    item = MARKET_ITEMS.get(item_key, {})
    return (
        f" • <b>Название товара: {item.get('title')}</b>\n\n"
        f" • <b>Описание: {item.get('description')}</b>\n\n"
        f" • <b>Цена: {item.get('price')}$</b>"
    )


async def safe_edit_media(callback: CallbackQuery, photo_path: str, caption: str, reply_markup: InlineKeyboardMarkup):
    try:
        media = InputMediaPhoto(media=get_photo(photo_path), caption=caption, parse_mode=ParseMode.HTML)
        await callback.message.edit_media(media=media, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Ошибка при редактировании медиа: {e}")
        await callback.message.edit_text(text=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


dp = Dispatcher()


# ==========================================
# 🛑 1. СИСТЕМА ЗАЯВОК И СТАРТ
# ==========================================
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    raw_name = message.from_user.username or message.from_user.first_name
    username = html.escape(raw_name)

    user_data = db_get_user(user_id)
    if not user_data:
        db_save_user(user_id, message.from_user.username or "", False, datetime.now())
    else:
        db_save_user(user_id, message.from_user.username or "", user_data["approved"], user_data["joined_date"])

    if not is_approved(user_id):
        await message.answer("⏳ <b>Ваша заявка отправлена администраторам. Ожидайте подтверждения!</b>",
                             parse_mode=ParseMode.HTML)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ])

        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 <b>Новая заявка на доступ в бот!</b>\n\n"
                         f"👤 <b>Пользователь:</b> {message.from_user.full_name} (@{username})\n"
                         f"🆔 <b>ID:</b> <code>{user_id}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
                )
            except Exception:
                pass
        return

    try:
        await message.answer_photo(
            photo=get_photo(IMAGES["main_menu"]),
            caption=get_main_text(username),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(),
        )
    except Exception:
        await message.answer(text=get_main_text(username), parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())


@dp.callback_query(F.data.startswith("approve_"))
async def approve_user_cmd(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    user_id = int(callback.data.split("_")[1])
    db_update_approval(user_id, True)

    try:
        await callback.bot.send_message(user_id,
                                        "✅ <b>Ваша заявка одобрена! Напишите /start для входа в меню.</b>",
                                        parse_mode=ParseMode.HTML)
    except Exception:
        pass

    await callback.message.edit_text(f"✅ Пользователь <code>{user_id}</code> успешно подтвержден!",
                                   parse_mode=ParseMode.HTML)
    await callback.answer()


@dp.callback_query(F.data.startswith("reject_"))
async def reject_user_cmd(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    user_id = int(callback.data.split("_")[1])
    try:
        await callback.bot.send_message(user_id, "❌ <b>Ваша заявка на доступ была отклонена.</b>",
                                        parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.message.edit_text(f"❌ Заявка пользователя <code>{user_id}</code> отклонена.",
                                   parse_mode=ParseMode.HTML)
    await callback.answer()


# ==========================================
# 📊 2. ТЕКСТОВЫЙ ХЕНДЛЕР ИНФО (С ПОДДЕРЖКОЙ @username)
# ==========================================
@dp.message(F.text.lower().startswith("инфо") | F.text.lower().startswith("/info"))
async def text_info_cmd(message: Message):
    user_id = message.from_user.id
    if not is_approved(user_id):
        await message.answer("⛔ У вас нет доступа к боту. Дождитесь подтверждения заявки.")
        return

    args = message.text.split()

    if len(args) > 1:
        target_username = args[1].replace("@", "").strip()
        target_user_id = None
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username.lower(),))
        row = cursor.fetchone()
        conn.close()
        if row:
            target_user_id = row[0]
    else:
        target_username = message.from_user.username or message.from_user.first_name
        target_user_id = user_id

    clean_username = html.escape(target_username)

    profits_db = db_get_all_profits()
    user_profits = [p for p in profits_db if p["username"].lower() == target_username.lower()]
    total_sum = sum(p["amount"] for p in user_profits)
    count = len(user_profits)

    target_data = db_get_user(target_user_id) if target_user_id else None
    if target_data:
        user_id_text = f"<code>{target_user_id}</code>"
        joined_date = target_data.get("joined_date", datetime.now())
        days_in_team = (datetime.now() - joined_date).days
        days_text = f"{days_in_team} дн."
    else:
        user_id_text = "<i>Не найден</i>"
        days_text = "<i>Нет данных</i>"

    mentor = db_get_mentor(target_user_id) if target_user_id else None
    mentor_text = f"@{mentor}" if mentor else "Не выбран"

    text = (
        f"📊 <b>Информация о воркере @{clean_username}:</b>\n\n"
        f"🏴‍☠️ • <b>ID:</b> {user_id_text}\n"
        f"💰 <b>Профиты:</b> {count} шт. (${total_sum:,.2f})\n"
        f"🗓 <b>Дней в тиме:</b> {days_text}\n"
        f"👨‍🏫 <b>Наставник:</b> {mentor_text}"
    )

    await message.answer(text, parse_mode=ParseMode.HTML)


# ==========================================
# 👑 3. ВЫСТАВЛЕНИЕ ПРОФИТА
# ==========================================
@dp.message(Command("profit"))
async def add_profit_cmd(message: Message, command: CommandObject):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        return

    if not command.args:
        await message.answer("⚠️ <b>Использование:</b> <code>/profit @username 100 Болгария</code>",
                             parse_mode=ParseMode.HTML)
        return

    try:
        args = command.args.split()
        raw_user = args[0].replace("@", "")
        amount = float(args[1].replace("$", ""))
        country_name = " ".join(args[2:]) if len(args) > 2 else "Не указана"

        worker_share = amount * 0.75
        flag = COUNTRY_FLAGS.get(country_name.lower(), "🌐")
        country_with_flag = f"{country_name.capitalize()} {flag}"

        # Ищем наставника воркера в БД
        assigned_mentor = ""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT u.user_id, um.mentor_username FROM users u JOIN user_mentors um ON u.user_id = um.user_id WHERE LOWER(u.username) = ?", (raw_user.lower(),))
        row = cursor.fetchone()
        if row:
            assigned_mentor = row[1]
        conn.close()

        db_add_profit(raw_user, amount, country_name, assigned_mentor)

        bot_info = await message.bot.get_me()
        bot_username = bot_info.username

        caption = (
            f"<b>PAYS | SAINT LEGION 💰</b>\n\n"
            f"<b>- PROFIT / УСПЕШНАЯ ОПЕРАЦИЯ</b>\n\n"
            f"├ <b>Воркер:</b> @{raw_user}\n"
            f"├ <b>Сумма:</b> <code>{amount:,.0f}$</code>\n"
            f"├ <b>Доля воркера:</b> <code>{worker_share:,.2f}$</code>\n"
            f"└ <b>Страна:</b> {country_with_flag}\n\n"
            f"🏛 <b>Проект:</b>\n"
            f"@{bot_username}"
        )

        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🤖", url=f"https://t.me/{bot_username}")]]
        )

        try:
            await message.answer_photo(
                photo=get_photo(IMAGES["profit_post"]),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=inline_kb
            )
        except TelegramBadRequest:
            await message.answer(text=caption, parse_mode=ParseMode.HTML, reply_markup=inline_kb)

        if PROFIT_CHANNEL_ID:
            try:
                await message.bot.send_photo(
                    chat_id=PROFIT_CHANNEL_ID,
                    photo=get_photo(IMAGES["profit_post"]),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=inline_kb
                )
            except Exception as e:
                await message.answer(f"⚠️ <b>Профит создан, но не отправлен в канал!</b> Ошибка: <code>{e}</code>",
                                     parse_mode=ParseMode.HTML)

    except Exception:
        await message.answer("❌ <b>Ошибка ввода!</b> Пример: <code>/profit @username 100 Болгария</code>",
                             parse_mode=ParseMode.HTML)


# ==========================================
# 🔘 4. КНОПКИ И МЕНЮ
# ==========================================
@dp.message(Command("me"))
async def me_cmd(message: Message):
    if not is_approved(message.from_user.id): return
    raw_name = message.from_user.username or message.from_user.first_name
    username = html.escape(raw_name)
    text = get_profile_text(message.from_user.id, username)
    try:
        await message.answer_photo(photo=get_photo(IMAGES["profile"]), caption=text, parse_mode=ParseMode.HTML,
                                   reply_markup=get_back_keyboard())
    except Exception:
        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())


@dp.message(Command("top"))
async def top_cmd(message: Message):
    if not is_approved(message.from_user.id): return
    text = get_top_text("day")
    try:
        await message.answer_photo(photo=get_photo(IMAGES["top"]), caption=text, parse_mode=ParseMode.HTML,
                                   reply_markup=get_top_keyboard("day"))
    except Exception:
        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=get_top_keyboard("day"))


@dp.message(Command("kassa"))
async def kassa_cmd(message: Message):
    if not is_approved(message.from_user.id): return
    text = get_cashdesk_text("all")
    try:
        await message.answer_photo(photo=get_photo(IMAGES["cashdesk"]), caption=text, parse_mode=ParseMode.HTML,
                                   reply_markup=get_cashdesk_keyboard("all"))
    except Exception:
        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=get_cashdesk_keyboard("all"))


@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    raw_name = callback.from_user.username or callback.from_user.first_name
    username = html.escape(raw_name)
    await safe_edit_media(callback, IMAGES["main_menu"], get_main_text(username), get_main_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    raw_name = callback.from_user.username or callback.from_user.first_name
    username = html.escape(raw_name)
    text = get_profile_text(callback.from_user.id, username)
    await safe_edit_media(callback, IMAGES["profile"], text, get_back_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("top_"))
async def top_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    period = callback.data.split("_")[1]
    await safe_edit_media(callback, IMAGES["top"], get_top_text(period), get_top_keyboard(period))
    await callback.answer()


@dp.callback_query(F.data.startswith("cash_") | (F.data == "cashdesk_all"))
async def cashdesk_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    period = "all" if callback.data == "cashdesk_all" else callback.data.split("_")[1]
    await safe_edit_media(callback, IMAGES["cashdesk"], get_cashdesk_text(period), get_cashdesk_keyboard(period))
    await callback.answer()


@dp.callback_query(F.data == "mentors")
async def mentors_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    user_id = callback.from_user.id
    mentor_name = db_get_mentor(user_id)
    if mentor_name:
        text = get_my_mentor_text(mentor_name)
        await safe_edit_media(callback, IMAGES["mentors"], text, get_back_keyboard())
    else:
        text = get_mentors_main_text()
        await safe_edit_media(callback, IMAGES["mentors"], text, get_mentors_list_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("mentor_view_"))
async def mentor_view_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    mentor_username = callback.data.replace("mentor_view_", "")
    text = get_mentor_card_text(mentor_username)
    await safe_edit_media(callback, IMAGES["mentors"], text, get_mentor_card_keyboard(mentor_username))
    await callback.answer()


@dp.callback_query(F.data.startswith("mentor_select_"))
async def mentor_select_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    mentor_username = callback.data.replace("mentor_select_", "")
    user_id = callback.from_user.id
    db_set_mentor(user_id, mentor_username)
    text = f"✅ <b>Вы успешно закреплены за @{mentor_username}!</b>"
    await safe_edit_media(callback, IMAGES["mentors"], text, get_back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "info_menu")
async def info_menu_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    info_text = (
        f"— ️ <b>Информация по боту</b>\n\n"
        f" <b>✅Доступные команды:</b>\n"
        f"<blockquote><i> • /start - Главное меню\n\n"
        f" • /me - Ваш профиль\n\n"
        f" • /top - Топ воркеров\n\n"
        f" • /kassa - Касса команды\n\n"
        f" • /info (ID) - Информация о пользователе</i></blockquote>\n\n\n"
        f" <b>Разделы бота:\n\n"
        f" • Профиль - Ваша статистика и информация\n"
        f" • Топ воркеров - Рейтинг за все время и за день\n"
        f" • Касса - Общая статистика команды\n\n</b>"
        f"<i>По вопросам обращайтесь к администрации.</i>"
    )
    await safe_edit_media(callback, IMAGES["info"], info_text, get_info_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "manuals")
async def manuals_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    await safe_edit_media(callback, IMAGES["manuals"], "<b>Мануалы по странам 👇</b>", get_manuals_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "market")
async def market_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    caption = "🏆 <b>Все для уверенного и стабильного вора:</b>"
    await safe_edit_media(callback, IMAGES["market"], caption, get_market_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("item_"))
async def item_handler(callback: CallbackQuery):
    if not is_approved(callback.from_user.id): return
    item_key = callback.data.replace("item_", "")
    text = get_item_text(item_key)
    await safe_edit_media(callback, IMAGES["market"], text, get_item_keyboard())
    await callback.answer()


# ==========================================
# 🚀 5. ЗАПУСК БОТА
# ==========================================
async def main():
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("--- Бот успешно запущен! ---")
        await dp.start_polling(bot)
    except TelegramNetworkError as e:
        print(f"⚠️ Сетевой сбой: {e}. Перезапуск через 3 секунды...")
        await asyncio.sleep(3)
        await main()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
