import re
import uuid
from pathlib import Path

from flask import current_app, url_for
from werkzeug.utils import secure_filename

from app.database import (
    commit,
    fetch_all,
    fetch_one,
    fetch_value,
    is_duplicate_key,
    is_duplicate_key_for,
    transaction,
)
from app.utils.formatters import format_short_date
from app.utils.validators import normalize_menu_code


MIN_MENU_PRICE = 500
CATEGORY_NAME_MAX_LENGTH = 100
MAX_CODE_RETRIES = 5
MENU_NAME_CREATE_DUPLICATE = "Nama menu sudah digunakan. Gunakan nama menu yang berbeda."
MENU_NAME_EDIT_DUPLICATE = "Nama menu sudah digunakan oleh menu lain."
MENU_NAME_CONCURRENT_DUPLICATE = "Nama menu sudah digunakan. Silakan gunakan nama lain."


def clean_menu_name(value):
    """Collapse whitespace while preserving the display capitalization."""
    return " ".join(str(value or "").strip().split())


def normalize_menu_name(value):
    """Canonical key: case-insensitive and independent of whitespace count."""
    return "".join(clean_menu_name(value).lower().split())


def find_menu_by_normalized_name(normalized_name, exclude_id=None):
    """Find a duplicate, including legacy rows not backfilled by the migration."""
    params = [normalized_name]
    exclude_sql = ""
    if exclude_id is not None:
        exclude_sql = " AND id <> %s"
        params.append(exclude_id)

    duplicate = fetch_one(
        f"""
        SELECT id, name, code
        FROM menus
        WHERE normalized_name = %s{exclude_sql}
        LIMIT 1
        """,
        tuple(params),
    )
    if duplicate:
        return duplicate

    # During a staged migration, legacy keys may be NULL or may use an older
    # normalization rule. Recheck every remaining row with the current helper.
    legacy_rows = fetch_all(
        f"""
        SELECT id, name, code
        FROM menus
        WHERE (normalized_name IS NULL OR normalized_name <> %s){exclude_sql}
        """,
        tuple(params),
    )
    return next(
        (row for row in legacy_rows if normalize_menu_name(row.get("name")) == normalized_name),
        None,
    )


def save_menu_image(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return "", None
    extension = Path(uploaded_file.filename).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        return "", "Format gambar tidak valid. Gunakan PNG, JPG, JPEG, atau WEBP."

    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")
    if cloud_name and api_key and api_secret:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
            public_id = f"{Path(secure_filename(uploaded_file.filename)).stem}-{uuid.uuid4().hex[:12]}"
            result = cloudinary.uploader.upload(
                uploaded_file.stream,
                public_id=public_id,
                folder=current_app.config.get("CLOUDINARY_FOLDER") or None,
                resource_type="image",
                overwrite=False,
            )
            return result.get("secure_url") or result.get("url"), None
        except Exception:
            current_app.logger.exception("Upload Cloudinary gagal.")
            return "", "Gagal mengunggah gambar ke Cloudinary. Periksa konfigurasi .env Anda."

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{secure_filename(uploaded_file.filename)}"
    uploaded_file.save(upload_folder / filename)
    return f"uploads/menu/{filename}", None


def menu_image_url(image_path):
    value = str(image_path or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "//")):
        return value
    return url_for("static", filename=value.lstrip("/"))


def normalize_category_name(value):
    return " ".join(str(value or "").strip().split())


def category_key(value):
    return normalize_category_name(value).lower()


def get_category_by_id(category_id):
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return None
    return fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))


def get_category_by_name(name):
    return fetch_one("SELECT * FROM categories WHERE name_key = %s", (category_key(name),))


def get_category(category_id=None, category_name=None):
    return get_category_by_id(category_id) or (get_category_by_name(category_name) if category_name else None)


def category_options():
    return fetch_all("SELECT id, name, description FROM categories ORDER BY LOWER(name), id")


def validate_category(data, exclude_id=None):
    name = normalize_category_name(data.get("name"))
    description = str(data.get("description") or "").strip() or None
    errors = {}
    if not name:
        errors["name"] = "Nama kategori wajib diisi."
    elif len(name) > CATEGORY_NAME_MAX_LENGTH:
        errors["name"] = f"Nama kategori maksimal {CATEGORY_NAME_MAX_LENGTH} karakter."
    else:
        duplicate = get_category_by_name(name)
        if duplicate and int(duplicate["id"]) != int(exclude_id or 0):
            errors["name"] = "Nama kategori sudah digunakan."
    return {"name": name, "description": description}, errors


def create_category(data):
    payload, errors = validate_category(data)
    if errors:
        return None, payload, errors
    try:
        cursor = commit(
            "INSERT INTO categories (name, name_key, description) VALUES (%s, %s, %s)",
            (payload["name"], category_key(payload["name"]), payload["description"]),
        )
        return get_category_by_id(cursor.lastrowid), payload, {}
    except Exception as exc:
        if is_duplicate_key(exc):
            return None, payload, {"name": "Nama kategori sudah digunakan."}
        raise


