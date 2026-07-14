from datetime import datetime

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import fetch_one, is_duplicate_key, transaction
from app.utils.validators import normalize_invite_code, validate_auth_fields


CASHIER_ROLE = "staff"
CASHIER_ROLE_ALIASES = ("staff", "kasir", "cashier")


def normalize_role(role):
    value = str(role or "").strip().lower()
    return CASHIER_ROLE if value in CASHIER_ROLE_ALIASES else value


def role_label(role):
    role = normalize_role(role)
    return "Owner" if role == "owner" else "Kasir" if role == CASHIER_ROLE else "Pengguna"


def find_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(%s) LIMIT 1", (email,))


def authenticate(email_input, password):
    email, errors = validate_auth_fields(email=email_input, password=password)
    if errors:
        return None, email, errors

    user = find_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return None, email, ["Email atau password salah. Cek kembali data login Anda."]
    active_value = user.get("is_active")
    if normalize_role(user.get("role")) == CASHIER_ROLE and int(1 if active_value is None else active_value) != 1:
        return None, email, ["Akun kasir ini sedang nonaktif. Silakan hubungi Owner."]
    if normalize_role(user.get("role")) not in {"owner", CASHIER_ROLE}:
        return None, email, ["Role akun tidak memiliki akses ke aplikasi ini."]
    return user, email, []


def register_user(role, form):
    role = normalize_role(role)
    full_name = str(form.get("full_name") or "").strip()
    email_input = str(form.get("email") or "").strip()
    password = str(form.get("password") or "")
    password_confirm = str(form.get("password_confirm") or "")
    staff_phone = str(form.get("staff_phone") or "").strip()
    invite_code = normalize_invite_code(form.get("invite_code"))

    email, errors = validate_auth_fields(full_name=full_name, email=email_input, password=password)
    if password != password_confirm:
        errors.append("Password dan konfirmasi password harus sama.")
    if find_user_by_email(email) if email else False:
        errors.append("Email sudah terdaftar. Gunakan email lain.")
    if role == CASHIER_ROLE and not invite_code:
        errors.append("Kode undangan kasir wajib diisi.")
    if role not in {"owner", CASHIER_ROLE}:
        errors.append("Role registrasi tidak valid.")

    form_data = {
        "full_name": full_name,
        "email": email_input,
        "staff_phone": staff_phone,
        "invite_code": invite_code,
    }
    if errors:
        return None, form_data, errors

    password_hash = generate_password_hash(password)
    now = datetime.now()
    try:
        with transaction() as connection:
            cursor = connection.cursor()
            owner_id = None
            invitation = None
            if role == CASHIER_ROLE:
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
                expires_at = invitation.get("expires_at")
                if expires_at and expires_at < now:
                    cursor.execute(
                        "UPDATE cashier_invitations SET status = 'Kedaluwarsa' WHERE id = %s",
                        (invitation["id"],),
                    )
                    raise ValueError("Kode undangan kasir sudah kedaluwarsa.")
                owner_id = invitation["owner_id"]

            cursor.execute(
                """
                INSERT INTO users (
                    full_name, email, password_hash, role, owner_id, staff_phone,
                    staff_position, joined_date, staff_status, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    full_name,
                    email,
                    password_hash,
                    role,
                    owner_id,
                    staff_phone or None,
                    "Kasir" if role == CASHIER_ROLE else None,
                    now.date() if role == CASHIER_ROLE else None,
                    "Aktif" if role == CASHIER_ROLE else None,
                    1,
                ),
            )
            user_id = cursor.lastrowid

            if invitation:
                cursor.execute(
                    """
                    UPDATE cashier_invitations
                    SET status = 'Digunakan', used_at = %s, used_by_cashier_id = %s
                    WHERE id = %s AND status = 'Aktif'
                    """,
                    (now, user_id, invitation["id"]),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Kode undangan baru saja digunakan pengguna lain.")
    except ValueError as exc:
        return None, form_data, [str(exc)]
    except Exception as exc:
        if is_duplicate_key(exc):
            return None, form_data, ["Email sudah terdaftar. Gunakan email lain."]
        current_app.logger.exception("Registrasi pengguna gagal.")
        return None, form_data, ["Registrasi gagal karena database bermasalah. Silakan coba lagi."]

    return {
        "id": user_id,
        "full_name": full_name,
        "email": email,
        "role": role,
        "owner_id": owner_id,
    }, form_data, []
