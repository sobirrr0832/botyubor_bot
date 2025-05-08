import logging
import sqlite3
import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiocron
import asyncio
import re
from datetime import datetime, timedelta

# Bot tokeni
API_TOKEN = 'time_str = message.text
time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
    
if not time_pattern.match(time_str):
    await message.answer(
        "Noto'g'ri vaqt formati. HH:MM formatida kiriting.\n"
        "Masalan: 09:00 yoki 18:30",
        reply_markup=get_cancel_keyboard()
    )
    return
    
await state.update_data(specific_time=time_str)
    
# Ma'lumotlarni olish
data = await state.get_data()
target_type = data.get('target_type')
target_id = data.get('target_id')
message_text = data.get('message_text')
    
# Bazaga saqlash
now = datetime.now()
cursor.execute(
    "INSERT INTO scheduled_messages (target_type, target_id, message_text, specific_time, created_by, is_active) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (target_type, target_id, message_text, time_str, message.from_user.id, True)
)
conn.commit()
    
await message.answer(
    f"✅ Xabar rejalashtirildi!\n\n"
    f"Har kuni {time_str} da yuboriladi.",
    reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
)
    
await state.finish()

# Hafta kunlari bo'yicha yuborish
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
    
    selected_names = [days_names[d] for d in selected_days]
    
    await callback_query.message.edit_text(
        f"Tanlangan kunlar: {', '.join(selected_names) if selected_names else 'Tanlanmagan'}\n\n"
        f"Tanlashni davom ettiring yoki \"Tayyor\" tugmasini bosing.",
        reply_markup=get_days_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "days_done", state=NewMessage.specific_days)
async def process_days_done(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_days = data.get('selected_days', [])
    
    if not selected_days:
        await callback_query.answer("Kamida bitta kunni tanlang!")
        return
    
    await callback_query.answer("Kunlar saqlandi!")
    
    # Ma'lumotlarni olish
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    message_text = data.get('message_text')
    days_str = ','.join(selected_days)
    
    # Bazaga saqlash
    now = datetime.now()
    cursor.execute(
        "INSERT INTO scheduled_messages (target_type, target_id, message_text, specific_days, created_by, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (target_type, target_id, message_text, days_str, callback_query.from_user.id, True)
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
    
    selected_names = [days_names[d] for d in selected_days]
    
    await callback_query.message.edit_text(
        f"✅ Xabar rejalashtirildi!\n\n"
        f"Har hafta {', '.join(selected_names)} kunlari soat 09:00 da yuboriladi."
    )
    
    is_admin = callback_query.from_user.id in ADMIN_IDS
    await callback_query.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))
    
    await state.finish()

# Rejalarni bekor qilish
@dp.message_handler(lambda message: message.text == "🚫 Rejalarni bekor qilish")
async def cancel_scheduled_messages(message: types.Message):
    user_id = message.from_user.id
    
    # Foydalanuvchining rejalashtirilgan xabarlarini olish
    cursor.execute(
        "SELECT * FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
        (user_id,)
    )
    messages = cursor.fetchall()
    
    if not messages:
        await message.answer("❌ Sizning rejalashtirilgan xabarlaringiz yo'q")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
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
            schedule_info = f"{', '.join(days_readable)} kunlari"
        
        target_info = f"@{target_id}" if target_id.startswith('@') else target_id
        
        button_text = f"❌ #{msg_id}: {target_info} ({schedule_info})"
        keyboard.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"cancel_msg_{msg_id}"
        ))
    
    await message.answer(
        "🚫 Bekor qilmoqchi bo'lgan xabarni tanlang:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('cancel_msg_'))
async def process_cancel_message(callback_query: types.CallbackQuery):
    msg_id = int(callback_query.data.split('_')[2])
    
    cursor.execute(
        "UPDATE scheduled_messages SET is_active = 0 WHERE id = ? AND created_by = ?",
        (msg_id, callback_query.from_user.id)
    )
    conn.commit()
    
    await callback_query.answer(f"#{msg_id} bekor qilindi!")
    
    # Qolgan xabarlarni tekshirish
    cursor.execute(
        "SELECT COUNT(*) FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
        (callback_query.from_user.id,)
    )
    count = cursor.fetchone()[0]
    
    if count > 0:
        # Buttonlarni yangilash
        cursor.execute(
            "SELECT * FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
            (callback_query.from_user.id,)
        )
        messages = cursor.fetchall()
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        
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
                schedule_info = f"{', '.join(days_readable)} kunlari"
            
            target_info = f"@{target_id}" if target_id.startswith('@') else target_id
            
            button_text = f"❌ #{msg_id}: {target_info} ({schedule_info})"
            keyboard.add(InlineKeyboardButton(
                text=button_text,
                callback_data=f"cancel_msg_{msg_id}"
            ))
        
        await callback_query.message.edit_text(
            "🚫 Bekor qilmoqchi bo'lgan xabarni tanlang:",
            reply_markup=keyboard
        )
    else:
        is_admin = callback_query.from_user.id in ADMIN_IDS
        await callback_query.message.edit_text("✅ Barcha rejalashtirilgan xabarlar bekor qilindi.")
        await callback_query.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))