def update_category(category_id, data):
    payload, errors = validate_category(data, exclude_id=category_id)
    if errors:
        return None, payload, errors
    try:
        with transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE categories
                SET name = %s, name_key = %s, description = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (payload["name"], category_key(payload["name"]), payload["description"], category_id),
            )
            cursor.execute("UPDATE menus SET category = %s WHERE category_id = %s", (payload["name"], category_id))
    except Exception as exc:
        if is_duplicate_key(exc):
            return None, payload, {"name": "Nama kategori sudah digunakan."}
        raise
    return get_category_by_id(category_id), payload, {}


def delete_category(category_id):
    count = int(fetch_value("SELECT COUNT(*) FROM menus WHERE category_id = %s", (category_id,), 0) or 0)
    if count:
        return f"Kategori ini masih digunakan oleh {count} menu. Pindahkan menu sebelum menghapus kategori."
    commit("DELETE FROM categories WHERE id = %s", (category_id,))
    return None


def list_categories(search=""):
    where = ""
    params = ()
    if search:
        where = "WHERE c.name LIKE %s OR COALESCE(c.description, '') LIKE %s"
        keyword = f"%{search}%"
        params = (keyword, keyword)
    rows = fetch_all(
        f"""
        SELECT c.id, c.name, c.description, c.created_at, c.updated_at, COUNT(m.id) AS menu_count
        FROM categories c
        LEFT JOIN menus m ON m.category_id = c.id
        {where}
        GROUP BY c.id, c.name, c.description, c.created_at, c.updated_at
        ORDER BY LOWER(c.name), c.id
        """,
        params,
    )
    for row in rows:
        row["created_label"] = format_short_date(row.get("created_at"))
        row["description"] = row.get("description") or ""
        row["menu_count"] = int(row.get("menu_count") or 0)
    return rows


def parse_menu_price(value):
    try:
        price = int(value)
    except (TypeError, ValueError):
        raise ValueError("Harga satuan harus berupa angka minimal Rp 500 dan kelipatan Rp 500.")
    if price < MIN_MENU_PRICE or price % MIN_MENU_PRICE:
        raise ValueError("Harga satuan harus berupa angka minimal Rp 500 dan kelipatan Rp 500.")
    return price


def build_code_prefix(category, name=""):
    source = str(category or name or "Menu").upper()
    words = re.sub(r"[^A-Z0-9]+", " ", source).strip().split()
    prefix = re.sub(r"[^A-Z0-9]", "", words[0] if words else "MNU")[:3]
    return (prefix or "MNU").ljust(3, "X")


def validate_menu_payload(data, *, require_stock=False, exclude_id=None):
    name = clean_menu_name(data.get("name"))
    normalized_name = normalize_menu_name(name)
    category = get_category(data.get("category_id"), data.get("category"))
    errors = []
    if not name:
        errors.append("Nama item wajib diisi.")
    elif find_menu_by_normalized_name(normalized_name, exclude_id=exclude_id):
        errors.append(MENU_NAME_EDIT_DUPLICATE if exclude_id is not None else MENU_NAME_CREATE_DUPLICATE)
    if not category:
        errors.append("Kategori wajib dipilih dan harus valid.")
    try:
        price = parse_menu_price(data.get("price"))
    except ValueError as exc:
        price = None
        errors.append(str(exc))
    stock = data.get("stock", 0)
    try:
        stock = int(stock)
        if stock < 0:
            raise ValueError
    except (TypeError, ValueError):
        stock = None
        errors.append("Stok harus berupa angka nol atau lebih.")
    if require_stock and data.get("stock") in (None, ""):
        errors.append("Stok wajib diisi.")
    description = str(data.get("description") or "").strip()
    if require_stock and not description:
        errors.append("Deskripsi wajib diisi.")
    return {
        "name": name,
        "normalized_name": normalized_name,
        "category": category,
        "price": price,
        "stock": stock,
        "description": description,
        "image": str(data.get("image") or ""),
        "is_active": bool(data.get("is_active", True)),
        "code": normalize_menu_code(data.get("code")),
    }, errors


