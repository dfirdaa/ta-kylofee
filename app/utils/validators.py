import re


MIN_PASSWORD_LENGTH = 6
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_email(email, *, gmail_required=False):
    value = str(email or "").strip()
    if not value:
        return value, "Email wajib diisi."
    if value != value.lower():
        return value, "Email harus menggunakan huruf kecil semua. Contoh: nama@gmail.com"
    if not EMAIL_PATTERN.fullmatch(value):
        return value, "Format email tidak valid."
    if gmail_required and not value.endswith("@gmail.com"):
        return value, "Gunakan alamat Gmail yang valid, contoh: nama@gmail.com."
    return value, None


def validate_password(password):
    if not password:
        return "Password wajib diisi."
    if len(password) < MIN_PASSWORD_LENGTH:
        return "Password harus terdiri dari minimal 6 karakter."
    return None


def validate_auth_fields(*, full_name=None, email=None, password=None, gmail_required=False):
    errors = []
    if full_name is not None and not str(full_name).strip():
        errors.append("Nama lengkap wajib diisi.")
    clean_email, email_error = validate_email(email, gmail_required=gmail_required)
    if email_error:
        errors.append(email_error)
    password_error = validate_password(password)
    if password_error:
        errors.append(password_error)
    return clean_email, errors


def normalize_menu_code(value):
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").strip().upper())


def normalize_invite_code(value):
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").strip().upper())[:64]

