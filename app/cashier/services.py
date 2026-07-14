import uuid
from datetime import date, datetime, timedelta

from flask import current_app
from werkzeug.security import generate_password_hash

from app.database import commit, fetch_all, fetch_one, fetch_value, is_duplicate_key
from app.utils.formatters import format_short_date
from app.utils.roles import CASHIER_ROLE, CASHIER_ROLE_ALIASES
from app.utils.validators import validate_email


STAFF_POSITIONS = ("Kasir",)
STAFF_STATUSES = ("Aktif", "Cuti", "Nonaktif")


def cashier_role_sql(column="u.role"):
    placeholders = ", ".join(["%s"] * len(CASHIER_ROLE_ALIASES))
    return f"LOWER({column}) IN ({placeholders})"


def parse_staff_date(value):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_status(status, is_active=True):
    value = str(status or "Aktif").strip().title()
    if value not in STAFF_STATUSES:
        value = "Aktif"
    return value if is_active else "Nonaktif"


def status_tone(status):
    return {"aktif": "active", "cuti": "leave"}.get(str(status).lower(), "inactive")


def format_cashier(row):
    is_active = int(row.get("is_active", 1) or 0) == 1
    status = normalize_status(row.get("staff_status"), is_active)
    joined = row.get("joined_date") or row.get("created_at")
    return {
        "id": row["id"],
        "full_name": row.get("full_name") or "Kasir",
        "initial": (row.get("full_name") or "K")[:1].upper(),
        "email": row.get("email") or "-",
        "phone": row.get("staff_phone") or "-",
        "phone_value": row.get("staff_phone") or "",
        "position": "Kasir",
        "role": "Kasir",
        "joined_date": format_short_date(joined),
        "joined_date_value": str(joined or "")[:10] or date.today().isoformat(),
        "created_at": row.get("created_at"),
        "status": status,
        "status_tone": status_tone(status),
        "is_active": is_active,
        "invite_code": row.get("invite_code") or "-",
    }


def list_cashiers(page=1, per_page=6):
    role_clause = cashier_role_sql()
    role_params = CASHIER_ROLE_ALIASES
    total = int(fetch_value(f"SELECT COUNT(*) FROM users u WHERE {role_clause}", role_params, 0) or 0)
    offset = (page - 1) * per_page
    rows = fetch_all(
        f"""
        SELECT
            u.id, u.full_name, u.email, u.role, u.staff_phone, u.staff_position,
            u.joined_date, u.staff_status, u.is_active, u.created_at,
            MAX(ci.invite_code) AS invite_code
        FROM users u
        LEFT JOIN cashier_invitations ci ON ci.used_by_cashier_id = u.id
        WHERE {role_clause}
        GROUP BY u.id, u.full_name, u.email, u.role, u.staff_phone, u.staff_position,
                 u.joined_date, u.staff_status, u.is_active, u.created_at
        ORDER BY u.id ASC
        LIMIT %s OFFSET %s
        """,
        (*role_params, per_page, offset),
    )
    return [format_cashier(row) for row in rows], total


def get_cashier(cashier_id):
    role_clause = cashier_role_sql()
    return fetch_one(
        f"""
        SELECT u.*, ci.invite_code
        FROM users u
        LEFT JOIN cashier_invitations ci ON ci.used_by_cashier_id = u.id
        WHERE u.id = %s AND {role_clause}
        LIMIT 1
        """,
        (cashier_id, *CASHIER_ROLE_ALIASES),
    )


def cashier_form_data(form):
    active = str(form.get("is_active", "1")) == "1"
    return {
        "full_name": str(form.get("full_name") or "").strip(),
        "email": str(form.get("email") or "").strip(),
        "staff_phone": str(form.get("staff_phone") or "").strip(),
        "staff_position": "Kasir",
        "joined_date": str(form.get("joined_date") or "").strip(),
        "staff_status": normalize_status(form.get("staff_status"), active),
        "is_active": active,
    }


def validate_cashier_form(data, *, exclude_id=None):
    errors = []
    if not data["full_name"]:
        errors.append("Nama lengkap wajib diisi.")
    clean_email, email_error = validate_email(data["email"])
    if email_error:
        errors.append(email_error)
    else:
        existing = fetch_one("SELECT id FROM users WHERE LOWER(email) = LOWER(%s) LIMIT 1", (clean_email,))
        if existing and int(existing["id"]) != int(exclude_id or 0):
            errors.append("Email sudah digunakan akun lain.")
    if not data["staff_phone"]:
        errors.append("Nomor telepon wajib diisi.")
    joined_date = parse_staff_date(data["joined_date"])
    if not joined_date:
        errors.append("Tanggal bergabung wajib diisi dengan format tanggal yang valid.")
    if data["staff_status"] not in STAFF_STATUSES:
        errors.append("Status kasir tidak valid.")
    return clean_email, joined_date, errors


