import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

# =========================
# SOZLAMALAR
# =========================
BOT_TOKEN = "8669780668:AAG_sq3lWprck6i4miJoIb1RBVKMHZuBp48"
ADMIN_ID =294495137  # Sizning Telegram ID'ingizni shu yerga yozing

DB_FILE = "seh_crm.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# =========================
# DATABASE
# =========================
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            telegram_id INTEGER UNIQUE,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            amount REAL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    conn.commit()
    conn.close()


def is_admin(message: Message) -> bool:
    return message.from_user and message.from_user.id == ADMIN_ID


def add_client(name, phone=None, telegram_id=None):
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO clients(name, phone, telegram_id, created_at) VALUES(?,?,?,?)",
            (name, phone, telegram_id, datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def find_client(name):
    conn = db()
    row = conn.execute(
        "SELECT * FROM clients WHERE lower(name) LIKE lower(?) ORDER BY id DESC LIMIT 1",
        (f"%{name}%",)
    ).fetchone()
    conn.close()
    return row


def get_client_by_tg(tg_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM clients WHERE telegram_id=?", (tg_id,)
    ).fetchone()
    conn.close()
    return row


def client_debt(client_id):
    conn = db()
    sold = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM sales WHERE client_id=?",
        (client_id,)
    ).fetchone()["s"]
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM payments WHERE client_id=?",
        (client_id,)
    ).fetchone()["s"]
    conn.close()
    return float(sold or 0) - float(paid or 0)


# =========================
# CLIENT COMMANDS
# =========================
@dp.message(Command("start"))
async def start(message: Message):
    # Klient botni start qilsa, admin keyin uni telegram_id bilan bog'lay oladi.
    tg_id = message.from_user.id
    username = message.from_user.username or ""

    existing = get_client_by_tg(tg_id)

    if existing:
        await message.answer(
            f"Assalomu alaykum, {existing['name']}!\n"
            f"Siz SEH tizimiga ulangan siz.\n"
            f"Qarz: {client_debt(existing['id']):,.0f} so'm"
        )
        await full_name = message.from_user.full_name

    add_client(

        name=full_name,

        phone=None,

        telegram_id=tg_id

    )

    await message.answer(

        f"Assalomu alaykum, {full_name}! 👋\n\n"

        "Siz SEH mijozlar bazasiga muvaffaqiyatli qo‘shildingiz.\n"

        f"Telegram ID: {tg_id}\n"

        f"Username: @{username if username else 'yo‘q'}\n\n"

        "Endi sotuv va to‘lovlar haqidagi xabarlar shu bot orqali keladi."

    )


@dp.message(Command("myid"))
async def myid(message: Message):
    await message.answer(f"Sizning Telegram ID'ingiz: {message.from_user.id}")


# =========================
# ADMIN COMMANDS
# =========================
@dp.message(Command("addclient"))
async def addclient(message: Message):
    if not is_admin(message):
        return await message.answer("Bu buyruq faqat admin uchun.")

    # Format:
    # /addclient Ism | Telefon | TelegramID
    text = message.text.partition(" ")[2].strip()
    parts = [x.strip() for x in text.split("|")]

    if len(parts) < 1 or not parts[0]:
        return await message.answer(
            "Format:\n/addclient Ism | Telefon | TelegramID\n\n"
            "Masalan:\n/addclient Aliyev Ali | +998901234567 | 123456789"
        )

    name = parts[0]
    phone = parts[1] if len(parts) >= 2 and parts[1] else None

    telegram_id = None
    if len(parts) >= 3 and parts[2]:
        try:
            telegram_id = int(parts[2])
        except ValueError:
            return await message.answer("Telegram ID raqam bo‘lishi kerak.")

    try:
        client_id = add_client(name, phone, telegram_id)
        await message.answer(f"✅ Klient qo‘shildi.\nID: {client_id}\nIsm: {name}")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bu Telegram ID allaqachon boshqa klientga ulangan.")