# Foydalanuvchi faolligini kuzatish
@dp.message_handler()
async def track_user_activity(message: types.Message):
    await register_user(message)
    
    # Asosiy menyuga qaytish
    if message.text == "/menu":
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))
    else:
        # Boshqa buyruqlar uchun
        await message.answer(
            "🤔 Nima qilishni xohlaysiz?\n\n"
            "Asosiy menyuga qaytish uchun /menu buyrug'ini yuboring.",
            reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
        )

if __name__ == '__main__':
    # Scheduled taskni ishga tushirish
    loop = asyncio.get_event_loop()
    scheduled_check.start()
    
    # Botni ishga tushirish
    executor.start_polling(dp, skip_updates=True)'

# Ma'lumotlar bazasini ishga tushirish
conn = sqlite3.connect('telegram_bot.db')
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
logging.basicConfig(level=logging.INFO)

# Bot va dispatcher yaratish
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Admin IDlarini ro'yxatga olish
ADMIN_IDS = [123456789]  # O'zingizning ID raqamingizni qo'ying

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
            "Necha daqiqada bir xabar yuborilsin?\n"
            "Raqam kiriting (5 dan 1440 gacha).",
            reply_markup=get_cancel_keyboard()
        )
    
    elif schedule_type == "🕒 Aniq vaqtda":
        await state.update_data(schedule_type="specific_time")
        await NewMessage.specific_time.set()
        await message.answer(
            "Qaysi vaqtda xabar yuborilsin?\n"
            "Format: HH:MM (24 soatlik format)\n"
            "Masalan: 09:00 yoki 18:30",
            reply_markup=get_cancel_keyboard()
        )
    
    elif schedule_type == "📅 Hafta kunlarida":
        await state.update_data(schedule_type="specific_days")
        await state.update_data(selected_days=[])
        await NewMessage.specific_days.set()
        await message.answer(
            "Qaysi kunlarda xabar yuborilsin?\n"
            "Bir nechta kunlarni tanlashingiz mumkin.",
            reply_markup=get_days_keyboard()
        )

