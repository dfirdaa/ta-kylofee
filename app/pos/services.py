import uuid

from flask import session

from app.database import fetch_all, fetch_one, get_db
from app.utils.formatters import format_currency, format_short_date
from app.utils.timezone import jakarta_now_naive, transaction_datetime_jakarta


def parse_amount(value, label):
    if value in (None, ""):
        return 0
    try:
        amount = int(str(value).strip().replace(".", "").replace(",", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{label} harus berupa angka.")
    if amount < 0:
        raise ValueError(f"{label} tidak boleh negatif.")
    return amount


def normalize_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Keranjang masih kosong.")
    items = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("Data item POS tidak valid.")
        try:
            menu_id = int(raw.get("menu_id"))
            quantity = int(raw.get("quantity", 1))
        except (TypeError, ValueError):
            raise ValueError("Data item POS tidak valid.")
        if menu_id < 1 or quantity < 1 or quantity > 999:
            raise ValueError("Jumlah item POS tidak valid.")
        items[menu_id] = items.get(menu_id, 0) + quantity
    return items


def generate_order_code(now=None):
    now = now or jakarta_now_naive()
    return f"POS-{now:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}"


def generate_invoice_code(now=None):
    now = now or jakarta_now_naive()
    return f"INV{now:%Y%m%d%H%M%S}{uuid.uuid4().hex[:3].upper()}"


def normalize_order_code(value):
    value = str(value or "").strip().upper()
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    return "".join(character for character in value if character in allowed)[:60]


def build_qris_payload(order_code, total_amount, timestamp):
    return f"ORDER={order_code}\nTOTAL={int(total_amount or 0)}\nTIME={timestamp}"


def current_shift():
    hour = jakarta_now_naive().hour
    return "Pagi" if 5 <= hour < 12 else "Siang" if 12 <= hour < 17 else "Malam"


def list_active_menus():
    return fetch_all(
        """
        SELECT m.id, m.code, m.name, m.description, m.price, m.image, m.stock,
               COALESCE(c.name, m.category) AS category, m.category_id, m.is_active
        FROM menus m
        LEFT JOIN categories c ON c.id = m.category_id
        WHERE m.is_active = 1
        ORDER BY m.id DESC
        """
    )


def category_filters(products):
    return sorted(
        {str(product.get("category") or "").strip() for product in products if product.get("category")},
        key=str.casefold,
    )


def create_transaction(data):
    items = normalize_items(data.get("items"))
    customer_name = str(data.get("customer_name") or "").strip() or "Walk-in Customer"
    method_key = str(data.get("payment_method") or "Tunai").strip().lower()
    if method_key in {"tunai", "cash"}:
        payment_method = "Cash"
    elif method_key == "qris":
        payment_method = "QRIS"
    else:
        raise ValueError("Metode pembayaran hanya boleh Cash atau QRIS.")

    discount = parse_amount(data.get("discount_amount"), "Diskon")
    placeholders = ", ".join(["%s"] * len(items))
    rows = fetch_all(
        f"SELECT id, code, name, price, stock, is_active FROM menus WHERE id IN ({placeholders})",
        tuple(items.keys()),
    )
    menu_map = {int(row["id"]): row for row in rows}
    prepared = []
    subtotal = 0
    item_count = 0

    for menu_id, quantity in items.items():
        menu = menu_map.get(menu_id)
        if not menu:
            raise ValueError(f"Menu ID {menu_id} tidak ditemukan.")
        name = menu.get("name") or "Menu"
        stock = int(menu.get("stock") or 0)
        if int(menu.get("is_active") or 0) != 1:
            raise ValueError(f"{name} sedang nonaktif.")
        if quantity > stock:
            raise ValueError(f"Stok {name} tidak cukup. Tersedia {stock}.")
        unit_price = int(menu.get("price") or 0)
        line_total = unit_price * quantity
        subtotal += line_total
        item_count += quantity
        prepared.append(
            {
                "menu_id": menu_id,
                "menu_code": menu.get("code"),
                "menu_name": name,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": line_total,
                "stock": stock,
            }
        )

    if discount > subtotal:
        raise ValueError("Diskon tidak boleh lebih besar dari subtotal.")
    total = subtotal - discount
    if payment_method == "Cash" and parse_amount(data.get("received_amount"), "Nominal diterima") < total:
        raise ValueError("Nominal diterima kurang dari total pembayaran.")

    now = jakarta_now_naive()
    order_code = normalize_order_code(data.get("order_code")) or generate_order_code(now)
    connection = get_db()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO pos_transactions (
                order_code, transaction_date, transaction_time, customer_name, payment_method,
                subtotal_amount, discount_amount, tax_amount, operational_cost, total_amount,
                item_count, status, owner_id, staff_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s, %s, 'Selesai', %s, %s)
            """,
            (
                order_code,
                now.date(),
                now.time().replace(microsecond=0),
                customer_name,
                payment_method,
                subtotal,
                discount,
                total,
                item_count,
                session.get("owner_id"),
                session.get("user_id"),
            ),
        )
        transaction_id = cursor.lastrowid
        for item in prepared:
            cursor.execute(
                "UPDATE menus SET stock = stock - %s WHERE id = %s AND stock >= %s AND is_active = 1",
                (item["quantity"], item["menu_id"], item["quantity"]),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Stok {item['menu_name']} baru saja berubah. Silakan cek ulang keranjang.")
            cursor.execute(
                """
                INSERT INTO pos_transaction_items (
                    transaction_id, menu_id, menu_code, menu_name, quantity, unit_price, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    item["menu_id"],
                    item["menu_code"],
                    item["menu_name"],
                    item["quantity"],
                    item["unit_price"],
                    item["subtotal"],
                ),
            )
            item["stock_remaining"] = item["stock"] - item["quantity"]
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "order_code": order_code,
        "subtotal_amount": subtotal,
        "discount_amount": discount,
        "total_amount": total,
        "item_count": item_count,
        "items": prepared,
    }


