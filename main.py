import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = '8314204853:AAGQ-7osbpTbgR1-l-TA1lxffuYupWm-EQg'
ADMIN_ID = 7047185903

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# DB
users_data = {}
users_db = set()

# STATES
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()

class Form(StatesGroup):
    waiting_for_reply = State()
    waiting_for_broadcast = State()

# --- KEYBOARDS ---
def get_phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона / Telefon yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_admin_reply_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✉️ Ответить / Javob berish", callback_data=f"reply_{user_id}"))
    return kb.as_markup()

def get_admin_main_kb():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📢 Рассылка / Xabar yuborish", callback_data="broadcast"))
    return kb.as_markup()

# --- START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Добро пожаловать, Админ!\n"
            "Xush kelibsiz, Admin!",
            reply_markup=get_admin_main_kb()
        )
        return

    if message.from_user.id not in users_data:
        await message.answer(
            "Введите ваше имя:\n"
            "Ismingizni kiriting:"
        )
        await state.set_state(Registration.waiting_for_name)

# --- NAME ---
@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "Теперь отправьте номер телефона:\n"
        "Endi telefon raqamingizni yuboring:",
        reply_markup=get_phone_kb()
    )
    await state.set_state(Registration.waiting_for_phone)

# --- PHONE ---
@dp.message(Registration.waiting_for_phone, F.contact)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer(
        "Введите ваш адрес:\n"
        "Manzilingizni kiriting:"
    )
    await state.set_state(Registration.waiting_for_address)

# --- ADDRESS ---
@dp.message(Registration.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    data = await state.get_data()

    users_data[message.from_user.id] = {
        "name": data["name"],
        "phone": data["phone"],
        "address": message.text
    }

    users_db.add(message.from_user.id)

    await message.answer(
        "Регистрация завершена! ✅\n"
        "Ro‘yxatdan o‘tish yakunlandi! ✅",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

# --- USER → ADMIN ---
@dp.message(F.chat.type == "private", F.from_user.id != ADMIN_ID)
async def forward_to_admin(message: types.Message):
    if message.from_user.id not in users_data:
        await message.answer(
            "Сначала пройдите регистрацию: /start\n"
            "Avval ro‘yxatdan o‘ting: /start"
        )
        return

    user = users_data[message.from_user.id]

    header = (
        f"👤 **Имя / Ism:** {user['name']}\n"
        f"📞 **Телефон / Telefon:** `{user['phone']}`\n"
        f"📍 **Адрес / Manzil:** {user['address']}\n"
        f"🆔 **ID:** `{message.from_user.id}`\n"
        f"------------------------\n"
    )

    if message.photo:
        await bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=header + (message.caption or ""),
            reply_markup=get_admin_reply_kb(message.from_user.id),
            parse_mode="Markdown"
        )
    else:
        await bot.send_message(
            ADMIN_ID,
            header + message.text,
            reply_markup=get_admin_reply_kb(message.from_user.id),
            parse_mode="Markdown"
        )

    await message.answer(
        "Сообщение отправлено админу ✅\n"
        "Xabar adminga yuborildi ✅"
    )

# --- ADMIN REPLY ---
@dp.callback_query(F.data.startswith("reply_"))
async def ask_reply(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    await state.update_data(reply_to=user_id)
    await callback.message.answer(
        f"Введите ответ пользователю:\n"
        f"Foydalanuvchiga javob yozing (ID: {user_id})"
    )
    await state.set_state(Form.waiting_for_reply)
    await callback.answer()

@dp.message(Form.waiting_for_reply)
async def send_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = data["reply_to"]

    await bot.send_message(
        uid,
        f"✉️ **Ответ админа / Admin javobi:**\n\n{message.text}",
        parse_mode="Markdown"
    )
    await message.answer("Отправлено ✅ / Yuborildi ✅")
    await state.clear()

# --- BROADCAST ---
@dp.callback_query(F.data == "broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Отправьте сообщение для рассылки:\n"
        "Xabar yuboring (ommaviy):"
    )
    await state.set_state(Form.waiting_for_broadcast)
    await callback.answer()

@dp.message(Form.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    count = 0
    for uid in users_db:
        try:
            await bot.send_message(uid, message.text)
            count += 1
        except:
            pass

    await message.answer(
        f"Рассылка завершена ✅\n"
        f"Yuborildi: {count} ta"
    )
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