# Interval bo'yicha yuborish
@dp.message_handler(state=NewMessage.interval)
async def process_interval(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    
    try:
        interval = int(message.text)
        if interval < 5 or interval > 1440:
            await message.answer(
                "Noto'g'ri vaqt. 5 daqiqadan 1440 daqiqagacha (24 soat) kiriting.",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        await state.update_data(interval=interval)
        
        # Ma'lumotlarni olish
        data = await state.get_data()
        target_type = data.get('target_type')
        target_id = data.get('target_id')
        message_text = data.get('message_text')
        
        # Bazaga saqlash
        now = datetime.now()
        cursor.execute(
            "INSERT INTO scheduled_messages (target_type, target_id, message_text, interval_minutes, created_by, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (target_type, target_id, message_text, interval, message.from_user.id, True)
        )
        conn.commit()
        
        await message.answer(
            f"✅ Xabar rejalashtirildi!\n\n"
            f"Har {interval} daqiqada yuboriladi.",
            reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
        )
        
        await state.finish()
        
    except ValueError:
        await message.answer(
            "Iltimos, faqat raqam kiriting.",
            reply_markup=get_cancel_keyboard()
        )

# Aniq vaqt bo'yicha yuborish
@dp.message_handler(state=NewMessage.specific_time)
async def process_specific_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(is_admin))
        return
    time_str = message.text
time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
    
if not time_pattern.match(time_str):
    await message.answer(
        "Noto'g'ri vaqt formati. HH:MM formatida kiriting.\n"
        "Masalan: 09:00 yoki 18:30",
        reply_markup=get_cancel_keyboard()
    )
    return
    
await state.update_data(specific_time=time_str)
    
# Ma'lumotlarni olish
data = await state.get_data()
target_type = data.get('target_type')
target_id = data.get('target_id')
message_text = data.get('message_text')
    
# Bazaga saqlash
now = datetime.now()
cursor.execute(
    "INSERT INTO scheduled_messages (target_type, target_id, message_text, specific_time, created_by, is_active) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (target_type, target_id, message_text, time_str, message.from_user.id, True)
)
conn.commit()
    
await message.answer(
    f"✅ Xabar rejalashtirildi!\n\n"
    f"Har kuni {time_str} da yuboriladi.",
    reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
)
    
await state.finish()

# Hafta kunlari bo'yicha yuborish
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
    
    selected_names = [days_names[d] for d in selected_days]
    
    await callback_query.message.edit_text(
        f"Tanlangan kunlar: {', '.join(selected_names) if selected_names else 'Tanlanmagan'}\n\n"
        f"Tanlashni davom ettiring yoki \"Tayyor\" tugmasini bosing.",
        reply_markup=get_days_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "days_done", state=NewMessage.specific_days)
async def process_days_done(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_days = data.get('selected_days', [])
    
    if not selected_days:
        await callback_query.answer("Kamida bitta kunni tanlang!")
        return
    
    await callback_query.answer("Kunlar saqlandi!")
    
    # Ma'lumotlarni olish
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    message_text = data.get('message_text')
    days_str = ','.join(selected_days)
    
    # Bazaga saqlash
    now = datetime.now()
    cursor.execute(
        "INSERT INTO scheduled_messages (target_type, target_id, message_text, specific_days, created_by, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (target_type, target_id, message_text, days_str, callback_query.from_user.id, True)
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
    
    selected_names = [days_names[d] for d in selected_days]
    
    await callback_query.message.edit_text(
        f"✅ Xabar rejalashtirildi!\n\n"
        f"Har hafta {', '.join(selected_names)} kunlari soat 09:00 da yuboriladi."
    )
    
    is_admin = callback_query.from_user.id in ADMIN_IDS
    await callback_query.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))
    
    await state.finish()

# Rejalarni bekor qilish
@dp.message_handler(lambda message: message.text == "🚫 Rejalarni bekor qilish")
async def cancel_scheduled_messages(message: types.Message):
    user_id = message.from_user.id
    
    # Foydalanuvchining rejalashtirilgan xabarlarini olish
    cursor.execute(
        "SELECT * FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
        (user_id,)
    )
    messages = cursor.fetchall()
    
    if not messages:
        await message.answer("❌ Sizning rejalashtirilgan xabarlaringiz yo'q")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
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
            schedule_info = f"{', '.join(days_readable)} kunlari"
        
        target_info = f"@{target_id}" if target_id.startswith('@') else target_id
        
        button_text = f"❌ #{msg_id}: {target_info} ({schedule_info})"
        keyboard.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"cancel_msg_{msg_id}"
        ))
    
    await message.answer(
        "🚫 Bekor qilmoqchi bo'lgan xabarni tanlang:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('cancel_msg_'))
async def process_cancel_message(callback_query: types.CallbackQuery):
    msg_id = int(callback_query.data.split('_')[2])
    
    cursor.execute(
        "UPDATE scheduled_messages SET is_active = 0 WHERE id = ? AND created_by = ?",
        (msg_id, callback_query.from_user.id)
    )
    conn.commit()
    
    await callback_query.answer(f"#{msg_id} bekor qilindi!")
    
    # Qolgan xabarlarni tekshirish
    cursor.execute(
        "SELECT COUNT(*) FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
        (callback_query.from_user.id,)
    )
    count = cursor.fetchone()[0]
    
    if count > 0:
        # Buttonlarni yangilash
        cursor.execute(
            "SELECT * FROM scheduled_messages WHERE created_by = ? AND is_active = 1",
            (callback_query.from_user.id,)
        )
        messages = cursor.fetchall()
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        
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
                schedule_info = f"{', '.join(days_readable)} kunlari"
            
            target_info = f"@{target_id}" if target_id.startswith('@') else target_id
            
            button_text = f"❌ #{msg_id}: {target_info} ({schedule_info})"
            keyboard.add(InlineKeyboardButton(
                text=button_text,
                callback_data=f"cancel_msg_{msg_id}"
            ))
        
        await callback_query.message.edit_text(
            "🚫 Bekor qilmoqchi bo'lgan xabarni tanlang:",
            reply_markup=keyboard
        )
    else:
        is_admin = callback_query.from_user.id in ADMIN_IDS
        await callback_query.message.edit_text("✅ Barcha rejalashtirilgan xabarlar bekor qilindi.")
        await callback_query.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))

# Foydalanuvchi faolligini kuzatish
@dp.message_handler()
async def track_user_activity(message: types.Message):
    await register_user(message)
    
    # Asosiy menyuga qaytish
    if message.text == "/menu":
        is_admin = message.from_user.id in ADMIN_IDS
        await message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(is_admin))
    else:
        # Boshqa buyruqlar uchun
        await message.answer(
            "🤔 Nima qilishni xohlaysiz?\n\n"
            "Asosiy menyuga qaytish uchun /menu buyrug'ini yuboring.",
            reply_markup=get_main_keyboard(message.from_user.id in ADMIN_IDS)
        )

if __name__ == '__main__':
    # Scheduled taskni ishga tushirish
    loop = asyncio.get_event_loop()
    scheduled_check.start()
    
    # Botni ishga tushirish
    executor.start_polling(dp, skip_updates=True)
