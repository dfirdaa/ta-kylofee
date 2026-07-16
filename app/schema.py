import re
from threading import Lock

from flask import current_app

from app.database import commit, execute, fetch_all, fetch_one, fetch_value, get_db, transaction
from app.menu.services import normalize_category_name, normalize_menu_name
from app.utils.validators import normalize_menu_code


_schema_lock = Lock()


CREATE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        full_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL,
        password_hash TEXT NOT NULL,
        role VARCHAR(50) NOT NULL,
        owner_id BIGINT NULL,
        staff_phone VARCHAR(40) NULL,
        staff_position VARCHAR(100) DEFAULT 'Kasir',
        joined_date DATE NULL,
        staff_status VARCHAR(40) DEFAULT 'active',
        is_active TINYINT NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        name_key VARCHAR(255) NOT NULL,
        normalized_name VARCHAR(255) NULL,
        description TEXT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS menus (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL,
        normalized_name VARCHAR(255) NULL,
        category VARCHAR(100) NOT NULL,
        category_id BIGINT NULL,
        code VARCHAR(100) NOT NULL,
        price BIGINT NOT NULL,
        stock INT NOT NULL DEFAULT 0,
        description TEXT NULL,
        image TEXT NULL,
        is_active TINYINT NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS menu_code_sequences (
        prefix VARCHAR(16) PRIMARY KEY,
        next_value BIGINT NOT NULL DEFAULT 1,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cashier_invitations (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        owner_id BIGINT NOT NULL,
        invite_code VARCHAR(64) NOT NULL,
        status VARCHAR(40) NOT NULL DEFAULT 'Aktif',
        expires_at DATETIME NULL,
        used_at DATETIME NULL,
        used_by_cashier_id BIGINT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pos_transactions (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        order_code VARCHAR(60) NOT NULL,
        transaction_date DATE NOT NULL,
        transaction_time TIME NOT NULL,
        customer_name VARCHAR(255) DEFAULT 'Walk-in Customer',
        payment_method VARCHAR(80) DEFAULT 'Tunai',
        subtotal_amount BIGINT NOT NULL DEFAULT 0,
        discount_amount BIGINT NOT NULL DEFAULT 0,
        tax_amount BIGINT NOT NULL DEFAULT 0,
        operational_cost BIGINT NOT NULL DEFAULT 0,
        total_amount BIGINT NOT NULL DEFAULT 0,
        item_count INT NOT NULL DEFAULT 0,
        status VARCHAR(40) NOT NULL DEFAULT 'Selesai',
        owner_id BIGINT NULL,
        staff_id BIGINT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pos_transaction_items (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        transaction_id BIGINT NOT NULL,
        menu_id BIGINT NULL,
        menu_code VARCHAR(100) NULL,
        menu_name VARCHAR(255) NOT NULL,
        quantity INT NOT NULL DEFAULT 1,
        unit_price BIGINT NOT NULL DEFAULT 0,
        subtotal BIGINT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


REQUIRED_COLUMNS = {
    "users": {
        "owner_id": "BIGINT NULL",
        "staff_phone": "VARCHAR(40) NULL",
        "staff_position": "VARCHAR(100) DEFAULT 'Kasir'",
        "joined_date": "DATE NULL",
        "staff_status": "VARCHAR(40) DEFAULT 'active'",
        "is_active": "TINYINT NOT NULL DEFAULT 1",
        "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "categories": {
        "name_key": "VARCHAR(255) NULL",
        "normalized_name": "VARCHAR(255) NULL",
        "description": "TEXT NULL",
        "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "menus": {
        "name": "VARCHAR(255) NULL",
        "normalized_name": "VARCHAR(255) NULL",
        "category": "VARCHAR(100) NULL",
        "category_id": "BIGINT NULL",
        "code": "VARCHAR(100) NULL",
        "price": "BIGINT NOT NULL DEFAULT 0",
        "stock": "INT NOT NULL DEFAULT 0",
        "description": "TEXT NULL",
        "image": "TEXT NULL",
        "is_active": "TINYINT NOT NULL DEFAULT 1",
        "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "cashier_invitations": {
        "used_at": "DATETIME NULL",
        "used_by_cashier_id": "BIGINT NULL",
    },
    "pos_transactions": {
        "owner_id": "BIGINT NULL",
        "staff_id": "BIGINT NULL",
        "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "pos_transaction_items": {
        "menu_code": "VARCHAR(100) NULL",
    },
}


INDEXES = (
    ("users", "uq_users_email", "CREATE UNIQUE INDEX uq_users_email ON users (email)"),
    ("users", "idx_users_role", "CREATE INDEX idx_users_role ON users (role)"),
    ("menus", "uq_menus_code", "CREATE UNIQUE INDEX uq_menus_code ON menus (code)"),
    ("menus", "idx_menus_category_id", "CREATE INDEX idx_menus_category_id ON menus (category_id)"),
    (
        "cashier_invitations",
        "uq_cashier_invitations_code",
        "CREATE UNIQUE INDEX uq_cashier_invitations_code ON cashier_invitations (invite_code)",
    ),
    (
        "cashier_invitations",
        "idx_cashier_invitations_owner_id",
        "CREATE INDEX idx_cashier_invitations_owner_id ON cashier_invitations (owner_id)",
    ),
    (
        "pos_transactions",
        "uq_pos_transactions_order_code",
        "CREATE UNIQUE INDEX uq_pos_transactions_order_code ON pos_transactions (order_code)",
    ),
    (
        "pos_transaction_items",
        "idx_pos_items_transaction_id",
        "CREATE INDEX idx_pos_items_transaction_id ON pos_transaction_items (transaction_id)",
    ),
)

def table_columns(table_name):
    return {row["Field"] for row in fetch_all(f"SHOW COLUMNS FROM `{table_name}`")}


def column_exists(table_name, column_name):
    return bool(
        fetch_value(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
            0,
        )
    )


def column_is_nullable(table_name, column_name):
    return (
        str(
            fetch_value(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = %s
                  AND column_name = %s
                LIMIT 1
                """,
                (table_name, column_name),
                "",
            )
            or ""
        ).upper()
        == "YES"
    )


def index_exists(table_name, index_name):
    return bool(
        fetch_value(
            """
            SELECT COUNT(*)
            FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s
            """,
            (table_name, index_name),
            0,
        )
    )

def _add_missing_columns():
    for table_name, definitions in REQUIRED_COLUMNS.items():
        columns = table_columns(table_name)
        for column_name, definition in definitions.items():
            if column_name not in columns:
                commit(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}")

def _normalize_users():
    duplicate = fetch_one(
        """
        SELECT LOWER(TRIM(email)) AS normalized_email, COUNT(*) AS total
        FROM users
        GROUP BY LOWER(TRIM(email))
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )
    if duplicate:
        raise RuntimeError(
            "Migration dihentikan: ada email pengguna duplikat secara case-insensitive. "
            "Rapikan data tersebut sebelum menambahkan unique constraint."
        )

    commit("UPDATE users SET email = LOWER(TRIM(email))")
    commit("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
    commit(
        """
        UPDATE users
        SET role = 'staff'
        WHERE LOWER(TRIM(role)) IN ('staff', 'kasir', 'cashier')
        """
    )
    commit(
        """
        UPDATE users
        SET staff_status = CASE
            WHEN LOWER(TRIM(COALESCE(staff_status, ''))) IN ('cuti', 'leave') THEN 'leave'
            WHEN LOWER(REPLACE(TRIM(COALESCE(staff_status, '')), ' ', ''))
                 IN ('nonaktif', 'non-aktif', 'inactive') THEN 'inactive'
            WHEN LOWER(TRIM(COALESCE(staff_status, ''))) IN ('aktif', 'active') THEN 'active'
            WHEN is_active = 0 THEN 'inactive'
            ELSE 'active'
        END
        WHERE LOWER(role) = 'staff'
        """
    )
    commit(
        """
        UPDATE users
        SET is_active = CASE WHEN staff_status = 'active' THEN 1 ELSE 0 END
        WHERE LOWER(role) = 'staff'
        """
    )

def _backfill_legacy_menu_columns():
    columns = table_columns("menus")
    aliases = {
        "name": ("menu_name", "product_name", "item_name", "nama", "nama_menu", "title"),
        "category": ("menu_category", "product_category", "kategori", "category_name"),
        "code": ("menu_code", "product_code", "kode", "kode_menu"),
        "price": ("menu_price", "product_price", "harga", "harga_menu"),
        "image": ("image_url", "photo", "photo_url", "gambar", "gambar_menu"),
    }
    for target, candidates in aliases.items():
        source = next((candidate for candidate in candidates if candidate in columns), None)
        if not source:
            continue
        if target in {"price"}:
            commit(
                f"UPDATE menus SET `{target}` = `{source}` WHERE (`{target}` IS NULL OR `{target}` = 0) AND `{source}` IS NOT NULL"
            )
        else:
            commit(
                f"""
                UPDATE menus SET `{target}` = `{source}`
                WHERE (`{target}` IS NULL OR TRIM(`{target}`) = '') AND `{source}` IS NOT NULL
                """
            )

    commit("UPDATE menus SET name = CONCAT('Menu ', id) WHERE name IS NULL OR TRIM(name) = ''")
    commit("UPDATE menus SET category = 'Uncategorized' WHERE category IS NULL OR TRIM(category) = ''")
    commit("UPDATE menus SET price = 0 WHERE price IS NULL")

def _relax_legacy_menu_columns():
    """Keep old TiDB schemas insert-compatible after canonical columns exist."""
    columns = table_columns("menus")
    if "menu_name" in columns:
        commit("ALTER TABLE menus MODIFY COLUMN menu_name VARCHAR(255) NULL")

def _migrate_menu_categories():
    rows = fetch_all("SELECT id, category, category_id FROM menus ORDER BY id")
    for row in rows:
        category_name, normalized_name = normalize_category_name(
            row.get("category") or "Uncategorized"
        )
        existing = None
        if row.get("category_id"):
            existing = fetch_one("SELECT id, name FROM categories WHERE id = %s", (row["category_id"],))
        if not existing:
            existing = fetch_one(
                """
                SELECT id, name
                FROM categories
                WHERE normalized_name = %s OR name_key = %s
                ORDER BY id
                LIMIT 1
                """,
                (normalized_name, normalized_name),
            )
        if not existing:
            legacy_categories = fetch_all("SELECT id, name FROM categories ORDER BY id")
            existing = next(
                (
                    category
                    for category in legacy_categories
                    if normalize_category_name(category.get("name"))[1] == normalized_name
                ),
                None,
            )
        if not existing:
            commit(
                """
                INSERT INTO categories (name, name_key, normalized_name, description)
                VALUES (%s, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE name = name
                """,
                (category_name, normalized_name, normalized_name),
            )
            existing = fetch_one(
                """
                SELECT id, name
                FROM categories
                WHERE normalized_name = %s OR name_key = %s
                ORDER BY id
                LIMIT 1
                """,
                (normalized_name, normalized_name),
            )
        commit(
            "UPDATE menus SET category_id = %s, category = %s WHERE id = %s",
            (existing["id"], existing["name"], row["id"]),
        )


def _menu_prefix(category, name):
    source = str(category or name or "Menu").upper()
    words = re.sub(r"[^A-Z0-9]+", " ", source).strip().split()
    prefix = re.sub(r"[^A-Z0-9]", "", words[0] if words else "MNU")[:3]
    return (prefix or "MNU").ljust(3, "X")


def _repair_menu_codes():
    rows = fetch_all("SELECT id, code, category, name FROM menus ORDER BY id ASC")
    used = set()
    next_by_prefix = {}

    for row in rows:
        code = normalize_menu_code(row.get("code"))
        prefix = _menu_prefix(row.get("category"), row.get("name"))
        match = re.fullmatch(r"([A-Z0-9]{3})-(\d+)", code)
        if match:
            next_by_prefix[match.group(1)] = max(next_by_prefix.get(match.group(1), 1), int(match.group(2)) + 1)

        if not code or code in used:
            number = next_by_prefix.get(prefix, 1)
            candidate = f"{prefix}-{number:03d}"
            while candidate in used:
                number += 1
                candidate = f"{prefix}-{number:03d}"
            code = candidate
            next_by_prefix[prefix] = number + 1

        used.add(code)
        if code != str(row.get("code") or ""):
            commit("UPDATE menus SET code = %s WHERE id = %s", (code, row["id"]))

    for prefix, next_value in next_by_prefix.items():
        commit(
            """
            INSERT INTO menu_code_sequences (prefix, next_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE next_value = GREATEST(next_value, VALUES(next_value))
            """,
            (prefix, next_value),
        )


def category_rows_with_menu_counts():
    return fetch_all(
        """
        SELECT c.id, c.name, c.description, c.created_at, COUNT(m.id) AS menu_count
        FROM categories c
        LEFT JOIN menus m ON m.category_id = c.id
        GROUP BY c.id, c.name, c.description, c.created_at
        ORDER BY c.id
        """
    )


def audit_category_name_duplicates(rows=None):
    rows = category_rows_with_menu_counts() if rows is None else rows
    grouped = {}
    for row in rows:
        display_name, normalized_name = normalize_category_name(row.get("name"))
        if not normalized_name:
            display_name = f"Category {row['id']}"
            normalized_name = f"category{row['id']}"
        item = dict(row)
        item["display_name"] = display_name
        item["normalized_name"] = normalized_name
        item["menu_count"] = int(item.get("menu_count") or 0)
        grouped.setdefault(normalized_name, []).append(item)
    return [
        {"normalized_name": normalized_name, "categories": categories}
        for normalized_name, categories in sorted(grouped.items())
        if len(categories) > 1
    ]


def _category_keeper(categories):
    return min(
        categories,
        key=lambda category: (-int(category.get("menu_count") or 0), int(category["id"])),
    )


def migrate_category_name_uniqueness(cleanup_duplicates=False):
    rows = category_rows_with_menu_counts()
    duplicates = audit_category_name_duplicates(rows)
    if duplicates and not cleanup_duplicates:
        return {
            "backfill": "blocked",
            "unique_index": "not_created",
            "duplicates": duplicates,
            "moved_menus": 0,
            "deleted_categories": 0,
        }

    moved_menus = 0
    deleted_categories = 0
    deleted_ids = set()
    keeper_overrides = {}

    with transaction() as connection:
        cursor = connection.cursor()
        if rows:
            placeholders = ", ".join(["%s"] * len(rows))
            cursor.execute(
                f"SELECT id FROM categories WHERE id IN ({placeholders}) FOR UPDATE",
                tuple(row["id"] for row in rows),
            )
            cursor.fetchall()

        for group in duplicates:
            keeper = _category_keeper(group["categories"])
            keeper_id = int(keeper["id"])
            keeper_name = keeper["display_name"]
            keeper_description = keeper.get("description") or next(
                (
                    category.get("description")
                    for category in group["categories"]
                    if category.get("description")
                ),
                None,
            )
            keeper_overrides[keeper_id] = (keeper_name, keeper_description)

            for duplicate in group["categories"]:
                duplicate_id = int(duplicate["id"])
                if duplicate_id == keeper_id:
                    continue
                cursor.execute(
                    """
                    UPDATE menus
                    SET category_id = %s, category = %s
                    WHERE category_id = %s
                    """,
                    (keeper_id, keeper_name, duplicate_id),
                )
                moved_menus += int(cursor.rowcount or 0)
                cursor.execute("DELETE FROM categories WHERE id = %s", (duplicate_id,))
                deleted_categories += int(cursor.rowcount or 0)
                deleted_ids.add(duplicate_id)

        for row in rows:
            category_id = int(row["id"])
            if category_id in deleted_ids:
                continue
            display_name, normalized_name = normalize_category_name(row.get("name"))
            if not normalized_name:
                display_name = f"Category {category_id}"
                normalized_name = f"category{category_id}"
            description = row.get("description")
            if category_id in keeper_overrides:
                display_name, description = keeper_overrides[category_id]
            cursor.execute(
                """
                UPDATE categories
                SET name = %s, name_key = %s, normalized_name = %s,
                    description = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (display_name, normalized_name, normalized_name, description, category_id),
            )
            cursor.execute(
                "UPDATE menus SET category = %s WHERE category_id = %s",
                (display_name, category_id),
            )

    null_count = int(
        fetch_value(
            """
            SELECT COUNT(*)
            FROM categories
            WHERE normalized_name IS NULL OR TRIM(normalized_name) = ''
            """,
            (),
            0,
        )
        or 0
    )
    duplicate_count = int(
        fetch_value(
            """
            SELECT COUNT(*)
            FROM (
                SELECT normalized_name
                FROM categories
                GROUP BY normalized_name
                HAVING COUNT(*) > 1
            ) duplicate_names
            """,
            (),
            0,
        )
        or 0
    )
    if null_count or duplicate_count:
        raise RuntimeError(
            "Migration kategori dihentikan karena normalized_name masih memiliki "
            f"{null_count} nilai kosong dan {duplicate_count} kelompok duplikat."
        )

    if column_is_nullable("categories", "normalized_name"):
        commit(
            "ALTER TABLE categories MODIFY COLUMN normalized_name VARCHAR(255) NOT NULL"
        )
    if not index_exists("categories", "uq_categories_name_key"):
        commit("CREATE UNIQUE INDEX uq_categories_name_key ON categories (name_key)")
    if not index_exists("categories", "uq_categories_normalized_name"):
        commit(
            "CREATE UNIQUE INDEX uq_categories_normalized_name ON categories (normalized_name)"
        )
    return {
        "backfill": "complete",
        "unique_index": "ready",
        "duplicates": duplicates,
        "moved_menus": moved_menus,
        "deleted_categories": deleted_categories,
    }


def _backfill_item_codes():
    commit(
        """
        UPDATE pos_transaction_items i
        LEFT JOIN menus m ON m.id = i.menu_id
        SET i.menu_code = m.code
        WHERE (i.menu_code IS NULL OR TRIM(i.menu_code) = '') AND m.id IS NOT NULL
        """
    )


def audit_menu_name_duplicates(rows=None):
    """Return all legacy duplicate groups using the backend normalization."""
    if rows is None:
        rows = fetch_all("SELECT id, code, name FROM menus ORDER BY id ASC")
    grouped = {}
    for row in rows:
        normalized_name = normalize_menu_name(row.get("name"))
        if normalized_name:
            grouped.setdefault(normalized_name, []).append(row)
    return [
        {"normalized_name": key, "menus": items}
        for key, items in sorted(grouped.items())
        if len(items) > 1
    ]


def backfill_menu_normalized_names():
    """Backfill atomically; leave every legacy key untouched when duplicates exist."""
    rows = fetch_all("SELECT id, code, name FROM menus ORDER BY id ASC")
    duplicates = audit_menu_name_duplicates(rows)
    if duplicates:
        return False, duplicates

    with transaction() as connection:
        cursor = connection.cursor()
        for row in rows:
            cursor.execute(
                "UPDATE menus SET normalized_name = %s WHERE id = %s",
                (normalize_menu_name(row.get("name")), row["id"]),
            )
    return True, []


def migrate_menu_name_uniqueness():
    """Perform the staged backfill and add the unique index only after a clean audit."""
    success, duplicates = backfill_menu_normalized_names()
    if not success:
        return {
            "backfill": "blocked",
            "unique_index": "not_created",
            "duplicates": duplicates,
        }

    if not index_exists("menus", "uq_menus_normalized_name"):
        commit("CREATE UNIQUE INDEX uq_menus_normalized_name ON menus (normalized_name)")
    return {"backfill": "complete", "unique_index": "ready", "duplicates": []}


def _create_indexes():
    for table_name, index_name, statement in INDEXES:
        if not index_exists(table_name, index_name):
            commit(statement)


def ensure_schema():
    if current_app.extensions.get("tidb_schema_ready"):
        return

    with _schema_lock:
        if current_app.extensions.get("tidb_schema_ready"):
            return
        connection = get_db()
        try:
            cursor = connection.cursor()
            for statement in CREATE_STATEMENTS:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        _add_missing_columns()
        _backfill_legacy_menu_columns()
        _relax_legacy_menu_columns()
        _normalize_users()
        category_name_migration = migrate_category_name_uniqueness()
        if category_name_migration["duplicates"]:
            current_app.logger.warning(
                "Unique nama kategori ditunda: %s kelompok duplikat harus dibersihkan "
                "dengan migrations/004_category_uniqueness.py.",
                len(category_name_migration["duplicates"]),
            )
        _migrate_menu_categories()
        _repair_menu_codes()
        _backfill_item_codes()
        commit("ALTER TABLE menus MODIFY COLUMN code VARCHAR(100) NOT NULL")
        _create_indexes()
        menu_name_migration = migrate_menu_name_uniqueness()
        if menu_name_migration["duplicates"]:
            current_app.logger.warning(
                "Unique nama menu ditunda: %s kelompok duplikat harus diperbaiki manual.",
                len(menu_name_migration["duplicates"]),
            )
        current_app.extensions["tidb_schema_ready"] = True
        current_app.logger.info("Skema TiDB siap digunakan.")


def reset_schema_state_for_tests(app):
    app.extensions.pop("tidb_schema_ready", None)
