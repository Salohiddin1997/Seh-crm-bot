import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "294495137"))
DB_FILE = "seh_crm.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Railway Variables ichida berilmagan!")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def add_client(name, phone=None, telegram_id=None, username=None):
    conn = db()
    try:
        cur = conn.execute(
            """INSERT INTO clients
            (name, phone, telegram_id, username, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (name, phone, telegram_id, username,
             datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def normalize_text(value):
    """Ism qidirishda katta-kichik harf va ortiqcha bo'shliqlarni bir xil qiladi."""
    return " ".join((value or "").strip().casefold().split())


def parse_amount(value):
    """5000000, 5 000 000, 5.000.000 va 5,000,000 ni qabul qiladi."""
    raw = (value or "").strip()
    cleaned = raw.replace(" ", "").replace("\u00a0", "")
    if not cleaned:
        raise ValueError

    # O'zbek so'm summalarida nuqta/vergul minglik ajratgich bo'lishi mumkin.
    if cleaned.count(".") > 1 or cleaned.count(",") > 1:
        cleaned = cleaned.replace(".", "").replace(",", "")
    elif "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", "")
    elif "." in cleaned and len(cleaned.split(".")[-1]) == 3:
        cleaned = cleaned.replace(".", "")
    elif "," in cleaned and len(cleaned.split(",")[-1]) == 3:
        cleaned = cleaned.replace(",", "")

    amount = float(cleaned)
    if amount <= 0:
        raise ValueError
    return amount


def find_client(name_or_id):
    """Avval Telegram ID, keyin ism bo'yicha mijozni topadi."""
    value = (name_or_id or "").strip()
    if value.isdigit():
        client = get_client_by_tg(int(value))
        if client:
            return client

    target = normalize_text(value)
    conn = db()
    clients = conn.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    conn.close()

    # Avval aniq moslik, keyin qisman moslik.
    for client in clients:
        if normalize_text(client["name"]) == target:
            return client
    for client in clients:
        if target and target in normalize_text(client["name"]):
            return client
    return None


def get_client_by_tg(tg_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM clients WHERE telegram_id = ? LIMIT 1",
        (tg_id,)
    ).fetchone()
    conn.close()
    return row


def client_debt(client_id):
    conn = db()
    sold = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM sales WHERE client_id=?",
        (client_id,)
    ).fetchone()["total"]
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE client_id=?",
        (client_id,)
    ).fetchone()["total"]
    conn.close()
    return float(sold or 0) - float(paid or 0)


