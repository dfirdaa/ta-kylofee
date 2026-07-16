import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


_CONFIG_ERRORS = []
_DB_CONFIG_ERRORS = []


def _record_config_error(message, database=False):
    _CONFIG_ERRORS.append(message)
    if database:
        _DB_CONFIG_ERRORS.append(message)


def _first_env(*names, default=""):
    """Return the first non-empty env value, allowing legacy DB_* aliases."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return str(default or "").strip()


def _env_bool(name, default=False, database=False):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    _record_config_error(
        f"{name} harus berupa 1/0, true/false, yes/no, atau on/off.", database=database
    )
    return default


def _safe_int(name, value, default, minimum=1, maximum=None, database=False):
    try:
        result = int(value)
        if result < minimum or (maximum is not None and result > maximum):
            raise ValueError
        return result
    except (TypeError, ValueError):
        limit = f" sampai {maximum}" if maximum is not None else " atau lebih"
        _record_config_error(
            f"{name} harus berupa angka {minimum}{limit}.", database=database
        )
        return default


def _database_url_config():
    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        return {}

    try:
        parsed = urlparse(raw_url)
        port = parsed.port or 4000
    except ValueError:
        _record_config_error("Port pada DATABASE_URL tidak valid.", database=True)
        return {}
    if parsed.scheme.lower() not in {"mysql", "mysql+pymysql"}:
        _record_config_error(
            "DATABASE_URL harus menggunakan skema mysql:// atau mysql+pymysql://.", database=True
        )
        return {}

    query = parse_qs(parsed.query)
    return {
        "host": parsed.hostname,
        "port": port,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": unquote((parsed.path or "").lstrip("/")),
        "ssl_ca": (query.get("ssl_ca") or query.get("ssl-ca") or [""])[0],
        "ssl_verify_cert": (query.get("ssl_verify_cert") or [""])[0],
    }


class Config:
    _url = _database_url_config()

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-this-before-production")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "menu"

    TIDB_HOST = _first_env("TIDB_HOST", "DB_HOST", default=_url.get("host", ""))
    TIDB_PORT = _safe_int(
        "TIDB_PORT/DB_PORT",
        _first_env("TIDB_PORT", "DB_PORT", default=_url.get("port", 4000)),
        4000,
        maximum=65535,
        database=True,
    )
    TIDB_USER = _first_env("TIDB_USER", "DB_USER", default=_url.get("user", ""))
    TIDB_PASSWORD = _first_env("TIDB_PASSWORD", "DB_PASSWORD", default=_url.get("password", ""))
    TIDB_DATABASE = _first_env("TIDB_DATABASE", "DB_NAME", default=_url.get("database", ""))
    TIDB_SSL_CA = _first_env("TIDB_SSL_CA", "DB_SSL_CA", default=_url.get("ssl_ca", ""))
    TIDB_SSL_VERIFY_CERT = _env_bool(
        "TIDB_SSL_VERIFY_CERT",
        str(_url.get("ssl_verify_cert", "1") or "1").lower() not in {"0", "false", "no", "off"},
        database=True,
    )
    TIDB_CONNECT_TIMEOUT = _safe_int(
        "TIDB_CONNECT_TIMEOUT",
        os.getenv("TIDB_CONNECT_TIMEOUT", "10"),
        10,
        maximum=60,
        database=True,
    )

    # DDL dari banyak cold start tidak aman. Di Vercel migrasi default nonaktif;
    # aktifkan hanya secara eksplisit setelah backup database.
    AUTO_MIGRATE = _env_bool("AUTO_MIGRATE", default=not bool(os.getenv("VERCEL")))
    SCHEMA_RETRY_SECONDS = _safe_int(
        "SCHEMA_RETRY_SECONDS", os.getenv("SCHEMA_RETRY_SECONDS", "60"), 60, maximum=3600
    )
    CONFIG_ERRORS = tuple(_CONFIG_ERRORS)
    DB_CONFIG_ERRORS = tuple(_DB_CONFIG_ERRORS)

    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@example.com").strip()
    STAFF_DEFAULT_PASSWORD = os.getenv("STAFF_DEFAULT_PASSWORD", "kyloffee123")

    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "kyloffee/menu").strip().strip("/")

