# SEH Telegram CRM bot

Bu bot SEH klientlari uchun oddiy CRM:
- klient qo‘shish
- sotuv yozish
- to‘lov yozish
- qarzni hisoblash
- Telegram ID ulangan klientga avtomatik shaxsiy xabar yuborish

## Muhim
Bot klientning Telegram kontaktlaridan odamni o‘zi topa olmaydi.
Klient avval botga `/start` yuborishi kerak. Shundan keyin uning Telegram ID sini `/addclient` orqali klientga bog‘laysiz.

## Ishga tushirish
1. Python 3.10+ o‘rnating.
2. Terminalda:
   `pip install -r requirements.txt`
3. `bot.py` ichidagi:
   `BOT_TOKEN = "PASTE_YOUR_NEW_BOT_TOKEN_HERE"`
   o‘rniga BotFather bergan yangi tokenni yozing.
4. `ADMIN_ID = 0` o‘rniga o‘zingizning Telegram ID ingizni yozing.
   Telegramda botga `/myid` yuborib ID ni ko‘rishingiz mumkin.
5. Ishga tushiring:
   `python bot.py`

## Buyruqlar

Klient:
`/start`

Admin:
`/addclient Aliyev Ali | +998901234567 | 123456789`

`/sale Aliyev | Eshik romi | 18000000 | 2 dona`

`/pay Aliyev | 5000000 | Naqd`

`/client Aliyev`

`/help`

SQLite bazasi `seh_crm.db` faylida saqlanadi.
