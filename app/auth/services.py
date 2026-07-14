from datetime import datetime

from flask import current_app, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import fetch_one, is_duplicate_key, transaction
from app.utils.roles import CASHIER_ROLE, normalize_role, role_label
from app.utils.validators import normalize_invite_code, validate_auth_fields


def find_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(%s) LIMIT 1", (email,))


def authenticate_user(email_input, password):
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


def set_authenticated_session(user):
    role = normalize_role(user.get("role"))
    session.permanent = True
    session["user_id"] = user.get("id")
    session["full_name"] = user.get("full_name")
    session["name"] = user.get("full_name")
    session["username"] = user.get("full_name")
    session["role"] = role
    session["role_label"] = role_label(role)
    session["owner_id"] = user.get("id") if role == "owner" else user.get("owner_id")


def redirect_for_role():
    if normalize_role(session.get("role")) == "owner":
        return redirect(url_for("menu.owner_menu"))
    if normalize_role(session.get("role")) == CASHIER_ROLE:
        return redirect(url_for("pos.pos"))
    session.clear()
    return redirect(url_for("auth.login"))


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
                from app.cashier.services import lock_valid_invitation

                invitation = lock_valid_invitation(cursor, invite_code, now)
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
                from app.cashier.services import consume_invitation

                consume_invitation(cursor, invitation["id"], user_id, now)
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
