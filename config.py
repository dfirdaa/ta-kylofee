import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _database_url_config():
    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        return {}

    parsed = urlparse(raw_url)
    if parsed.scheme.lower() not in {"mysql", "mysql+pymysql"}:
        raise RuntimeError("DATABASE_URL harus menggunakan skema mysql:// atau mysql+pymysql://.")

    query = parse_qs(parsed.query)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 4000,
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
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0").lower() in {"1", "true", "yes", "on"}
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "menu"

    TIDB_HOST = os.getenv("TIDB_HOST", os.getenv("DB_HOST", _url.get("host", ""))).strip()
    TIDB_PORT = int(os.getenv("TIDB_PORT", os.getenv("DB_PORT", str(_url.get("port", 4000)))))
    TIDB_USER = os.getenv("TIDB_USER", os.getenv("DB_USER", _url.get("user", ""))).strip()
    TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", os.getenv("DB_PASSWORD", _url.get("password", "")))
    TIDB_DATABASE = os.getenv("TIDB_DATABASE", os.getenv("DB_NAME", _url.get("database", ""))).strip()
    TIDB_SSL_CA = os.getenv("TIDB_SSL_CA", os.getenv("DB_SSL_CA", _url.get("ssl_ca", ""))).strip()
    TIDB_SSL_VERIFY_CERT = os.getenv(
        "TIDB_SSL_VERIFY_CERT", _url.get("ssl_verify_cert", "1") or "1"
    ).lower() not in {"0", "false", "no", "off"}
    TIDB_CONNECT_TIMEOUT = int(os.getenv("TIDB_CONNECT_TIMEOUT", "10"))

    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@example.com").strip()
    STAFF_DEFAULT_PASSWORD = os.getenv("STAFF_DEFAULT_PASSWORD", "kyloffee123")

    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "kyloffee/menu").strip().strip("/")