def create_cashier(data, creator_owner_id):
    email, joined_date, errors = validate_cashier_form(data)
    if errors:
        return errors
    password = current_app.config["STAFF_DEFAULT_PASSWORD"]
    if len(password) < 6:
        return ["STAFF_DEFAULT_PASSWORD harus minimal 6 karakter."]
    try:
        commit(
            """
            INSERT INTO users (
                full_name, email, password_hash, role, owner_id, staff_phone,
                staff_position, joined_date, staff_status, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, 'Kasir', %s, 'Aktif', 1)
            """,
            (
                data["full_name"],
                email,
                generate_password_hash(password),
                CASHIER_ROLE,
                creator_owner_id,
                data["staff_phone"],
                joined_date,
            ),
        )
    except Exception as exc:
        if is_duplicate_key(exc):
            return ["Email sudah terdaftar. Gunakan email kasir yang berbeda."]
        raise
    return []


def update_cashier(cashier_id, data):
    email, joined_date, errors = validate_cashier_form(data, exclude_id=cashier_id)
    if errors:
        return errors
    role_clause = cashier_role_sql("role")
    try:
        cursor = commit(
            f"""
            UPDATE users
            SET full_name = %s, email = %s, staff_phone = %s, staff_position = 'Kasir',
                joined_date = %s, staff_status = %s, is_active = %s
            WHERE id = %s AND {role_clause}
            """,
            (
                data["full_name"],
                email,
                data["staff_phone"],
                joined_date,
                data["staff_status"],
                1 if data["is_active"] else 0,
                cashier_id,
                *CASHIER_ROLE_ALIASES,
            ),
        )
        if cursor.rowcount != 1:
            return ["Data kasir tidak ditemukan."]
    except Exception as exc:
        if is_duplicate_key(exc):
            return ["Email sudah digunakan akun lain."]
        raise
    return []


def create_invitation(owner_id, expires_days=7):
    for _attempt in range(5):
        code = f"KASIR-{uuid.uuid4().hex[:10].upper()}"
        try:
            commit(
                """
                INSERT INTO cashier_invitations (owner_id, invite_code, status, expires_at)
                VALUES (%s, %s, 'Aktif', %s)
                """,
                (owner_id, code, datetime.now() + timedelta(days=expires_days)),
            )
            return code
        except Exception as exc:
            if not is_duplicate_key(exc):
                raise
    raise RuntimeError("Gagal membuat kode undangan unik setelah 5 percobaan.")


def lock_valid_invitation(cursor, invite_code, now=None):
    now = now or datetime.now()
    cursor.execute(
        """
        SELECT id, owner_id, status, expires_at
        FROM cashier_invitations
        WHERE invite_code = %s
        FOR UPDATE
        """,
        (invite_code,),
    )
    invitation = cursor.fetchone()
    if not invitation:
        raise ValueError("Kode undangan kasir tidak ditemukan.")
    if str(invitation.get("status") or "").lower() != "aktif":
        raise ValueError("Kode undangan kasir sudah digunakan atau tidak aktif.")
    if invitation.get("expires_at") and invitation["expires_at"] < now:
        raise ValueError("Kode undangan kasir sudah kedaluwarsa.")
    return invitation


def consume_invitation(cursor, invitation_id, cashier_id, now=None):
    cursor.execute(
        """
        UPDATE cashier_invitations
        SET status = 'Digunakan', used_at = %s, used_by_cashier_id = %s
        WHERE id = %s AND status = 'Aktif'
        """,
        (now or datetime.now(), cashier_id, invitation_id),
    )
    if cursor.rowcount != 1:
        raise ValueError("Kode undangan baru saja digunakan pengguna lain.")


def list_invitations(limit=10):
    rows = fetch_all(
        """
        SELECT ci.*, owner.full_name AS owner_name, cashier.full_name AS cashier_name
        FROM cashier_invitations ci
        LEFT JOIN users owner ON owner.id = ci.owner_id
        LEFT JOIN users cashier ON cashier.id = ci.used_by_cashier_id
        ORDER BY ci.created_at DESC, ci.id DESC
        LIMIT %s
        """,
        (limit,),
    )
    now = datetime.now()
    for row in rows:
        if str(row.get("status")).lower() == "aktif" and row.get("expires_at") and row["expires_at"] < now:
            row["status"] = "Kedaluwarsa"
            commit("UPDATE cashier_invitations SET status = 'Kedaluwarsa' WHERE id = %s", (row["id"],))
    return rows