@dp.message(Command("sale"))
async def sale(message: Message):
    if not is_admin(message):
        return await message.answer("Bu buyruq faqat admin uchun.")

    # Format:
    # /sale Klient | Mahsulot | Summa | Izoh
    text = message.text.partition(" ")[2].strip()
    parts = [x.strip() for x in text.split("|")]

    if len(parts) < 3:
        return await message.answer(
            "Format:\n/sale Klient | Mahsulot | Summa | Izoh\n\n"
            "Masalan:\n/sale Aliyev | Eshik romi | 18000000 | 2 dona"
        )

    client_name, product, amount_text = parts[:3]
    note = parts[3] if len(parts) >= 4 else ""

    client = find_client(client_name)
    if not client:
        return await message.answer("❌ Klient topilmadi. Avval /addclient bilan qo‘shing.")

    try:
        amount = float(amount_text.replace(" ", "").replace(",", ""))
    except ValueError:
        return await message.answer("❌ Summa noto‘g‘ri. Masalan: 18000000")

    conn = db()
    conn.execute(
        "INSERT INTO sales(client_id, product, amount, note, created_at) VALUES(?,?,?,?,?)",
        (client["id"], product, amount, note, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    debt = client_debt(client["id"])

    await message.answer(
        f"✅ Sotuv yozildi.\n"
        f"Klient: {client['name']}\n"
        f"Mahsulot: {product}\n"
        f"Summa: {amount:,.0f} so‘m\n"
        f"Jami qarz: {debt:,.0f} so‘m"
    )

    # Telegram ID mavjud bo'lsa, klientga shaxsiy xabar yuboriladi.
    if client["telegram_id"]:
        try:
            await bot.send_message(
                client["telegram_id"],
                f"Assalomu alaykum, {client['name']}!\n\n"
                f"SEH bo‘yicha yangi sotuv yozildi:\n"
                f"Mahsulot: {product}\n"
                f"Summa: {amount:,.0f} so‘m\n"
                f"Jami qarz: {debt:,.0f} so‘m"
                + (f"\nIzoh: {note}" if note else "")
            )
        except Exception:
            await message.answer(
                "⚠️ Sotuv saqlandi, lekin klientga Telegram xabari yuborilmadi. "
                "Klient botni /start qilganini tekshiring."
            )
    else:
        await message.answer(
            "ℹ️ Klientning Telegram IDsi ulanmagan, shuning uchun shaxsiy xabar yuborilmadi."
        )


@dp.message(Command("pay"))
async def pay(message: Message):
    if not is_admin(message):
        return await message.answer("Bu buyruq faqat admin uchun.")

    # /pay Klient | Summa | Izoh
    text = message.text.partition(" ")[2].strip()
    parts = [x.strip() for x in text.split("|")]

    if len(parts) < 2:
        return await message.answer(
            "Format:\n/pay Klient | Summa | Izoh\n\n"
            "Masalan:\n/pay Aliyev | 5000000 | Naqd"
        )

    client_name, amount_text = parts[:2]
    note = parts[2] if len(parts) >= 3 else ""

    client = find_client(client_name)
    if not client:
        return await message.answer("❌ Klient topilmadi.")

    try:
        amount = float(amount_text.replace(" ", "").replace(",", ""))
    except ValueError:
        return await message.answer("❌ Summa noto‘g‘ri.")

    conn = db()
    conn.execute(
        "INSERT INTO payments(client_id, amount, note, created_at) VALUES(?,?,?,?)",
        (client["id"], amount, note, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    debt = client_debt(client["id"])

    await message.answer(
        f"✅ To‘lov yozildi.\n"
        f"Klient: {client['name']}\n"
        f"To‘lov: {amount:,.0f} so‘m\n"
        f"Qolgan qarz: {debt:,.0f} so‘m"
    )

    if client["telegram_id"]:
        try:
            await bot.send_message(
                client["telegram_id"],
                f"Assalomu alaykum, {client['name']}!\n\n"
                f"SEH bo‘yicha to‘lovingiz qabul qilindi.\n"
                f"To‘lov: {amount:,.0f} so‘m\n"
                f"Qolgan qarz: {debt:,.0f} so‘m"
            )
        except Exception:
            pass


@dp.message(Command("client"))
async def client_info(message: Message):
    if not is_admin(message):
        return await message.answer("Bu buyruq faqat admin uchun.")

    name = message.text.partition(" ")[2].strip()
    if not name:
        return await message.answer("Format: /client Aliyev")

    client = find_client(name)
    if not client:
        return await message.answer("❌ Klient topilmadi.")

    await message.answer(
        f"👤 {client['name']}\n"
        f"📞 {client['phone'] or '—'}\n"
        f"🆔 Telegram ID: {client['telegram_id'] or 'ulanmagan'}\n"
        f"💰 Qarz: {client_debt(client['id']):,.0f} so‘m"
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    if is_admin(message):
        await message.answer(
            "SEH CRM buyruqlari:\n\n"
            "/addclient Ism | Telefon | TelegramID\n"
            "/sale Klient | Mahsulot | Summa | Izoh\n"
            "/pay Klient | Summa | Izoh\n"
            "/client Klient\n\n"
            "Misol:\n"
            "/sale Aliyev | Eshik romi | 18000000 | 2 dona"
        )
    else:
        await message.answer(
            "SEH botiga xush kelibsiz.\n"
            "Admin sizni bazaga ulaganidan keyin kerakli xabarlar shu yerga keladi."
        )


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