def remember_payment(order_code, method, total, received=None, change=None):
    received = int(received if received is not None else total)
    session["last_payment"] = {
        "order_code": order_code,
        "payment_method": method,
        "received_amount": received,
        "change_amount": int(change if change is not None else max(received - total, 0)),
    }


def payment_details(order_code, transaction):
    stored = session.get("last_payment") or {}
    if stored.get("order_code") == order_code:
        return {
            "method": stored.get("payment_method") or transaction.get("payment_method"),
            "received_amount": int(stored.get("received_amount") or 0),
            "change_amount": int(stored.get("change_amount") or 0),
        }
    total = int(transaction.get("total_amount") or 0)
    return {"method": transaction.get("payment_method"), "received_amount": total, "change_amount": 0}


def transaction_detail(order_code):
    transaction = fetch_one(
        """
        SELECT t.*, u.full_name AS staff_name
        FROM pos_transactions t
        LEFT JOIN users u ON u.id = t.staff_id
        WHERE t.order_code = %s
        """,
        (order_code,),
    )
    if not transaction:
        return None
    items = fetch_all(
        """
        SELECT menu_id, menu_code, menu_name, quantity, unit_price, subtotal
        FROM pos_transaction_items
        WHERE transaction_id = %s
        ORDER BY id
        """,
        (transaction["id"],),
    )
    local_datetime = transaction_datetime_jakarta(
        transaction.get("transaction_date"),
        transaction.get("transaction_time"),
        transaction.get("created_at"),
    )
    transaction["date_display"] = format_short_date(
        local_datetime.date() if local_datetime else transaction.get("transaction_date")
    )
    transaction["time_display"] = (
        local_datetime.strftime("%H:%M")
        if local_datetime
        else str(transaction.get("transaction_time") or "")[:5]
    )
    transaction["total_display"] = format_currency(transaction.get("total_amount"))
    transaction["subtotal_display"] = format_currency(transaction.get("subtotal_amount"))
    for item in items:
        item["unit_price_display"] = format_currency(item.get("unit_price"))
        item["subtotal_display"] = format_currency(item.get("subtotal"))
    transaction["items"] = items
    return transaction
