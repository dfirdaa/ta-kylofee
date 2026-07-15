from contextlib import contextmanager
from pathlib import Path

import pymysql
from flask import current_app, g


class DatabaseUnavailable(RuntimeError):
    """Raised with a credential-safe message when TiDB cannot be reached."""


def _ssl_options():
    host = current_app.config["TIDB_HOST"]
    ca_value = current_app.config.get("TIDB_SSL_CA", "")
    verify = current_app.config.get("TIDB_SSL_VERIFY_CERT", True)

    if ca_value:
        ca_path = Path(ca_value)
        if not ca_path.is_absolute():
            ca_path = Path(current_app.root_path).parent / ca_path
        if not ca_path.is_file():
            raise DatabaseUnavailable("File CA TiDB tidak ditemukan. Periksa TIDB_SSL_CA.")
        return {"ca": str(ca_path), "check_hostname": verify}

    if "tidbcloud.com" in host.lower() or int(current_app.config["TIDB_PORT"]) == 4000:
        return {"check_hostname": verify}
    return None


def _validate_config():
    missing = [
        name
        for name in ("TIDB_HOST", "TIDB_USER", "TIDB_PASSWORD", "TIDB_DATABASE")
        if not current_app.config.get(name)
    ]
    if missing:
        raise DatabaseUnavailable(
            "Konfigurasi TiDB belum lengkap. Isi DATABASE_URL atau variabel TIDB_HOST, "
            "TIDB_PORT, TIDB_USER, TIDB_PASSWORD, dan TIDB_DATABASE."
        )


def get_db():
    if "db" not in g:
        _validate_config()
        try:
            g.db = pymysql.connect(
                host=current_app.config["TIDB_HOST"],
                port=int(current_app.config["TIDB_PORT"]),
                user=current_app.config["TIDB_USER"],
                password=current_app.config["TIDB_PASSWORD"],
                database=current_app.config["TIDB_DATABASE"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=int(current_app.config.get("TIDB_CONNECT_TIMEOUT", 10)),
                read_timeout=20,
                write_timeout=20,
                ssl=_ssl_options(),
            )
        except DatabaseUnavailable:
            raise
        except pymysql.MySQLError as exc:
            current_app.logger.error("Koneksi TiDB gagal (kode=%s).", exc.args[0] if exc.args else "unknown")
            raise DatabaseUnavailable(
                "Gagal terhubung ke database TiDB. Periksa konfigurasi koneksi dan SSL."
            ) from exc
    return g.db


def close_db(_exception=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def execute(query, params=()):
    cursor = get_db().cursor()
    cursor.execute(query, params)
    return cursor


def fetch_one(query, params=()):
    return execute(query, params).fetchone()


def fetch_all(query, params=()):
    return execute(query, params).fetchall()


def fetch_value(query, params=(), default=None):
    row = fetch_one(query, params)
    if not row:
        return default
    return next(iter(row.values()))


def commit(query, params=()):
    connection = get_db()
    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()
        return cursor
    except Exception:
        connection.rollback()
        raise


@contextmanager
def transaction():
    connection = get_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def is_duplicate_key(exc):
    return isinstance(exc, pymysql.err.IntegrityError) and bool(exc.args) and exc.args[0] == 1062


def is_duplicate_key_for(exc, index_name):
    """Return True when MySQL/TiDB reports a duplicate for a named index."""
    return is_duplicate_key(exc) and str(index_name or "").lower() in str(exc).lower()


def init_app(app):
    app.teardown_appcontext(close_db)
