import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = '7160875026:AAFqGkoYmr9XqW1zANPU8OxsokmawqkeJ5g'
ADMIN_ID = 6643037038  # Твой ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Временная база данных (в памяти)
# Структура: {user_id: {"name": "...", "phone": "..."}}
users_data = {}
users_db = set() # Для рассылки

# Состояния
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

class Form(StatesGroup):
    waiting_for_reply = State()
    waiting_for_broadcast = State()

# --- Клавиатуры ---
def get_phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_admin_reply_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}"))
    return builder.as_markup()

def get_admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast"))
    return builder.as_markup()

# --- Хендлеры Регистрации ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, Админ!", reply_markup=get_admin_main_kb())
        return

    # Если пользователя нет в базе, начинаем опрос
    if message.from_user.id not in users_data:
        await message.answer("Привет! Чтобы отправить сообщение админу, нужно зарегистрироваться.\n\nВведите ваше **Имя**:")
        await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"Приятно познакомиться, {message.text}! Теперь нажмите кнопку ниже, чтобы отправить свой номер телефона:", 
                         reply_markup=get_phone_kb())
    await state.set_state(Registration.waiting_for_phone)

@dp.message(Registration.waiting_for_phone, F.contact)
async def process_phone(message: types.Message, state: FSMContext):
    user_info = await state.get_data()
    name = user_info.get("name")
    phone = message.contact.phone_number
    
    # Сохраняем в "базу"
    users_data[message.from_user.id] = {"name": name, "phone": phone}
    users_db.add(message.from_user.id)
    
    await message.answer(f"Регистрация завершена! ✅\nТеперь вы можете писать сообщения админу.", 
                         reply_markup=ReplyKeyboardRemove())
    await state.clear()

# --- Хендлеры Сообщений (Пользователь -> Админ) ---

@dp.message(F.chat.type == "private", F.from_user.id != ADMIN_ID)
async def forward_to_admin(message: types.Message, state: FSMContext):
    # Проверка регистрации
    if message.from_user.id not in users_data:
        await message.answer("Сначала пройдите регистрацию. Напишите /start")
        return

    user_info = users_data[message.from_user.id]
    info_header = (f"👤 **От:** {user_info['name']}\n"
                   f"📞 **Тел:** `{user_info['phone']}`\n"
                   f"🆔 **ID:** `{message.from_user.id}`\n"
                   f"------------------------\n")

    if message.photo:
        photo_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        await bot.send_photo(
            ADMIN_ID, 
            photo_id, 
            caption=f"{info_header}{caption}",
            reply_markup=get_admin_reply_kb(message.from_user.id),
            parse_mode="Markdown"
        )
    else:
        await bot.send_message(
            ADMIN_ID, 
            f"{info_header}{message.text}",
            reply_markup=get_admin_reply_kb(message.from_user.id),
            parse_mode="Markdown"
        )
    await message.answer("Сообщение доставлено админу!")

# --- Хендлеры Админки (Ответ и Рассылка) ---

@dp.callback_query(F.data.startswith("reply_"))
async def ask_reply(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    await state.update_data(reply_to_user_id=user_id)
    await callback.message.answer(f"Введите ответ для пользователя (ID: {user_id}):")
    await state.set_state(Form.waiting_for_reply)
    await callback.answer()

@dp.message(Form.waiting_for_reply)
async def send_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to_user_id")
    
    try:
        if message.photo:
            await bot.send_photo(user_id, message.photo[-1].file_id, caption=f"✉️ **Ответ админа:**\n\n{message.caption or ''}", parse_mode="Markdown")
        else:
            await bot.send_message(user_id, f"✉️ **Ответ админа:**\n\n{message.text}", parse_mode="Markdown")
        await message.answer("Ответ отправлен!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    await state.clear()

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Пришлите сообщение для рассылки (текст или фото):")
    await state.set_state(Form.waiting_for_broadcast)
    await callback.answer()

@dp.message(Form.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    count = 0
    for uid in list(users_db):
        try:
            if message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption, parse_mode="Markdown")
            else:
                await bot.send_message(uid, message.text, parse_mode="Markdown")
            count += 1
        except:
            pass
    await message.answer(f"✅ Рассылка завершена. Получили: {count}")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