def _insert_menu(cursor, payload, code):
    cursor.execute(
        """
        INSERT INTO menus (
            name, normalized_name, category, category_id, code, price, stock, description, image, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            payload["name"],
            payload["normalized_name"],
            payload["category"]["name"],
            payload["category"]["id"],
            code,
            payload["price"],
            payload["stock"],
            payload["description"],
            payload["image"],
            1 if payload["is_active"] else 0,
        ),
    )
    return cursor.lastrowid


def create_menu(data, *, require_stock=False):
    payload, errors = validate_menu_payload(data, require_stock=require_stock)
    if errors:
        return None, payload, errors

    manual_code = payload["code"]
    if manual_code:
        try:
            with transaction() as connection:
                menu_id = _insert_menu(connection.cursor(), payload, manual_code)
            return get_menu(menu_id), payload, []
        except Exception as exc:
            if is_duplicate_key_for(exc, "uq_menus_normalized_name"):
                return None, payload, [MENU_NAME_CONCURRENT_DUPLICATE]
            if is_duplicate_key(exc):
                return None, payload, ["Kode menu sudah digunakan. Gunakan kode lain."]
            raise

    prefix = build_code_prefix(payload["category"]["name"], payload["name"])
    for _attempt in range(MAX_CODE_RETRIES):
        try:
            with transaction() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO menu_code_sequences (prefix, next_value)
                    VALUES (%s, 1)
                    ON DUPLICATE KEY UPDATE prefix = VALUES(prefix)
                    """,
                    (prefix,),
                )
                cursor.execute("SELECT next_value FROM menu_code_sequences WHERE prefix = %s FOR UPDATE", (prefix,))
                number = int(cursor.fetchone()["next_value"])
                cursor.execute(
                    "UPDATE menu_code_sequences SET next_value = %s WHERE prefix = %s",
                    (number + 1, prefix),
                )
                code = f"{prefix}-{number:03d}"
                menu_id = _insert_menu(cursor, payload, code)
            return get_menu(menu_id), payload, []
        except Exception as exc:
            if is_duplicate_key_for(exc, "uq_menus_normalized_name"):
                return None, payload, [MENU_NAME_CONCURRENT_DUPLICATE]
            if is_duplicate_key(exc):
                current_app.logger.warning("Benturan kode menu %s; mencoba ulang.", code)
                continue
            raise
    return None, payload, ["Gagal membuat kode menu unik setelah 5 percobaan."]


def get_menu(menu_id):
    return fetch_one(
        """
        SELECT m.*, COALESCE(c.name, m.category) AS category_name
        FROM menus m LEFT JOIN categories c ON c.id = m.category_id
        WHERE m.id = %s
        """,
        (menu_id,),
    )


def update_menu(menu_id, data, *, require_stock=False):
    existing = get_menu(menu_id)
    if not existing:
        return None, {}, ["Menu tidak ditemukan."]
    merged = {
        "name": existing.get("name"),
        "category_id": existing.get("category_id"),
        "category": existing.get("category_name") or existing.get("category"),
        "code": existing.get("code"),
        "price": existing.get("price"),
        "stock": existing.get("stock"),
        "description": existing.get("description"),
        "image": existing.get("image"),
        "is_active": bool(existing.get("is_active")),
    }
    merged.update(data)
    payload, errors = validate_menu_payload(merged, require_stock=require_stock, exclude_id=menu_id)
    if errors:
        return None, payload, errors
    code = payload["code"] or normalize_menu_code(existing["code"])
    try:
        commit(
            """
            UPDATE menus
            SET name = %s, normalized_name = %s, category = %s, category_id = %s, code = %s, price = %s,
                stock = %s, description = %s, image = %s, is_active = %s
            WHERE id = %s
            """,
            (
                payload["name"],
                payload["normalized_name"],
                payload["category"]["name"],
                payload["category"]["id"],
                code,
                payload["price"],
                payload["stock"],
                payload["description"],
                payload["image"],
                1 if payload["is_active"] else 0,
                menu_id,
            ),
        )
    except Exception as exc:
        if is_duplicate_key_for(exc, "uq_menus_normalized_name"):
            return None, payload, [MENU_NAME_CONCURRENT_DUPLICATE]
        if is_duplicate_key(exc):
            return None, payload, ["Kode menu sudah digunakan. Gunakan kode lain."]
        raise
    return get_menu(menu_id), payload, []


def list_menus(page=1, per_page=8, search="", category_id=None):
    where_parts = []
    params = []
    if search:
        where_parts.append("(m.name LIKE %s OR COALESCE(c.name, m.category) LIKE %s OR m.code LIKE %s)")
        keyword = f"%{search}%"
        params.extend([keyword, keyword, keyword])
    if category_id:
        where_parts.append("m.category_id = %s")
        params.append(category_id)
    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    total = int(
        fetch_value(
            f"SELECT COUNT(*) FROM menus m LEFT JOIN categories c ON c.id = m.category_id {where}",
            tuple(params),
            0,
        )
        or 0
    )
    rows = fetch_all(
        f"""
        SELECT m.id, m.name, COALESCE(c.name, m.category) AS category, m.category_id,
               m.code, m.price, m.stock, m.description, m.image, m.is_active
        FROM menus m
        LEFT JOIN categories c ON c.id = m.category_id
        {where}
        ORDER BY m.id DESC
        LIMIT %s OFFSET %s
        """,
        (*params, per_page, (page - 1) * per_page),
    )
    return rows, total
