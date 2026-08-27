from flask import Flask, request, redirect, session, flash
import sqlite3, os, hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SEH_SECRET", "change-this-secret")
DB = "seh_ombor.db"


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT
    );
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY, name TEXT, unit TEXT,
        qty REAL DEFAULT 0, cost REAL DEFAULT 0, price REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS workers(
        id INTEGER PRIMARY KEY, name TEXT, phone TEXT, paid REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY, worker_id INTEGER, amount REAL, note TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS clients(
        id INTEGER PRIMARY KEY, name TEXT, phone TEXT, debt REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS door_sales(
        id INTEGER PRIMARY KEY,
        sale_id INTEGER,
        client_id INTEGER,
        width REAL,
        height REAL,
        note TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS sales(
        id INTEGER PRIMARY KEY, product_id INTEGER, client_id INTEGER,
        qty REAL, price REAL, total REAL, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS client_payments(
        id INTEGER PRIMARY KEY, client_id INTEGER, amount REAL, note TEXT, created_at TEXT
    );
    """)
    if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        c.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            ("admin", hashlib.sha256(b"admin123").hexdigest(), "admin")
        )
    c.commit()
    c.close()


init()

STYLE = """<style>
body{font-family:Arial;margin:0;background:#f3f4f6;color:#111827}
header{background:#111827;color:white;padding:18px 24px;font-size:25px;font-weight:700}
nav{background:white;padding:12px;display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid #ddd}
nav a{padding:10px 14px;border-radius:9px;text-decoration:none;color:#111;background:#e5e7eb}
main{max-width:1200px;margin:auto;padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.card,.panel{background:white;border-radius:14px;padding:18px;margin-bottom:16px;box-shadow:0 2px 8px #0001}
.num{font-size:28px;font-weight:bold;margin-top:8px}
input,select{padding:10px;border:1px solid #ccc;border-radius:8px;margin:4px;width:calc(100% - 16px)}
button{padding:10px 14px;border:0;border-radius:8px;background:#111827;color:white;cursor:pointer}
table{width:100%;border-collapse:collapse}
td,th{padding:10px;border-bottom:1px solid #eee;text-align:left}
.msg{padding:10px;background:#dcfce7;border-radius:8px;margin-bottom:10px}
</style>"""


def page(title, body):
    nav = "" if not session.get("user") else """<nav>
    <a href="/">🏠 Bosh sahifa</a>
    <a href="/stock">📦 Ombor</a>
    <a href="/workers">👷 Ishchilar</a>
    <a href="/clients">👥 Klientlar</a>
    <a href="/sales">🧾 Sotuv</a>
    <a href="/logout">🚪 Chiqish</a>
    </nav>"""
    messages = "".join(
        f"<div class='msg'>{m}</div>" for m in session.pop("_flashes", [])
    )
    return (
        "<html><head><meta charset='utf-8'><title>SEH OMBOR</title>"
        + STYLE + "</head><body><header>🏭 SEH OMBOR</header>"
        + nav + "<main><h2>" + title + "</h2>" + messages + body
        + "</main></body></html>"
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = hashlib.sha256(request.form["password"].encode()).hexdigest()
        c = db()
        row = c.execute(
            "SELECT * FROM users WHERE username=? AND password=?", (u, p)
        ).fetchone()
        c.close()
        if row:
            session["user"] = row["username"]
            session["role"] = row["role"]
            return redirect("/")
        flash("Login yoki parol xato")
    return page("Kirish", """<div class='panel' style='max-width:420px;margin:auto'>
    <form method='post'>
    <input name='username' placeholder='Login' required>
    <input name='password' type='password' placeholder='Parol' required>
    <button>Kirish</button>
    <p>Demo admin: <b>admin</b> / <b>admin123</b></p>
    </form></div>""")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.before_request
def protect():
    if request.endpoint not in ("login", "static") and not session.get("user"):
        return redirect("/login")


@app.route("/")
def home():
    c = db()
    products = c.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]
    workers = c.execute("SELECT COUNT(*) n FROM workers").fetchone()["n"]
    clients = c.execute("SELECT COUNT(*) n FROM clients").fetchone()["n"]
    pay = c.execute("SELECT COALESCE(SUM(amount),0) n FROM payments").fetchone()["n"]
    sales = c.execute("SELECT COALESCE(SUM(total),0) n FROM sales").fetchone()["n"]
    c.close()
    return page("Bosh sahifa", f"""<div class='grid'>
    <div class='card'>📦 Mahsulotlar<div class='num'>{products}</div></div>
    <div class='card'>👷 Ishchilar<div class='num'>{workers}</div></div>
    <div class='card'>👥 Klientlar<div class='num'>{clients}</div></div>
    <div class='card'>💰 Ishchilarga berilgan<div class='num'>{pay:,.0f} so'm</div></div>
    <div class='card'>🧾 Jami sotuv<div class='num'>{sales:,.0f} so'm</div></div>
    </div><div class='panel'><b>Admin:</b> {session['user']}</div>""")


@app.route("/stock", methods=["GET", "POST"])
def stock():
    c = db()
    if request.method == "POST":
        c.execute(
            "INSERT INTO products(name,unit,qty,cost,price) VALUES(?,?,?,?,?)",
            (request.form["name"], request.form["unit"],
             float(request.form["qty"] or 0),
             float(request.form["cost"] or 0),
             float(request.form["price"] or 0))
        )
        c.commit()
    rows = c.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    c.close()
    body = """<div class='panel'><form method='post'>
    <input name='name' placeholder='Mahsulot nomi' required>
    <select name='unit'><option>kg</option><option>dona</option></select>
    <input name='qty' type='number' step='0.01' placeholder='Boshlang‘ich qoldiq'>
    <input name='cost' type='number' step='0.01' placeholder='Tannarx'>
    <input name='price' type='number' step='0.01' placeholder='Sotuv narxi'>
    <button>+ Mahsulot qo‘shish</button></form></div>
    <div class='panel'><table><tr><th>Mahsulot</th><th>Birlik</th>
    <th>Qoldiq</th><th>Tannarx</th><th>Sotuv</th></tr>"""
    body += "".join(
        f"<tr><td>{r['name']}</td><td>{r['unit']}</td><td>{r['qty']}</td>"
        f"<td>{r['cost']:,.0f}</td><td>{r['price']:,.0f}</td></tr>"
        for r in rows
    )
    return page("📦 Ombor", body + "</table></div>")


@app.route("/workers", methods=["GET", "POST"])
def workers():
    c = db()
    if request.method == "POST":
        c.execute(
            "INSERT INTO workers(name,phone) VALUES(?,?)",
            (request.form["name"], request.form["phone"])
        )
        c.commit()
    rows = c.execute("SELECT * FROM workers ORDER BY id DESC").fetchall()
    c.close()
    body = """<div class='panel'><form method='post'>
    <input name='name' placeholder='Ism familiya' required>
    <input name='phone' placeholder='Telefon raqam' required>
    <button>+ Ishchi qo‘shish</button></form></div>
    <div class='panel'><table><tr><th>Ishchi</th><th>Telefon</th>
    <th>Jami berilgan</th><th>Pul berish</th></tr>"""
    for r in rows:
        body += f"""<tr><td>{r['name']}</td><td>{r['phone']}</td>
        <td>{r['paid']:,.0f} so'm</td><td><form method='post' action='/pay/{r['id']}'>
        <input name='amount' type='number' step='0.01' placeholder='Summa' required>
        <input name='note' placeholder='Izoh'><button>+ Pul berish</button>
        </form></td></tr>"""
    return page("👷 Ishchilar", body + "</table></div>")


@app.post("/pay/<int:wid>")
def pay(wid):
    amount = float(request.form["amount"])
    note = request.form.get("note", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = db()
    w = c.execute("SELECT * FROM workers WHERE id=?", (wid,)).fetchone()
    if not w or amount <= 0:
        c.close()
        flash("Ishchi yoki summa noto‘g‘ri.")
        return redirect("/workers")
    c.execute(
        "INSERT INTO payments(worker_id,amount,note,created_at) VALUES(?,?,?,?)",
        (wid, amount, note, now)
    )
    c.execute("UPDATE workers SET paid=paid+? WHERE id=?", (amount, wid))
    c.commit()
    c.close()
    flash(f"{w['name']} ga {amount:,.0f} so'm qayd qilindi.")
    return redirect("/workers")


@app.route("/clients", methods=["GET", "POST"])
def clients():
    c = db()
    if request.method == "POST":
        c.execute(
            "INSERT INTO clients(name,phone) VALUES(?,?)",
            (request.form["name"], request.form["phone"])
        )
        c.commit()
    rows = c.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    body = """<div class='panel'><form method='post'>
    <input name='name' placeholder='Klient nomi' required>
    <input name='phone' placeholder='Telefon'>
    <button>+ Klient qo‘shish</button></form></div>
    <div class='panel'><table><tr><th>Klient</th><th>Telefon</th>
    <th>Qarz</th><th>Pul qabul qilish</th></tr>"""
    for r in rows:
        body += f"""<tr><td>{r['name']}</td><td>{r['phone']}</td>
        <td><b>{r['debt']:,.0f} so'm</b></td><td>
        <form method='post' action='/client-pay/{r['id']}'>
        <input name='amount' type='number' step='0.01' min='0.01'
        placeholder='To‘langan summa' required>
        <input name='note' placeholder='Izoh'>
        <button>💵 Pul qabul qilish</button></form></td></tr>"""
    c.close()
    return page("👥 Klientlar", body + "</table></div>")


@app.post("/client-pay/<int:cid>")
def client_pay(cid):
    amount = float(request.form["amount"])
    note = request.form.get("note", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = db()
    client = c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    if not client:
        c.close()
        flash("Klient topilmadi.")
        return redirect("/clients")
    if amount <= 0 or amount > client["debt"]:
        c.close()
        flash("To‘lov summasi noto‘g‘ri.")
        return redirect("/clients")
    c.execute(
        "INSERT INTO client_payments(client_id,amount,note,created_at) VALUES(?,?,?,?)",
        (cid, amount, note, now)
    )
    c.execute("UPDATE clients SET debt=debt-? WHERE id=?", (amount, cid))
    c.commit()
    c.close()
    flash(f"{client['name']} dan {amount:,.0f} so'm qabul qilindi.")
    return redirect("/clients")


@app.route("/sales", methods=["GET", "POST"])
def sales():
    c = db()

    if request.method == "POST":
        sale_type = request.form.get("sale_type", "stock")
        cid = request.form.get("client_id") or None

        if sale_type == "door":
            width = request.form.get("width", "").strip()
            height = request.form.get("height", "").strip()
            price_raw = request.form.get("door_price", "").strip()
            note = request.form.get("note", "").strip()

            try:
                width_n = float(width)
                height_n = float(height)
                price = float(price_raw)
            except (ValueError, TypeError):
                width_n = height_n = price = -1

            if width_n <= 0 or height_n <= 0 or price <= 0:
                flash("Eshik o‘lchami va narxi noto‘g‘ri.")
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")

                # Eshik tayyor mahsulot emas:
                # ombordagi products qoldig‘i umuman kamaymaydi.
                c.execute(
                    """INSERT INTO sales
                       (product_id,client_id,qty,price,total,created_at)
                       VALUES(NULL,?,?,?,?,?)""",
                    (cid, 1, price, price, now),
                )
                sale_id = c.lastrowid

                c.execute(
                    """INSERT INTO door_sales
                       (sale_id,client_id,width,height,note,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (sale_id, cid, width_n, height_n, note, now),
                )

                if cid:
                    c.execute(
                        "UPDATE clients SET debt=debt+? WHERE id=?",
                        (price, cid),
                    )

                c.commit()
                flash("🚪 Eshik sotuvi muvaffaqiyatli qayd qilindi.")

        else:
            product_id = request.form.get("product_id")
            p = c.execute(
                "SELECT * FROM products WHERE id=?",
                (product_id,),
            ).fetchone()

            try:
                qty = float(request.form.get("qty", 0))
                price = float(
                    request.form.get("stock_price") or p["price"]
                )
            except (ValueError, TypeError, KeyError):
                qty = -1
                price = 0

            if not p:
                flash("Mahsulot topilmadi.")
            elif qty <= 0 or qty > p["qty"]:
                flash("Omborda yetarli qoldiq yo‘q.")
            else:
                total = qty * price
                now = datetime.now().strftime("%Y-%m-%d %H:%M")

                c.execute(
                    "UPDATE products SET qty=qty-? WHERE id=?",
                    (qty, p["id"]),
                )
                c.execute(
                    """INSERT INTO sales
                       (product_id,client_id,qty,price,total,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (p["id"], cid, qty, price, total, now),
                )

                if cid:
                    c.execute(
                        "UPDATE clients SET debt=debt+? WHERE id=?",
                        (total, cid),
                    )

                c.commit()
                flash("Sotuv muvaffaqiyatli qayd qilindi.")

    ps = c.execute(
        "SELECT * FROM products ORDER BY name"
    ).fetchall()
    cs = c.execute(
        "SELECT * FROM clients ORDER BY name"
    ).fetchall()

    stock_sales = c.execute(
        """SELECT s.*,p.name pn,c.name cn
           FROM sales s
           JOIN products p ON p.id=s.product_id
           LEFT JOIN clients c ON c.id=s.client_id
           ORDER BY s.id DESC LIMIT 50"""
    ).fetchall()

    door_sales = c.execute(
        """SELECT d.*,c.name cn,s.price
           FROM door_sales d
           LEFT JOIN clients c ON c.id=d.client_id
           JOIN sales s ON s.id=d.sale_id
           ORDER BY d.id DESC LIMIT 50"""
    ).fetchall()

    c.close()

    body = """<div class='panel'>
    <h3>🧾 Sotuv qo‘shish</h3>
    <form method='post'>

    <select name='sale_type'
      onchange=\"this.form.querySelector('.stock-fields').style.display=this.value==='stock'?'block':'none';this.form.querySelector('.door-fields').style.display=this.value==='door'?'block':'none';\">
      <option value='stock'>📦 Ombordagi mahsulot</option>
      <option value='door'>🚪 Eshik</option>
    </select>

    <select name='client_id'>
      <option value=''>Klientsiz</option>"""

    body += "".join(
        f"<option value='{c['id']}'>{c['name']}</option>"
        for c in cs
    )

    body += """</select>

    <div class='stock-fields'>
      <select name='product_id'>"""

    body += "".join(
        f"<option value='{p['id']}'>{p['name']} ({p['qty']} {p['unit']})</option>"
        for p in ps
    )

    body += """</select>
      <input name='qty' type='number' step='0.01' placeholder='Miqdor'>
      <input name='stock_price' type='number' step='0.01' placeholder='Narx'>
    </div>

    <div class='door-fields' style='display:none'>
      <input name='width' type='number' step='0.01' placeholder='Eshik eni (mm)'>
      <input name='height' type='number' step='0.01' placeholder='Eshik bo‘yi (mm)'>
      <input name='door_price' type='number' step='0.01' placeholder='Eshik narxi'>
      <input name='note' placeholder='Izoh (rang, model va h.k.)'>
    </div>

    <button>✅ Sotuvni saqlash</button>
    </form>
    </div>

    <div class='panel'>
    <h3>🚪 Eshik sotuvlari</h3>
    <table>
    <tr><th>Sana</th><th>O‘lcham</th><th>Klient</th><th>Summa</th><th>Izoh</th></tr>"""

    body += "".join(
        f"<tr><td>{r['created_at']}</td>"
        f"<td>{r['width']:g} × {r['height']:g} mm</td>"
        f"<td>{r['cn'] or ''}</td>"
        f"<td>{r['price']:,.0f} so‘m</td>"
        f"<td>{r['note'] or ''}</td></tr>"
        for r in door_sales
    )

    body += """</table>
    </div>

    <div class='panel'>
    <h3>📦 Ombor mahsuloti sotuvlari</h3>
    <table>
    <tr><th>Sana</th><th>Mahsulot</th><th>Miqdor</th><th>Klient</th><th>Summa</th></tr>"""

    body += "".join(
        f"<tr><td>{s['created_at']}</td>"
        f"<td>{s['pn']}</td>"
        f"<td>{s['qty']}</td>"
        f"<td>{s['cn'] or ''}</td>"
        f"<td>{s['total']:,.0f} so‘m</td></tr>"
        for s in stock_sales
    )

    body += "</table></div>"

    return page("🧾 Sotuv", body)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
