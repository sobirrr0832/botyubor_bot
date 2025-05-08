import logging
import sqlite3
import datetime
import os
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiocron
import asyncio
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env faylidan ma'lumotlarni yuklash
load_dotenv()

# Bot tokeni
API_TOKEN = os.getenv('BOT_TOKEN')

# Admin IDlarini yuklash
ADMIN_IDS = [int(admin_id) for admin_id in os.getenv('ADMIN_IDS', '').split(',') if admin_id]

# Data papkasini tekshirish va yaratish
data_dir = 'data'
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Ma'lumotlar bazasini ishga tushirish
db_path = os.path.join(data_dir, 'telegram_bot.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Jadvallarni yaratish
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    joined_date TIMESTAMP,
    last_activity TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS scheduled_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT,
    target_id TEXT,
    message_text TEXT,
    interval_minutes INTEGER DEFAULT NULL,
    specific_time TEXT DEFAULT NULL,
    specific_days TEXT DEFAULT NULL,
    last_sent TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users (user_id)
)
''')

conn.commit()

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(data_dir, 'bot.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Bot va dispatcher yaratish
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# State klasslarini yaratish
class NewMessage(StatesGroup):
    target_type = State()
    target_id = State()
    message_text = State()
    schedule_type = State()
    interval = State()
    specific_time = State()
    specific_days = State()

# Klaviaturalar
def get_main_keyboard(is_admin=False):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📤 Xabar yuborish"))
    keyboard.row(KeyboardButton("⏰ Rejalashtirish"))
    keyboard.row(KeyboardButton("🚫 Rejalarni bekor qilish"))
    
    if is_admin:
        keyboard.row(KeyboardButton("👨‍💼 Admin panel"))
    
    return keyboard

def get_target_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("👤 Foydalanuvchiga"))
    keyboard.row(KeyboardButton("👥 Guruhga"))
    keyboard.row(KeyboardButton("📢 Kanalga"))
    keyboard.row(KeyboardButton("🔙 Orqaga"))
    return keyboard

def get_schedule_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("⏱ Har X daqiqada"))
    keyboard.row(KeyboardButton("🕒 Aniq vaqtda"))
    keyboard.row(KeyboardButton("📅 Hafta kunlarida"))
    keyboard.row(KeyboardButton("🔙 Orqaga"))
    return keyboard

def get_days_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)
    days = {
        "monday": "Dushanba",
        "tuesday": "Seshanba",
        "wednesday": "Chorshanba",
        "thursday": "Payshanba",
        "friday": "Juma",
        "saturday": "Shanba",
        "sunday": "Yakshanba"
    }
    
    buttons = []
    for day_key, day_name in days.items():
        buttons.append(InlineKeyboardButton(
            text=day_name,
            callback_data=f"day_{day_key}"
        ))
    
    for i in range(0, len(buttons), 3):
        keyboard.row(*buttons[i:i+3])
    
    keyboard.row(InlineKeyboardButton("✅ Tayyor", callback_data="days_done"))
    
    return keyboard

def get_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("❌ Bekor qilish"))
    return keyboard

def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("👥 Foydalanuvchilar statistikasi"))
    keyboard.row(KeyboardButton("📊 Faollik statistikasi"))
    keyboard.row(KeyboardButton("📝 Rejalashtirilgan xabarlar"))
    keyboard.row(KeyboardButton("🔙 Orqaga"))
    return keyboard

# Foydalanuvchini saqlash
async def register_user(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    now = datetime.now()
    
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, joined_date, last_activity) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, first_name, last_name, now, now)
    )
    
    cursor.execute(
        "UPDATE users SET last_activity = ? WHERE user_id = ?",
        (now, user_id)
    )
    
    conn.commit()

# Xabar yuborish funksiyasi
async def send_message_to_target(target_type, target_id, message_text):
    try:
        # Premium emojilarni to'g'ri ko'rsatish uchun parse_mode=None
        if target_type == "user":
            await bot.send_message(chat_id=target_id, text=message_text)
        elif target_type == "group":
            await bot.send_message(chat_id=target_id, text=message_text)
        elif target_type == "channel":
            await bot.send_message(chat_id=target_id, text=message_text)
        return True
    except Exception as e:
        logging.error(f"Xabar yuborishda xatolik: {e}")
        return False

# Rejalashtirilgan xabarlarni tekshirish va yuborish
async def check_scheduled_messages():
    now = datetime.now()
    cursor.execute("SELECT * FROM scheduled_messages WHERE is_active = 1")
    scheduled = cursor.fetchall()
    
    for msg in scheduled:
        msg_id, target_type, target_id, message_text, interval_minutes, specific_time, specific_days, last_sent, is_active, created_by = msg
        
        should_send = False
        
        # Interval bo'yicha tekshirish
        if interval_minutes:
            if last_sent is None or now - datetime.fromisoformat(last_sent) > timedelta(minutes=interval_minutes):
                should_send = True
        
        # Aniq vaqt bo'yicha tekshirish
        if specific_time:
            current_time = now.strftime("%H:%M")
            if current_time == specific_time and (last_sent is None or datetime.fromisoformat(last_sent).date() < now.date()):
                should_send = True
        
        # Hafta kunlari bo'yicha tekshirish
        if specific_days:
            days = specific_days.split(',')
            current_day = now.strftime("%A").lower()
            current_time = now.strftime("%H:%M")
            
            if current_day in days and current_time == "09:00":  # 09:00 da yuborish
                if last_sent is None or datetime.fromisoformat(last_sent).date() < now.date():
                    should_send = True
        
        if should_send:
            success = await send_message_to_target(target_type, target_id, message_text)
            if success:
                cursor.execute(
                    "UPDATE scheduled_messages SET last_sent = ? WHERE id = ?",
                    (now.isoformat(), msg_id)
                )
                conn.commit()

# Xabar yuborish va rejalashtirish funksiyalari uchun cron task
@aiocron.crontab('* * * * *')  # Har daqiqada tekshirish
async def scheduled_check():
    await check_scheduled_messages()

# Start buyrug'i
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await register_user(message)
    
    is_admin = message.from_user.id in ADMIN_IDS
    keyboard = get_main_keyboard(is_admin)
    
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}! 📱\n\n"
        f"Men avtomatik xabar yuboruvchi botman. Menga xabar va vaqt belgilang, men belgilangan vaqtda xabarlaringizni yuboraman.",
        reply_markup=keyboard
    )

# Admin panel
@dp.message_handler(lambda message: message.text == "👨‍💼 Admin panel" and message.from_user.id in ADMIN_IDS)
async def admin_panel(message: types.Message):
    await message.answer("Admin panel:", reply_markup=get_admin_keyboard())

# Foydalanuvchilar statistikasi
@dp.message_handler(lambda message: message.text == "👥 Foydalanuvchilar statistikasi" and message.from_user.id in ADMIN_IDS)
async def users_statistics(message: types.Message):
    # Jami foydalanuvchilar
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    # Faol foydalanuvchilar (so'nggi 7 kun ichida)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_activity > ?", (week_ago,))
    active_users = cursor.fetchone()[0]
    
    # Bugungi yangi foydalanuvchilar
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM users WHERE date(joined_date) = ?", (today,))
    new_users_today = cursor.fetchone()[0]
    
    # So'nggi hafta yangi foydalanuvchilar
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date > ?", (week_ago,))
    new_users_week = cursor.fetchone()[0]
    
    await message.answer(
        f"📊 <b>Foydalanuvchilar statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🟢 Faol foydalanuvchilar: <b>{active_users}</b>\n"
        f"🆕 Bugun yangi: <b>{new_users_today}</b>\n"
        f"📅 Haftalik yangi: <b>{new_users_week}</b>",
        parse_mode="HTML"
    )

# Faollik statistikasi
@dp.message_handler(lambda message: message.text == "📊 Faollik statistikasi" and message.from_user.id in ADMIN_IDS)
async def activity_statistics(message: types.Message):
    # Bugun faol foydalanuvchilar
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM users WHERE date(last_activity) = ?", (today,))
    active_today = cursor.fetchone()[0]
    
    # Kecha faol foydalanuvchilar
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM users WHERE date(last_activity) = ?", (yesterday,))
    active_yesterday = cursor.fetchone()[0]
    
    # Haftalik faollik
    week_data = []
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        day_name = (datetime.now() - timedelta(days=i)).strftime('%A')
        cursor.execute("SELECT COUNT(*) FROM users WHERE date(last_activity) = ?", (day,))
        count = cursor.fetchone()[0]
        week_data.append((day_name, count))
    
    week_stats = "\n".join([f"- {day}: {count}" for day, count in week_data])
    
    await message.answer(
        f"📈 <b>Faollik statistikasi</b>\n\n"
        f"🟢 Bugun faol: <b>{active_today}</b>\n"
        f"🔵 Kecha faol: <b>{active_yesterday}</b>\n\n"
        f"<b>Haftalik faollik:</b>\n{week_stats}",
        parse_mode="HTML"
    )

# Rejalashtirilgan xabarlar ro'yxati
@dp.message_handler(lambda message: message.text == "📝 Rejalashtirilgan xabarlar" and message.from_user.id in ADMIN_IDS)
async def scheduled_messages_list(message: types.Message):
    cursor.execute("SELECT * FROM scheduled_messages WHERE is_active = 1")
    messages = cursor.fetchall()
    
    if not messages:
        await message.answer("❌ Rejalashtirilgan xabarlar yo'q")
        return
    
    response = "📋 <b>Rejalashtirilgan xabarlar:</b>\n\n"
    
    for msg in messages:
        msg_id, target_type, target_id, message_text, interval_minutes, specific_time, specific_days, last_sent, is_active, created_by = msg
        
        schedule_info = ""
        if interval_minutes:
            schedule_info = f"Har {interval_minutes} daqiqada"
        elif specific_time:
            schedule_info = f"Har kuni {specific_time} da"
        elif specific_days:
            days_list = specific_days.split(',')
            days_names = {
                "monday": "Dushanba", 
                "tuesday": "Seshanba", 
                "wednesday": "Chorshanba",
                "thursday": "Payshanba", 
                "friday": "Juma", 
                "saturday": "Shanba", 
                "sunday": "Yakshanba"
            }
            days_readable = [days_names.get(day, day) for day in days_list]
            schedule_info = f"{', '.join(days_readable)} kunlari 09:00 da"
        
        last_sent_info = "Yuborilmagan" if not last_sent else f"So'nggi: {datetime.fromisoformat(last_sent).strftime('%d.%m.%Y %H:%M')}"
        
        target_info = f"@{target_id}" if target_id.startswith('@') else target_id
        
        response += (
            f"<b>ID:</b> {msg_id}\n"
            f"<b>Manzil:</b> {target_type} ({target_info})\n"
            f"<b>Xabar:</b> {message_text[:50]}...\n"
            f"<b>Rejim:</b> {schedule_info}\n"
            f"<b>{last_sent_info}</b>\n\n"
        )
    
    # Xabarni o'chirish tugmalarini qo'shish
    keyboard = InlineKeyboardMarkup(row_width=2)
    for msg in messages:
        msg_id = msg[0]
        keyboard.add(InlineKeyboardButton(
            text=f"❌ #{msg_id} ni o'chirish",
            callback_data=f"delete_msg_{msg_id}"
        ))
    
    await message.answer(response, reply_markup=keyboard, parse_mode="HTML")

# Xabarni o'chirish
@dp.callback_query_handler(lambda c: c.data.startswith('delete_msg_'))
async def delete_scheduled_message(callback_query: types.CallbackQuery):
    msg_id = int(callback_query.data.split('_')[2])
    
    cursor.execute("UPDATE scheduled_messages SET is_active = 0 WHERE id = ?", (msg_id,))
    conn.commit()
    
    await callback_query.answer("Xabar o'chirildi!")
    await callback_query.message.edit_text(
        callback_query.message.text + "\n\n<b>✅ #" + str(msg_id) + " o'chirildi!</b>",
        parse_mode="HTML"
    )

# Orqaga qaytish
@dp.message_handler(lambda message: message.text == "🔙 Orqaga")
async def go_back(message: types.Message):
    is_admin = message.from_user.id in ADMIN_IDS
    keyboard = get_main_keyboard(is_admin)
    
    await message.answer("Asosiy menyu:", reply_markup=keyboard)

# Xabar yuborish
@dp.message_handler(lambda message: message.text == "📤 Xabar yuborish")
async def send_message_start(message: types.Message):
    await NewMessage.target_type.set()
    await message.answer("Xabar kimga yuborilsin?", reply_markup=get_target_keyboard())

# Rejalashtirish
@dp.message_handler(lambda message: message.text == "⏰ Rejalashtirish")
async def schedule_message_start(message: types.Message):
    await NewMessage.target_type.set()
    await message.answer("Rejalashtirilgan xabar kimga yuborilsin?", reply_markup=get_target_keyboard())

# Target type tanlash
@dp.message_handler(state=NewMessage.target_type)
async def process_target_type(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))
        return
    
    target_types = {
        "👤 Foydalanuvchiga": "user",
        "👥 Guruhga": "group",
        "📢 Kanalga": "channel"
    }
    
    if message.text not in target_types:
        await message.answer("Iltimos, quyidagi variantlardan birini tanlang.", reply_markup=get_target_keyboard())
        return
    
    target_type = target_types[message.text]
    
    await state.update_data(target_type=target_type)
    await NewMessage.target_id.set()
    
    if target_type == "user":
        await message.answer(
            "Foydalanuvchining username yoki ID raqamini kiriting.\n"
            "Masalan: @username yoki 123456789",
            reply_markup=get_cancel_keyboard()
        )
    elif target_type == "group":
        await message.answer(
            "Guruhning username yoki ID raqamini kiriting.\n"
            "Masalan: @guruh_nomi yoki -1001234567890",
            reply_markup=get_cancel_keyboard()
        )
    elif target_type == "channel":
        await message.answer(
            "Kanalning username yoki ID raqamini kiriting.\n"
            "Masalan: @kanal_nomi yoki -1001234567890",
            reply_markup=get_cancel_keyboard()
        )

# Target ID ni olish
@dp.message_handler(state=NewMessage.target_id)
async def process_target_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    
    target_id = message.text
    
    # @ belgisi bilan boshlansa, qo'shimcha tekshirish
    if target_id.startswith('@'):
        # To'g'ri format: faqat harf, raqamlar va "_" belgisi, uzunligi 5-32
        if not re.match(r'^@[a-zA-Z0-9_]{5,32}$', target_id):
            await message.answer(
                "Noto'g'ri username formati. Iltimos, qayta kiriting.\n"
                "Masalan: @username",
                reply_markup=get_cancel_keyboard()
            )
            return
    # Agar raqam bo'lsa
    elif target_id.startswith('-100'):
        if not target_id[4:].isdigit():
            await message.answer(
                "Noto'g'ri ID formati. Iltimos, qayta kiriting.\n"
                "Masalan: -1001234567890",
                reply_markup=get_cancel_keyboard()
            )
            return
    # Agar oddiy raqam bo'lsa (foydalanuvchi ID)
    elif not target_id.isdigit():
        await message.answer(
            "Noto'g'ri format. Iltimos, qayta kiriting.\n"
            "Username: @username\n"
            "ID: 123456789 yoki -1001234567890",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(target_id=target_id)
    await NewMessage.message_text.set()
    
    await message.answer(
        "Yubormoqchi bo'lgan xabaringizni kiriting.\n"
        "Premium emojilarni ham ishlatishingiz mumkin.",
        reply_markup=get_cancel_keyboard()
    )

# Xabar matnini olish
@dp.message_handler(state=NewMessage.message_text)
async def process_message_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    
    message_text = message.text
    await state.update_data(message_text=message_text)
    
    # Oldingi holatdan ma'lumotlarni olish
    data = await state.get_data()
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    
    # Ko'rsatish uchun
    target_types = {
        "user": "Foydalanuvchi",
        "group": "Guruh",
        "channel": "Kanal"
    }
    
    await message.answer(
        f"<b>Ma'lumotlar:</b>\n\n"
        f"<b>Manzil:</b> {target_types[target_type]} ({target_id})\n"
        f"<b>Xabar:</b>\n\n{message_text}\n\n"
        f"Xabarni rejalashtirish kerakmi?",
        parse_mode="HTML",
        reply_markup=get_schedule_keyboard()
    )
    
    await NewMessage.schedule_type.set()

# Rejalashtirish turini tanlash
@dp.message_handler(state=NewMessage.schedule_type)
async def process_schedule_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish" or message.text == "🔙 Orqaga":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    
    data = await state.get_data()
    
    # Hozir yuborish uchun
    if message.text not in ["⏱ Har X daqiqada", "🕒 Aniq vaqtda", "📅 Hafta kunlarida"]:
        # Xabarni hozir yuborish
        target_type = data.get('target_type')
        target_id = data.get('target_id')
        message_text = data.get('message_text')
        
        success = await send_message_to_target(target_type, target_id, message_text)
        
        if success:
            await message.answer("✅ Xabar muvaffaqiyatli yuborildi!", reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS))
        else:
            await message.answer("❌ Xabar yuborishda xatolik yuz berdi. Manzilni tekshiring.", reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS))
        
        await state.finish()
        return
    
    # Rejalashtirish uchun
    schedule_type = message.text
    
    if schedule_type == "⏱ Har X daqiqada":
        await state.update_data(schedule_type="interval")
        await NewMessage.interval.set()
        await message.answer(
            ""Necha daqiqada bir xabar yuborilsin?\n"
            "Raqam kiriting (masalan: 30, 60, 120...)",
            reply_markup=get_cancel_keyboard()
        )
    elif schedule_type == "🕒 Aniq vaqtda":
        await state.update_data(schedule_type="specific_time")
        await NewMessage.specific_time.set()
        await message.answer(
            "Har kuni qaysi vaqtda xabar yuborilsin?\n"
            "Vaqtni HH:MM formatida kiriting (masalan: 09:00, 18:30)",
            reply_markup=get_cancel_keyboard()
        )
    elif schedule_type == "📅 Hafta kunlarida":
        await state.update_data(schedule_type="specific_days")
        await state.update_data(selected_days=[])
        await NewMessage.specific_days.set()
        await message.answer(
            "Qaysi kunlari xabar yuborilsin?\n"
            "Kunlarni tanlang:",
            reply_markup=get_days_keyboard()
        )

# Interval ni olish
@dp.message_handler(state=NewMessage.interval)
async def process_interval(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    
    try:
        interval = int(message.text)
        if interval < 1:
            raise ValueError("Interval must be positive")
    except ValueError:
        await message.answer(
            "Iltimos, musbat raqam kiriting.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(interval=interval)
    
    # Xabarni rejalashtirish
    data = await state.get_data()
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    message_text = data.get('message_text')
    
    cursor.execute(
        "INSERT INTO scheduled_messages (target_type, target_id, message_text, interval_minutes, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (target_type, target_id, message_text, interval, message.from_user.id)
    )
    conn.commit()
    
    await message.answer(
        f"✅ Xabar rejalashtirildi!\n"
        f"Har {interval} daqiqada yuboriladi.",
        reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
    )
    
    await state.finish()

# Aniq vaqt olish
@dp.message_handler(state=NewMessage.specific_time)
async def process_specific_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    
    # Vaqt formatini tekshirish (HH:MM)
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', message.text):
        await message.answer(
            "Noto'g'ri vaqt formati. Iltimos, HH:MM formatida kiriting.\n"
            "Masalan: 09:00, 18:30",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    specific_time = message.text
    await state.update_data(specific_time=specific_time)
    
    # Xabarni rejalashtirish
    data = await state.get_data()
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    message_text = data.get('message_text')
    
    cursor.execute(
        "INSERT INTO scheduled_messages (target_type, target_id, message_text, specific_time, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (target_type, target_id, message_text, specific_time, message.from_user.id)
    )
    conn.commit()
    
    await message.answer(
        f"✅ Xabar rejalashtirildi!\n"
        f"Har kuni {specific_time} da yuboriladi.",
        reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
    )
    
    await state.finish()

# Hafta kunlari tanlash
@dp.callback_query_handler(lambda c: c.data.startswith('day_'), state=NewMessage.specific_days)
async def process_day_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    day = callback_query.data.split('_')[1]
    data = await state.get_data()
    selected_days = data.get('selected_days', [])
    
    if day in selected_days:
        selected_days.remove(day)
    else:
        selected_days.append(day)
    
    await state.update_data(selected_days=selected_days)
    
    days_names = {
        "monday": "Dushanba", 
        "tuesday": "Seshanba", 
        "wednesday": "Chorshanba",
        "thursday": "Payshanba", 
        "friday": "Juma", 
        "saturday": "Shanba", 
        "sunday": "Yakshanba"
    }
    
    days_text = ", ".join([days_names.get(d, d) for d in selected_days])
    
    if selected_days:
        await callback_query.message.edit_text(
            f"Tanlangan kunlar: {days_text}\n\n"
            f"Davom etish uchun \"✅ Tayyor\" tugmasini bosing.",
            reply_markup=get_days_keyboard()
        )
    else:
        await callback_query.message.edit_text(
            f"Hech qanday kun tanlanmadi.\n"
            f"Iltimos, kamida bitta kunni tanlang:",
            reply_markup=get_days_keyboard()
        )

# Kunlar tanlash tugallandi
@dp.callback_query_handler(lambda c: c.data == 'days_done', state=NewMessage.specific_days)
async def process_days_done(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_days = data.get('selected_days', [])
    
    if not selected_days:
        await callback_query.answer("Iltimos, kamida bitta kunni tanlang!")
        return
    
    await callback_query.answer()
    
    # Xabarni rejalashtirish
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    message_text = data.get('message_text')
    specific_days = ','.join(selected_days)
    
    cursor.execute(
        "INSERT INTO scheduled_messages (target_type, target_id, message_text, specific_days, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (target_type, target_id, message_text, specific_days, callback_query.from_user.id)
    )
    conn.commit()
    
    days_names = {
        "monday": "Dushanba", 
        "tuesday": "Seshanba", 
        "wednesday": "Chorshanba",
        "thursday": "Payshanba", 
        "friday": "Juma", 
        "saturday": "Shanba", 
        "sunday": "Yakshanba"
    }
    
    days_text = ", ".join([days_names.get(d, d) for d in selected_days])
    
    is_admin = callback_query.from_user.id in ADMIN_IDS
    
    await callback_query.message.edit_text(
        f"✅ Xabar rejalashtirildi!\n"
        f"Yuborish kunlari: {days_text}\n"
        f"Vaqt: 09:00"
    )
    
    await callback_query.message.answer(
        "Asosiy menyu:",
        reply_markup=get_main_keyboard(is_admin)
    )
    
    await state.finish()

# Rejalashtirilgan xabarlarni bekor qilish
@dp.message_handler(lambda message: message.text == "🚫 Rejalarni bekor qilish")
async def cancel_scheduled_messages(message: types.Message):
    user_id = message.from_user.id
    
    cursor.execute(
        "SELECT id, target_type, target_id, message_text FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
        (user_id,)
    )
    messages = cursor.fetchall()
    
    if not messages:
        await message.answer("❌ Sizda rejalashtirilgan xabarlar yo'q.")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for msg_id, target_type, target_id, message_text in messages:
        keyboard.add(InlineKeyboardButton(
            text=f"❌ {target_type} ({target_id}): {message_text[:30]}...",
            callback_data=f"cancel_msg_{msg_id}"
        ))
    
    await message.answer("Bekor qilmoqchi bo'lgan xabarni tanlang:", reply_markup=keyboard)

# Rejalashtirilgan xabarni bekor qilish
@dp.callback_query_handler(lambda c: c.data.startswith('cancel_msg_'))
async def cancel_specific_message(callback_query: types.CallbackQuery):
    msg_id = int(callback_query.data.split('_')[2])
    
    cursor.execute("UPDATE scheduled_messages SET is_active = 0 WHERE id = ?", (msg_id,))
    conn.commit()
    
    await callback_query.answer("Xabar bekor qilindi!")
    await callback_query.message.edit_text(
        callback_query.message.text + "\n\n✅ Xabar bekor qilindi!"
    )

# Text xabarlarni qayta ishlash
@dp.message_handler()
async def process_regular_messages(message: types.Message):
    await register_user(message)
    
    # Agar xabar oddiy bo'lsa, start buyrug'ini yuborish
    is_admin = message.from_user.id in ADMIN_IDS
    keyboard = get_main_keyboard(is_admin)
    
    await message.answer(
        "Iltimos, quyidagi menyudan foydalaning:",
        reply_markup=keyboard
    )

if __name__ == '__main__':
    # Cron task larni ishga tushirish
    loop = asyncio.get_event_loop()
    aiocron.crontab('* * * * *', func=scheduled_check, start=True, loop=loop)
    
    # Botni ishga tushirish
    executor.start_polling(dp, skip_updates=True)