def add_sale(client_id, product, amount, note=""):
    conn = db()
    conn.execute(
        """INSERT INTO sales
           (client_id, product, amount, note, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (client_id, product, amount, note,
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


def add_payment(client_id, amount, note=""):
    conn = db()
    conn.execute(
        """INSERT INTO payments
           (client_id, amount, note, created_at)
           VALUES (?, ?, ?, ?)""",
        (client_id, amount, note,
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


def is_admin(message: Message):
    return bool(message.from_user and message.from_user.id == ADMIN_ID)


def money(value):
    return f"{float(value):,.0f}".replace(",", " ")


def parse_parts(message: Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return []
    return [x.strip() for x in parts[1].split("|")]


async def notify_client(client, text):
    if not client["telegram_id"]:
        return
    try:
        await bot.send_message(client["telegram_id"], text)
    except Exception as e:
        logging.warning("Mijozga xabar yuborilmadi: %s", e)


@dp.message(Command("start"))
async def start(message: Message):
    tg_id = message.from_user.id
    username = message.from_user.username or ""
    existing = get_client_by_tg(tg_id)

    if existing:
        await message.answer(
            f"Assalomu alaykum, {existing['name']}! 👋\n\n"
            "Siz SEH tizimiga ulandingiz.\n"
            f"💰 Qarz: {money(client_debt(existing['id']))} so'm"
        )
        return

    full_name = message.from_user.full_name or "Noma'lum"
    client_id = add_client(
        full_name, None, tg_id, username
    )

    if not client_id:
        await message.answer("Xatolik: bazaga qo'shib bo'lmadi.")
        return

    await message.answer(
        f"Assalomu alaykum, {full_name}! 👋\n\n"
        "Siz SEH mijozlar bazasiga muvaffaqiyatli qo'shildingiz.\n"
        f"Telegram ID: {tg_id}\n"
        f"Username: @{username if username else 'yo‘q'}\n\n"
        "Endi sotuv va to'lovlar haqidagi xabarlar shu bot orqali keladi."
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            "🆕 Yangi mijoz botga qo‘shildi!\n\n"
            f"👤 Ism: {full_name}\n"
            f"🆔 Telegram ID: {tg_id}\n"
            f"🔗 Username: @{username if username else 'yo‘q'}"
        )
    except Exception:
        pass


@dp.message(Command("myid"))
async def myid(message: Message):
    await message.answer(
        f"Sizning Telegram ID'ingiz: {message.from_user.id}"
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    if is_admin(message):
        await message.answer(
            "SEH CRM buyruqlari:\n\n"
            "/addclient Ism | Telefon | TelegramID\n"
            "/sale Klient | Mahsulot | Summa | Izoh\n"
            "/door Klient | O‘lcham | Summa | Izoh\n"
            "/pay Klient | Summa | Izoh\n"
            "/payid TelegramID | Summa | Izoh\n"
            "/client Klient\n"
            "/clients\n"
            "/myid\n"
            "/resetdata HA — test sotuv va to‘lovlarni tozalash\n\n"
            "Misol:\n"
            "/sale Aliyev Ali | Eshik romi | 1800000 | Oq rang\n"
            "/pay Aliyev Ali | 500000 | Naqd\n"
            "Yoki: /payid 6105920151 | 500000 | Naqd"
        )
    else:
        await message.answer(
            "SEH bot.\n\n/start — tizimga ulanish\n/myid — Telegram ID"
        )


@dp.message(Command("addclient"))
async def addclient_cmd(message: Message):
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    parts = parse_parts(message)
    if not parts or not parts[0]:
        await message.answer(
            "Format:\n/addclient Ism | Telefon | TelegramID"
        )
        return

    name = parts[0]
    phone = parts[1] if len(parts) > 1 and parts[1] else None
    telegram_id = None

    if len(parts) > 2 and parts[2]:
        try:
            telegram_id = int(parts[2])
        except ValueError:
            await message.answer("Xatolik: Telegram ID faqat raqam bo'lishi kerak.")
            return

    client_id = add_client(name, phone, telegram_id)
    if not client_id:
        await message.answer("Xatolik: mijoz qo'shilmadi. Bu Telegram ID bazada mavjud bo'lishi mumkin.")
        return

    await message.answer(
        "✅ Mijoz qo‘shildi!\n\n"
        f"👤 Ism: {name}\n"
        f"📞 Telefon: {phone or '—'}\n"
        f"🆔 Telegram ID: {telegram_id or '—'}"
    )


@dp.message(Command("sale"))
async def sale_cmd(message: Message):
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    parts = parse_parts(message)
    if len(parts) < 3:
        await message.answer(
            "Format:\n/sale Klient | Mahsulot | Summa | Izoh"
        )
        return

    client = find_client(parts[0])
    if not client:
        await message.answer(f"❌ '{parts[0]}' nomli mijoz topilmadi.")
        return

    try:
        amount = parse_amount(parts[2])
    except ValueError:
        await message.answer("Xatolik: summa noto'g'ri. Masalan: 5000000 yoki 5.000.000")
        return

    product = parts[1]
    note = parts[3] if len(parts) > 3 else ""
    add_sale(client["id"], product, amount, note)
    debt = client_debt(client["id"])

    await message.answer(
        "✅ Sotuv yozildi!\n\n"
        f"👤 Mijoz: {client['name']}\n"
        f"📦 Mahsulot: {product}\n"
        f"💵 Summa: {money(amount)} so‘m\n"
        f"💰 Qolgan qarz: {money(debt)} so‘m"
    )

    await notify_client(
        client,
        "🧾 SEH — yangi sotuv\n\n"
        f"📦 Mahsulot: {product}\n"
        f"💵 Summa: {money(amount)} so‘m\n"
        f"💰 Qolgan qarzingiz: {money(debt)} so‘m"
        + (f"\n📝 Izoh: {note}" if note else "")
    )



@dp.message(Command("door"))
async def door_sale_cmd(message: Message):
    """Tayyor eshik sotuvini qayd qiladi. Eshik omborga qo'shilmaydi."""
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    parts = parse_parts(message)
    if len(parts) < 3:
        await message.answer(
            "🚪 Eshik sotish formati:\n"
            "/door Klient | O‘lcham | Summa | Izoh\n\n"
            "Misol:\n"
            "/door Aliyev Ali | 2000x500 | 1000000 | Oq eshik"
        )
        return

    client = find_client(parts[0])
    if not client:
        await message.answer(f"❌ '{parts[0]}' nomli mijoz topilmadi.")
        return

    size = parts[1]
    try:
        amount = parse_amount(parts[2])
    except ValueError:
        await message.answer(
            "❌ Summa noto‘g‘ri. Masalan: 1000000 yoki 1.000.000"
        )
        return

    note = parts[3] if len(parts) > 3 else ""
    product = f"Eshik {size}"
    add_sale(client["id"], product, amount, note)
    debt = client_debt(client["id"])

    await message.answer(
        "✅ Eshik sotuvi yozildi!\n\n"
        f"👤 Klient: {client['name']}\n"
        f"🚪 Eshik: {size}\n"
        f"💵 Summa: {money(amount)} so‘m\n"
        f"💰 Qolgan qarz: {money(debt)} so‘m"
        + (f"\n📝 Izoh: {note}" if note else "")
    )

    await notify_client(
        client,
        "🧾 SEH — yangi eshik sotuvi\n\n"
        f"🚪 Eshik: {size}\n"
        f"💵 Summa: {money(amount)} so‘m\n"
        f"💰 Qolgan qarzingiz: {money(debt)} so‘m"
        + (f"\n📝 Izoh: {note}" if note else "")
    )

@dp.message(Command("pay"))
async def pay_cmd(message: Message):
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    parts = parse_parts(message)
    if len(parts) < 2:
        await message.answer(
            "Format:\n/pay Mijoz | Summa | Izoh"
        )
        return

    client = find_client(parts[0])
    if not client:
        await message.answer(f"❌ '{parts[0]}' nomli mijoz topilmadi.")
        return

    try:
        amount = parse_amount(parts[1])
    except ValueError:
        await message.answer("Xatolik: summa noto'g'ri. Masalan: 5000000 yoki 5.000.000")
        return

    note = parts[2] if len(parts) > 2 else ""
    add_payment(client["id"], amount, note)
    debt = client_debt(client["id"])

    await message.answer(
        "✅ To‘lov yozildi!\n\n"
        f"👤 Mijoz: {client['name']}\n"
        f"💵 To‘lov: {money(amount)} so‘m\n"
        f"💰 Qolgan qarz: {money(debt)} so‘m"
    )

    await notify_client(
        client,
        "💳 SEH — to‘lov qabul qilindi\n\n"
        f"💵 To‘lov: {money(amount)} so‘m\n"
        f"💰 Qolgan qarzingiz: {money(debt)} so‘m"
        + (f"\n📝 Izoh: {note}" if note else "")
    )


@dp.message(Command("payid"))
async def payid_cmd(message: Message):
    if not is_admin(message):
        await message.answer("Xatolik: bu buyruq faqat admin uchun.")
        return

    parts = parse_parts(message)
    if len(parts) < 2:
        await message.answer(
            "Format:\n/payid TelegramID | Summa | Izoh\n\n"
            "Misol:\n/payid 6105920151 | 2000000 | Qarz"
        )
        return

    try:
        tg_id = int(parts[0])
    except ValueError:
        await message.answer("Telegram ID faqat raqamlardan iborat bo'lishi kerak.")
        return

    client = get_client_by_tg(tg_id)
    if not client:
        await message.answer(f"Bu Telegram ID bo'yicha mijoz topilmadi: {tg_id}")
        return

    try:
        amount = parse_amount(parts[1])
    except ValueError:
        await message.answer("Summa noto'g'ri. Masalan: 2000000 yoki 2.000.000")
        return

    note = parts[2] if len(parts) > 2 else ""
    add_payment(client["id"], amount, note)
    debt = client_debt(client["id"])

    await message.answer(
        "To'lov yozildi!\n\n"
        f"Mijoz: {client['name']}\n"
        f"To'lov: {money(amount)} so'm\n"
        f"Qolgan qarz: {money(debt)} so'm"
    )

    await notify_client(
        client,
        "SEH CRM — to'lov qabul qilindi\n\n"
        f"To'lov: {money(amount)} so'm\n"
        f"Qolgan qarzingiz: {money(debt)} so'm"
        + (f"\nIzoh: {note}" if note else "")
    )


@dp.message(Command("resetdata"))
async def resetdata_cmd(message: Message):
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip().upper() != "HA":
        await message.answer(
            "⚠️ Bu buyruq barcha sotuv va to‘lov yozuvlarini o‘chiradi.\n"
            "Mijozlarning o‘zi saqlanib qoladi.\n\n"
            "Tasdiqlash uchun yozing:\n"
            "/resetdata HA"
        )
        return

    conn = db()
    conn.execute("DELETE FROM payments")
    conn.execute("DELETE FROM sales")
    conn.commit()
    conn.close()

    await message.answer(
        "✅ Test ma’lumotlari tozalandi!\n\n"
        "Mijozlar saqlanib qoldi.\n"
        "Sotuvlar: 0\n"
        "To‘lovlar: 0\n"
        "Endi hisob-kitobni boshidan boshlashingiz mumkin."
    )


@dp.message(Command("client"))
async def client_info(message: Message):
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    parts = parse_parts(message)
    if not parts:
        await message.answer("Format: /client Mijoz")
        return

    client = find_client(parts[0])
    if not client:
        await message.answer("Xatolik: mijoz topilmadi.")
        return

    await message.answer(
        f"👤 {client['name']}\n"
        f"📞 {client['phone'] or '—'}\n"
        f"🆔 Telegram ID: {client['telegram_id'] or '—'}\n"
        f"🔗 Username: @{client['username'] if client['username'] else '—'}\n"
        f"💰 Qarz: {money(client_debt(client['id']))} so‘m"
    )


@dp.message(Command("clients"))
async def clients_cmd(message: Message):
    if not is_admin(message):
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return

    conn = db()
    clients = conn.execute(
        "SELECT * FROM clients ORDER BY id DESC"
    ).fetchall()
    conn.close()

    if not clients:
        await message.answer("Hozircha mijozlar yo‘q.")
        return

    text = "👥 SEH mijozlari:\n\n"
    for i, client in enumerate(clients, 1):
        text += f"{i}. {client['name']} — {money(client_debt(client['id']))} so‘m\n"

    await message.answer(text[:4000])


async def main():
    init_db()
    logging.info("SEH CRM bot ishga tushdi")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
