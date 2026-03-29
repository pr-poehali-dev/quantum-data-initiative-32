import json
import os
import hashlib
import psycopg2
import random
import requests
from urllib.parse import urlencode
from datetime import datetime

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
}

CATALOG = [
    {"id": "1", "name": "Аметист", "price": 890.0, "emoji": "💜"},
    {"id": "2", "name": "Розовый кварц", "price": 650.0, "emoji": "🌸"},
    {"id": "3", "name": "Горный хрусталь", "price": 750.0, "emoji": "🔮"},
    {"id": "4", "name": "Обсидиан", "price": 550.0, "emoji": "🖤"},
    {"id": "5", "name": "Цитрин", "price": 980.0, "emoji": "🌟"},
    {"id": "6", "name": "Селенит", "price": 420.0, "emoji": "🤍"},
]

def tg(token, method, data):
    url = TELEGRAM_API.format(token=token, method=method)
    resp = requests.post(url, json=data, timeout=10)
    return resp.json()

def send_message(token, chat_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = reply_markup
    return tg(token, "sendMessage", data)

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def calculate_signature(*args):
    joined = ':'.join(str(a) for a in args)
    return hashlib.md5(joined.encode()).hexdigest()

def create_payment(user_name, user_email, user_phone, user_address, cart_items, amount):
    merchant_login = os.environ.get("ROBOKASSA_MERCHANT_LOGIN")
    password_1 = os.environ.get("ROBOKASSA_PASSWORD_1")
    if not merchant_login or not password_1:
        return None, None, "Robokassa не настроена"

    conn = get_db()
    cur = conn.cursor()

    for _ in range(10):
        inv_id = random.randint(100000, 2147483647)
        cur.execute("SELECT COUNT(*) FROM orders WHERE robokassa_inv_id = %s", (inv_id,))
        if cur.fetchone()[0] == 0:
            break

    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{inv_id}"

    cur.execute("""
        INSERT INTO orders (order_number, user_name, user_email, user_phone, amount, robokassa_inv_id, status, delivery_address)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s) RETURNING id
    """, (order_number, user_name, user_email, user_phone, round(amount, 2), inv_id, user_address))
    order_id = cur.fetchone()[0]

    for item in cart_items:
        cur.execute("""
            INSERT INTO order_items (order_id, product_id, product_name, product_price, quantity)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, item["id"], item["name"], item["price"], item["quantity"]))

    amount_str = f"{amount:.2f}"
    signature = calculate_signature(merchant_login, amount_str, inv_id, password_1)
    params = {
        "MerchantLogin": merchant_login,
        "OutSum": amount_str,
        "InvoiceID": inv_id,
        "SignatureValue": signature,
        "Email": user_email,
        "Culture": "ru",
        "Description": f"Заказ {order_number}"
    }
    payment_url = f"https://auth.robokassa.ru/Merchant/Index.aspx?{urlencode(params)}"

    cur.execute("UPDATE orders SET payment_url = %s WHERE id = %s", (payment_url, order_id))
    conn.commit()
    cur.close()
    conn.close()

    return payment_url, order_number, None

def get_state(chat_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT state, data FROM bot_sessions WHERE chat_id = %s
    """, (str(chat_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0], json.loads(row[1]) if row[1] else {}
    return "start", {}

def set_state(chat_id, state, data=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bot_sessions (chat_id, state, data, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (chat_id) DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, updated_at = NOW()
    """, (str(chat_id), state, json.dumps(data or {}, ensure_ascii=False)))
    conn.commit()
    cur.close()
    conn.close()

def catalog_keyboard():
    buttons = [[{"text": f"{p['emoji']} {p['name']} — {int(p['price'])} ₽"}] for p in CATALOG]
    buttons.append([{"text": "🛒 Оформить заказ"}])
    return {"keyboard": buttons, "resize_keyboard": True}

def handle_update(token, update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    state, data = get_state(chat_id)

    if text == "/start":
        set_state(chat_id, "catalog", {"cart": []})
        send_message(token, chat_id,
            "👋 Привет! Добро пожаловать в <b>CRYSTALIA</b> — магазин натуральных кристаллов.\n\n"
            "Выбери кристалл из каталога и добавь в корзину:",
            catalog_keyboard()
        )
        return

    if text == "/cart" or text == "🛒 Оформить заказ":
        cart = data.get("cart", [])
        if not cart:
            send_message(token, chat_id, "🛒 Корзина пуста. Выбери кристаллы из каталога!")
            return
        lines = ["🛒 <b>Твоя корзина:</b>\n"]
        total = 0
        for item in cart:
            subtotal = item["price"] * item["quantity"]
            total += subtotal
            lines.append(f"• {item['name']} × {item['quantity']} = {int(subtotal)} ₽")
        lines.append(f"\n<b>Итого: {int(total)} ₽</b>")
        lines.append("\nДля оформления введи своё <b>имя</b>:")
        set_state(chat_id, "awaiting_name", data)
        send_message(token, chat_id, "\n".join(lines),
            {"keyboard": [[{"text": "❌ Отмена"}]], "resize_keyboard": True})
        return

    if text == "❌ Отмена":
        set_state(chat_id, "catalog", {"cart": data.get("cart", [])})
        send_message(token, chat_id, "Отменено. Возвращаемся в каталог.", catalog_keyboard())
        return

    product_match = next((p for p in CATALOG if f"{p['emoji']} {p['name']} — {int(p['price'])} ₽" == text), None)
    if product_match and state in ("catalog", "start"):
        cart = data.get("cart", [])
        existing = next((i for i in cart if i["id"] == product_match["id"]), None)
        if existing:
            existing["quantity"] += 1
        else:
            cart.append({"id": product_match["id"], "name": product_match["name"],
                         "price": product_match["price"], "quantity": 1})
        data["cart"] = cart
        set_state(chat_id, "catalog", data)
        total = sum(i["price"] * i["quantity"] for i in cart)
        send_message(token, chat_id,
            f"✅ <b>{product_match['name']}</b> добавлен в корзину!\n"
            f"В корзине: {sum(i['quantity'] for i in cart)} шт. на <b>{int(total)} ₽</b>\n\n"
            "Продолжи выбор или нажми <b>🛒 Оформить заказ</b>",
            catalog_keyboard()
        )
        return

    if state == "awaiting_name":
        data["name"] = text
        set_state(chat_id, "awaiting_phone", data)
        send_message(token, chat_id, f"Отлично, <b>{text}</b>! Введи номер телефона:")
        return

    if state == "awaiting_phone":
        data["phone"] = text
        set_state(chat_id, "awaiting_email", data)
        send_message(token, chat_id, "Введи email для чека:")
        return

    if state == "awaiting_email":
        data["email"] = text
        set_state(chat_id, "awaiting_address", data)
        send_message(token, chat_id, "Введи адрес доставки:")
        return

    if state == "awaiting_address":
        data["address"] = text
        cart = data.get("cart", [])
        total = sum(i["price"] * i["quantity"] for i in cart)

        payment_url, order_number, error = create_payment(
            user_name=data.get("name", ""),
            user_email=data.get("email", ""),
            user_phone=data.get("phone", ""),
            user_address=text,
            cart_items=cart,
            amount=total
        )

        if error:
            send_message(token, chat_id, f"❌ Ошибка при создании заказа: {error}")
            return

        set_state(chat_id, "catalog", {"cart": []})
        lines = [
            f"🎉 <b>Заказ {order_number} оформлен!</b>\n",
            f"👤 {data.get('name')}",
            f"📱 {data.get('phone')}",
            f"📧 {data.get('email')}",
            f"📦 {text}\n",
        ]
        for item in cart:
            lines.append(f"• {item['name']} × {item['quantity']} = {int(item['price'] * item['quantity'])} ₽")
        lines.append(f"\n💰 <b>Итого: {int(total)} ₽</b>")
        lines.append(f"\n👇 Нажми кнопку ниже для оплаты:")

        send_message(token, chat_id, "\n".join(lines), {
            "inline_keyboard": [[{"text": f"💳 Оплатить {int(total)} ₽", "url": payment_url}]]
        })
        return

    send_message(token, chat_id,
        "Выбери кристалл из каталога или нажми /start чтобы начать заново.",
        catalog_keyboard()
    )

def handler(event: dict, context) -> dict:
    """
    Webhook для Telegram-бота CRYSTALIA.
    Принимает обновления от Telegram и обрабатывает заказы от покупателей.
    """
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": HEADERS, "body": "", "isBase64Encoded": False}

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"statusCode": 500, "headers": HEADERS,
                "body": json.dumps({"error": "TELEGRAM_BOT_TOKEN not set"}), "isBase64Encoded": False}

    try:
        body = json.loads(event.get("body", "{}"))
        handle_update(token, body)
    except Exception as e:
        import traceback
        print(f"Bot error: {e}\n{traceback.format_exc()}")

    return {"statusCode": 200, "headers": HEADERS, "body": json.dumps({"ok": True}), "isBase64Encoded": False}
