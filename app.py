# Modul standar berikut menangani konfigurasi, validasi teks, keamanan koneksi, database lokal, dan pembuatan kode unik.
import os
import re
import ssl
import sqlite3
import uuid
# BytesIO menampung gambar QR di memori, sedangkan wraps menjaga identitas fungsi saat memakai decorator akses.
from io import BytesIO
# Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
from functools import wraps
from pathlib import Path
from datetime import date, datetime, timedelta

# Memuat konfigurasi rahasia dari .env dan menyediakan layanan email aplikasi.
from dotenv import load_dotenv
# Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
import resend
# Komponen Flask berikut menangani route, template, request, session, respons JSON, pesan flash, dan redirect.
from flask import (
    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
# Werkzeug dipakai untuk mengamankan password dan nama file upload.
from werkzeug.security import check_password_hash, generate_password_hash
# Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
from werkzeug.utils import secure_filename

# Cloudinary bersifat opsional agar penyimpanan gambar lokal tetap dapat dipakai ketika paket tidak tersedia.
try:
    # Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
    import cloudinary
    import cloudinary.uploader
# Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
except ImportError:  # pragma: no cover - only used when dependency is missing.
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cloudinary = None

# Library QR bersifat opsional agar bagian lain aplikasi tetap dapat dimulai sebelum dependensi dipasang.
try:
    # Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
    import qrcode
# Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
except ImportError:  # pragma: no cover - app still runs before dependency install.
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    qrcode = None

# Menentukan folder dasar project agar lokasi .env, database, template, dan aset tidak bergantung pada terminal aktif.
BASE_DIR = Path(__file__).resolve().parent
# Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
load_dotenv(BASE_DIR / ".env")
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
DATABASE = Path(os.getenv("SQLITE_DATABASE_PATH", "/tmp/database.db" if os.getenv("VERCEL") else BASE_DIR / "database.db"))


# ======================
# Resend Email Configuration
# ======================
# Nilai email diambil dari environment supaya kredensial tidak ditulis langsung di source code.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@example.com").strip()

# API key hanya dipasang bila tersedia agar mode lokal tanpa layanan email tidak gagal.
if RESEND_API_KEY:
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    resend.api_key = RESEND_API_KEY

# Konfigurasi ini menentukan apakah aplikasi memakai MySQL/TiDB atau SQLite lokal sebagai cadangan.
DB_HOST = os.getenv("DB_HOST", "").strip()
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
DB_PORT = int(os.getenv("DB_PORT", "4000")) if os.getenv("DB_PORT") else 4000
DB_USER = os.getenv("DB_USER", "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "").strip()
DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()

# Set DB_FORCE_SQLITE=1 in .env when you want the app to ignore remote DB
# and use the local database.db file instead.
DB_FORCE_SQLITE = os.getenv("DB_FORCE_SQLITE", "0").strip().lower() in {"1", "true", "yes", "on"}

# Keep this enabled by default so wrong/expired TiDB credentials do not block
# login/register during local development. Set DB_FALLBACK_SQLITE=0 to fail fast.
DB_FALLBACK_SQLITE = os.getenv("DB_FALLBACK_SQLITE", "1").strip().lower() not in {"0", "false", "no", "off"}

# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
DEBUG_DB_CONFIG = os.getenv("DEBUG_DB_CONFIG", "0").strip().lower() in {"1", "true", "yes", "on"}
# Informasi koneksi hanya dicetak ketika mode debug database sengaja diaktifkan.
if DEBUG_DB_CONFIG:
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    print("DB_HOST:", DB_HOST or "<empty - using SQLite>")
    print("DB_PORT:", DB_PORT)
    print("DB_USER:", DB_USER or "<empty>")
    print("DB_NAME:", DB_NAME or "<empty>")
    print("DB_PASSWORD exists:", bool(DB_PASSWORD))
    print("DB_FORCE_SQLITE:", DB_FORCE_SQLITE)
    print("DB_FALLBACK_SQLITE:", DB_FALLBACK_SQLITE)

# Driver MySQL dibuat opsional karena aplikasi juga mendukung SQLite.
try:
    # Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
    import pymysql
# Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
except ImportError:
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    pymysql = None

# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
DB_REMOTE_CONFIGURED = bool(DB_HOST and DB_USER and DB_NAME and pymysql is not None)
DB_USE_MYSQL = DB_REMOTE_CONFIGURED and not DB_FORCE_SQLITE
REMOTE_DB_FAILED = False
SCHEMA_READY = False


# Menyusun opsi SSL yang aman untuk koneksi MySQL/TiDB, termasuk saat file CA tidak ditemukan.
def get_mysql_ssl_options():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    """Return PyMySQL SSL options that work for TiDB Cloud/MySQL.

    If DB_SSL_CA is filled but the file is missing, we do not crash.
    The app will try a default encrypted connection instead.
    """
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not DB_SSL_CA:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if "tidbcloud.com" in DB_HOST.lower() or DB_PORT == 4000:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return {"ssl": {}}
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return {}

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    ssl_ca_path = Path(DB_SSL_CA)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not ssl_ca_path.is_absolute():
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        ssl_ca_path = BASE_DIR / ssl_ca_path

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if ssl_ca_path.exists():
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return {"ssl": {"ca": str(ssl_ca_path)}}

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    print(f"WARNING: DB_SSL_CA file was not found: {ssl_ca_path}. Using default SSL instead.")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {"ssl": {}}


# Pembungkus ini menyamakan cara pemanggilan SQLite dan MySQL sehingga query aplikasi dapat memakai antarmuka yang sama.
class DatabaseConnection:
    # Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
    def __init__(self, conn, is_mysql=False):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        self.conn = conn
        self.is_mysql = is_mysql

    # MySQL memakai placeholder %s, sehingga tanda ? dari query bersama perlu disesuaikan sebelum dieksekusi.
    def adapt_sql(self, sql):
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if self.is_mysql:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return sql.replace("?", "%s")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return sql

    # Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
    def cursor(self):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return self.conn.cursor()

    # Menjalankan satu query beserta parameter secara aman pada jenis database yang sedang aktif.
    def execute(self, sql, params=()):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        sql = self.adapt_sql(sql)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if self.is_mysql:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            cursor = self.conn.cursor()
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            cursor.execute(sql, params)
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return cursor
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return self.conn.execute(sql, params)

    # Menjalankan beberapa pernyataan SQL sekaligus, dengan fallback manual untuk driver tanpa executescript.
    def executescript(self, script):
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if hasattr(self.conn, "executescript"):
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return self.conn.executescript(script)
        # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
        for statement in script.split(";"):
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            statement = statement.strip()
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if statement:
                # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
                self.execute(statement)

    # Commit memastikan perubahan transaksi benar-benar disimpan di database.
    def commit(self):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return self.conn.commit()

    # Rollback membatalkan transaksi ketika proses penyimpanan mengalami kegagalan.
    def rollback(self):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return self.conn.rollback()

    # Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
    def close(self):
        return self.conn.close()
    def __getattr__(self, name):
        return getattr(self.conn, name)

# Konstanta berikut menjadi aturan bersama untuk akun kasir, menu, kategori, dan kompatibilitas data lama.
STAFF_DEFAULT_PASSWORD = os.getenv("STAFF_DEFAULT_PASSWORD", "kyloffee123")
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
MIN_MENU_PRICE = 500
CATEGORY_NAME_MAX_LENGTH = 100
STAFF_POSITIONS = ["Kasir"]
STAFF_STATUSES = ["Aktif", "Cuti", "Nonaktif"]
CASHIER_ROLE = "staff"
CASHIER_ROLE_ALIASES = ("staff", "kasir", "cashier")
LEGACY_CASHIER_OWNER_WINDOW_MINUTES = int(os.getenv("LEGACY_CASHIER_OWNER_WINDOW_MINUTES", "120"))

# Membuat aplikasi Flask dengan lokasi template dan file statis yang eksplisit.
app = Flask(
    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
    __name__,
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
# Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
)
# Konfigurasi session melindungi cookie login, sedangkan batas upload mencegah file terlalu besar.
app.config["SECRET_KEY"] = os.environ.get(
    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
    "SECRET_KEY",
    "dev-secret-key-change-this-before-production",
# Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
)
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.getenv("VERCEL"))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["UPLOAD_FOLDER"] = BASE_DIR / "static" / "uploads" / "menu"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
MYSQL_SSL_OPTIONS = get_mysql_ssl_options() if DB_USE_MYSQL else {}

# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_FOLDER = os.environ.get("CLOUDINARY_FOLDER", "kyloffee/menu").strip().strip("/")

# Cloudinary hanya dikonfigurasi jika library dan seluruh kredensial wajib tersedia.
if cloudinary and CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
    cloudinary.config(
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

# ======================
# Resend Email Helper
# ======================
def send_email(to_email, subject, html_content):
    # Tanpa API key, fungsi berhenti secara aman karena email bukan syarat agar transaksi utama berjalan.
    if not RESEND_API_KEY:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.warning("RESEND_API_KEY belum tersedia. Email tidak dikirim.")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return False

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        resend.Emails.send(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return True
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception as exc:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.error("Resend gagal mengirim email: %s", exc)
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return False


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_db():

    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    """Get the database connection for the current Flask request.

    Priority:
    1. Remote MySQL/TiDB when .env is complete and DB_FORCE_SQLITE is not enabled.
    2. Local SQLite database.db when remote DB is disabled or unavailable.

    This prevents a wrong TiDB password from making login/register unusable.
    """
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    global REMOTE_DB_FAILED

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "db" not in g:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        should_try_mysql = DB_USE_MYSQL and not (REMOTE_DB_FAILED and DB_FALLBACK_SQLITE)

        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if should_try_mysql:
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                conn = pymysql.connect(
                    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                    host=DB_HOST,
                    port=int(DB_PORT),
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=False,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    **MYSQL_SSL_OPTIONS,
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                )
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                g.db = DatabaseConnection(conn, is_mysql=True)
                # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
                return g.db
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except Exception as exc:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                REMOTE_DB_FAILED = True
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                safe_message = str(exc)

                # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
                if not DB_FALLBACK_SQLITE:
                    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                    app.logger.error("Failed to connect to MySQL/TiDB: %s", safe_message)
                    # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
                    raise RuntimeError(
                        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                        "Gagal terhubung ke TiDB/MySQL. Periksa DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, dan SSL."
                    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                    ) from exc

                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                app.logger.warning(
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Remote MySQL/TiDB unavailable. Falling back to local SQLite database.db. Detail: %s",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    safe_message,
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                )

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        sqlite_conn = sqlite3.connect(DATABASE)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        sqlite_conn.row_factory = sqlite3.Row
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        g.db = DatabaseConnection(sqlite_conn, is_mysql=False)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return g.db


# Menjalankan query perubahan data, melakukan commit saat berhasil, dan rollback saat terjadi kesalahan.
def execute_commit(query, params=()):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor = db.execute(query, params)
        # Melakukan commit agar seluruh perubahan transaksi tersimpan permanen.
        db.commit()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.debug("DB commit successful: %s", query)
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return cursor
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Melakukan rollback agar perubahan parsial dibatalkan ketika proses gagal.
        db.rollback()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.exception("DB write failed and rollback executed.")
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        raise


# Menjalankan kumpulan query skema sebagai satu transaksi agar perubahan tabel konsisten.
def execute_script_commit(script):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        db.executescript(script)
        # Melakukan commit agar seluruh perubahan transaksi tersimpan permanen.
        db.commit()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.debug("DB script commit successful.")
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Melakukan rollback agar perubahan parsial dibatalkan ketika proses gagal.
        db.rollback()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.exception("DB schema change failed and rollback executed.")
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        raise


# Mengambil satu nilai dari hasil query agregat tanpa bergantung pada bentuk row driver database.
def fetch_scalar(cursor):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    row = cursor.fetchone()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if row is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if isinstance(row, dict):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return next(iter(row.values()))
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return row[0]


# Mengubah seluruh hasil query menjadi dictionary agar mudah dipakai oleh template dan respons JSON.
def fetch_all_dict(cursor):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = cursor.fetchall()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not rows:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return []
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if isinstance(rows[0], dict):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return rows
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = [col[0] for col in cursor.description]
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return [dict(zip(columns, row)) for row in rows]


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def row_to_dict(row):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if row is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return {}
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if isinstance(row, dict):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return row
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return dict(row)


# Menyamakan variasi nama role lama menjadi role aplikasi yang berlaku saat ini.
def normalize_role_value(role):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role_key = str(role or "").strip().lower()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if role_key in CASHIER_ROLE_ALIASES:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return CASHIER_ROLE
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return role_key


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def cashier_role_filter(column="role"):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    placeholders = ", ".join(["?"] * len(CASHIER_ROLE_ALIASES))
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"LOWER({column}) IN ({placeholders})"


# Mengubah berbagai format waktu database menjadi datetime untuk perbandingan dan tampilan yang konsisten.
def parse_db_datetime(value):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if isinstance(value, datetime):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return value
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if isinstance(value, date):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return datetime.combine(value, datetime.min.time())

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    value = str(value or "").strip()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None

    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for candidate in (value, value.replace("Z", "+00:00")):
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            parsed = datetime.fromisoformat(candidate)
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return parsed.replace(tzinfo=None)
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except ValueError:
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue

    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return datetime.strptime(value[:19], date_format)
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except ValueError:
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return None


# Merapikan spasi nama kategori agar validasi duplikat tidak terkecoh oleh perbedaan spasi.
def normalize_category_name(value):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return " ".join(str(value or "").strip().split())


# Decorator ini membuat helper kategori dapat dipanggil langsung dari seluruh template Jinja.
@app.template_global()
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def category_key(category):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return normalize_category_name(category).lower()


# Membaca struktur tabel untuk mendukung migrasi pada SQLite maupun MySQL.
def get_table_columns(table_name):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cursor = db.cursor()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor.execute(f"SHOW COLUMNS FROM {table_name}")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        fetched = cursor.fetchall()
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return {row["Field"] if isinstance(row, dict) else row[0] for row in fetched}

    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    cursor.execute(f"PRAGMA table_info({table_name})")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {row[1] for row in cursor.fetchall()}


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def table_exists(table_name):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor = db.execute("SHOW TABLES LIKE ?", (table_name,))
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor = db.execute(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (table_name,),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return cursor.fetchone() is not None


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def index_exists(table_name, index_name):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return fetch_scalar(
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = ?
                  AND index_name = ?
                """,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (table_name, index_name),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ) > 0

    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    cursor = db.execute(f"PRAGMA index_list({table_name})")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return any(row[1] == index_name for row in cursor.fetchall())


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def is_duplicate_column_error(exc):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return (
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        pymysql is not None
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        and isinstance(exc, pymysql.err.OperationalError)
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        and exc.args
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        and exc.args[0] == 1060
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def is_duplicate_index_error(exc):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return (
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        pymysql is not None
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        and isinstance(exc, (pymysql.err.OperationalError, pymysql.err.InternalError))
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        and exc.args
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        and exc.args[0] == 1061
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Menambah kolom hanya bila belum tersedia supaya proses inisialisasi aman dijalankan berulang kali.
def add_column_if_missing(table_name, column_name, mysql_definition, sqlite_definition):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if column_name in get_table_columns(table_name):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    definition = mysql_definition if db.is_mysql else sqlite_definition
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception as exc:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if db.is_mysql and is_duplicate_column_error(exc):
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            app.logger.info("Column %s.%s already exists; continuing.", table_name, column_name)
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        raise


# Membuat index hanya sekali agar query lebih cepat tanpa menimbulkan error duplikasi skema.
def create_index_if_missing(table_name, index_name, create_sql):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if index_exists(table_name, index_name):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit(create_sql)
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception as exc:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if db.is_mysql and is_duplicate_index_error(exc):
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            app.logger.info("Index %s.%s already exists; continuing.", table_name, index_name)
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        raise


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def app_setting_key_column():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return "`key`" if get_db().is_mysql else "key"


# Mengambil nilai konfigurasi internal yang disimpan di database.
def get_app_setting(setting_key):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    key_column = app_setting_key_column()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return get_db().execute(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        f"SELECT value FROM app_settings WHERE {key_column} = ?",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (setting_key,),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()


# Menyimpan konfigurasi internal dan memakai commit agar nilainya tersedia pada request berikutnya.
def set_app_setting(setting_key, value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    key_column = app_setting_key_column()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return execute_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            INSERT INTO app_settings ({key_column}, value)
            VALUES (?, ?)
            ON DUPLICATE KEY UPDATE value = VALUES(value)
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (setting_key, value),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return execute_commit(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        f"INSERT OR REPLACE INTO app_settings ({key_column}, value) VALUES (?, ?)",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (setting_key, value),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def role_display_name(role):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role = normalize_role_value(role)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if role == "owner":
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "Owner"
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if role == CASHIER_ROLE:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "Kasir"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return role.title() or "Pengguna"


# Menormalkan data akun kasir lama agar role dan statusnya sesuai aturan autentikasi saat ini.
def normalize_cashier_rows():
    # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
    execute_commit(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        UPDATE users
        SET role = ?
        WHERE {cashier_role_filter("role")} AND LOWER(role) != ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (CASHIER_ROLE, *CASHIER_ROLE_ALIASES, CASHIER_ROLE),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
    execute_commit(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        UPDATE users
        SET staff_position = ?
        WHERE {cashier_role_filter("role")}
          AND (staff_position IS NULL OR TRIM(staff_position) = '' OR LOWER(TRIM(staff_position)) IN (?, ?))
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        ("Kasir", *CASHIER_ROLE_ALIASES, "staff", "cashier"),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
    execute_commit(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        UPDATE users
        SET staff_status = ?
        WHERE {cashier_role_filter("role")}
          AND (staff_status IS NULL OR TRIM(staff_status) = '')
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        ("Aktif", *CASHIER_ROLE_ALIASES),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
    execute_commit(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        UPDATE users
        SET joined_date = DATE(created_at)
        WHERE {cashier_role_filter("role")}
          AND (joined_date IS NULL OR TRIM(joined_date) = '')
          AND created_at IS NOT NULL
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        CASHIER_ROLE_ALIASES,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Menghubungkan akun kasir lama ke owner yang tepat agar pembatasan data per owner tetap berlaku.
def attach_legacy_cashiers_to_owner():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    normalize_cashier_rows()

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "SELECT id, created_at FROM users WHERE LOWER(role) = ? ORDER BY created_at ASC, id ASC",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            ("owner",),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not owner_rows:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if len(owner_rows) != 1:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        orphan_cashiers = fetch_all_dict(
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                f"""
                SELECT id, full_name, email, created_at
                FROM users
                WHERE {cashier_role_filter("role")} AND owner_id IS NULL
                ORDER BY created_at ASC, id ASC
                """,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                CASHIER_ROLE_ALIASES,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        parsed_owners = [
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            {**owner, "created_dt": parse_db_datetime(owner.get("created_at"))}
            # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
            for owner in owner_rows
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ]

        # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
        for cashier in orphan_cashiers:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            cashier_created = parse_db_datetime(cashier.get("created_at"))
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if not cashier_created:
                # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
                continue

            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            candidates = [
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                owner
                # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
                for owner in parsed_owners
                # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
                if owner.get("created_dt") and owner["created_dt"] <= cashier_created
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            ]
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if not candidates:
                # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
                continue

            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            owner = max(candidates, key=lambda item: item["created_dt"])
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            delta = cashier_created - owner["created_dt"]
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if delta <= timedelta(minutes=LEGACY_CASHIER_OWNER_WINDOW_MINUTES):
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                execute_commit(
                    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                    f"""
                    UPDATE users
                    SET owner_id = ?
                    WHERE id = ? AND {cashier_role_filter("role")} AND owner_id IS NULL
                    """,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    (owner["id"], cashier["id"], *CASHIER_ROLE_ALIASES),
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                )
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                app.logger.info(
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Linked legacy cashier %s (%s) to owner_id %s from creation-time proximity.",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    cashier.get("full_name"),
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    cashier.get("email"),
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    owner["id"],
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                )
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
    execute_commit(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        UPDATE users
        SET owner_id = ?
        WHERE {cashier_role_filter("role")} AND owner_id IS NULL
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (owner_rows[0]["id"], *CASHIER_ROLE_ALIASES),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_default_owner_id_for_cashier():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        get_db().execute(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "SELECT id FROM users WHERE LOWER(role) = ? ORDER BY id ASC",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            ("owner",),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if len(owner_rows) == 1:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return owner_rows[0].get("id")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return None


# Memastikan tabel kategori memiliki seluruh kolom yang dibutuhkan versi aplikasi saat ini.
def ensure_category_columns():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = get_table_columns("categories")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "name_key" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("categories", "name_key", "VARCHAR(255)", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "description" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("categories", "description", "TEXT", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "created_at" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("categories", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "updated_at" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("categories", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TEXT")

    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    rows = fetch_all_dict(db.execute("SELECT id, name, name_key FROM categories"))
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        expected_key = category_key(row.get("name"))
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if expected_key and row.get("name_key") != expected_key:
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            execute_commit(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "UPDATE categories SET name_key = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (expected_key, row["id"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        create_index_if_missing(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "categories",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "idx_categories_name_key",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "CREATE UNIQUE INDEX idx_categories_name_key ON categories (name_key)",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_name_key ON categories (name_key)")


# Membuat tabel kategori dan migrasinya sebelum fitur kategori digunakan.
def init_category_table():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS categories (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL,
                name_key VARCHAR(255) NOT NULL UNIQUE,
                description TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_key TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_category_columns()


# Mencari satu kategori berdasarkan ID untuk validasi form dan operasi edit/hapus.
def get_category_by_id(category_id):
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_id = int(category_id)
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except (TypeError, ValueError):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category_id < 1:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return get_db().execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_category_by_name(name):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    key = category_key(name)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not key:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return get_db().execute("SELECT * FROM categories WHERE name_key = ?", (key,)).fetchone()


# Menggunakan kategori yang sudah ada atau membuatnya bila diperlukan saat migrasi menu lama.
def get_or_create_category(name, description=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    clean_name = normalize_category_name(name)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    key = category_key(clean_name)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not clean_name:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    existing = get_category_by_name(clean_name)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if existing:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return existing

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        cursor = execute_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            INSERT INTO categories (name, name_key, description)
            VALUES (?, ?, ?)
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (clean_name, key, description or None),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_id = cursor.lastrowid
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return get_category_by_name(clean_name)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return get_category_by_id(category_id)


# Memindahkan referensi kategori berbentuk teks pada menu lama ke relasi category_id.
def migrate_menu_categories():
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not table_exists("menus"):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = get_table_columns("menus")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "category" not in columns or "category_id" not in columns:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    menu_rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            SELECT id, category, category_id
            FROM menus
            WHERE category IS NOT NULL AND TRIM(category) <> ''
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for menu in menu_rows:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        existing_category = get_category_by_id(menu.get("category_id"))
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if existing_category:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            category_name = normalize_category_name(existing_category["name"])
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if menu.get("category") != category_name:
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                execute_commit(
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "UPDATE menus SET category = ? WHERE id = ?",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    (category_name, menu["id"]),
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                )
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category = get_or_create_category(menu.get("category"))
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if category:
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            execute_commit(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "UPDATE menus SET category_id = ?, category = ? WHERE id = ?",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (category["id"], category["name"], menu["id"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )


# Memvalidasi nama kategori dan mencegah duplikat, sambil mengecualikan record yang sedang diedit.
def validate_category_payload(data, exclude_id=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    name = normalize_category_name(data.get("name", ""))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    description = str(data.get("description", "") or "").strip() or None
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    errors = {}

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not name:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors["name"] = "Nama kategori wajib diisi."
    # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
    elif len(name) > CATEGORY_NAME_MAX_LENGTH:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors["name"] = f"Nama kategori maksimal {CATEGORY_NAME_MAX_LENGTH} karakter."
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        duplicate = get_category_by_name(name)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if duplicate and int(duplicate["id"]) != int(exclude_id or 0):
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            errors["name"] = "Nama kategori sudah digunakan."

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {"name": name, "description": description}, errors


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_category_options():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        get_db().execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            SELECT id, name, description
            FROM categories
            ORDER BY LOWER(name) ASC, id ASC
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_menu_category_from_value(category_id=None, category_name=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_category_by_id(category_id)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not category and category_name:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category = get_category_by_name(category_name)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return category


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_category_date(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    value = str(value or "").strip()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "-"

    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            parsed = datetime.strptime(value[:19], date_format)
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return format_short_date(parsed.date())
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except ValueError:
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return value[:10]


# Mengambil daftar kategori beserta jumlah menu untuk tabel manajemen dan fitur pencarian.
def fetch_category_management_rows(search=""):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    where_clause = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    params = []

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if search:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        where_clause = "WHERE c.name LIKE ? OR COALESCE(c.description, '') LIKE ?"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        keyword = f"%{search}%"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        params = [keyword, keyword]

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT
                c.id,
                c.name,
                c.description,
                c.created_at,
                c.updated_at,
                COUNT(m.id) AS menu_count
            FROM categories c
            LEFT JOIN menus m ON m.category_id = c.id
            {where_clause}
            GROUP BY c.id, c.name, c.description, c.created_at, c.updated_at
            ORDER BY LOWER(c.name) ASC, c.id ASC
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            params,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        row["created_label"] = format_category_date(row.get("created_at"))
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        row["description"] = row.get("description") or ""
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        row["menu_count"] = int(row.get("menu_count") or 0)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return rows


# Flask memanggil fungsi ini setelah request selesai agar koneksi database selalu ditutup.
@app.teardown_appcontext
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def close_db(exception=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = g.pop("db", None)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db is not None:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        db.close()


# Memastikan tabel pengguna memiliki kolom role, relasi owner, dan profil kasir yang diperlukan.
def ensure_user_columns():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cursor = db.cursor()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor.execute("SHOW COLUMNS FROM users")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        fetched = cursor.fetchall()
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        columns = {row["Field"] if isinstance(row, dict) else row[0] for row in fetched}
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor.execute("PRAGMA table_info(users)")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        columns = {row[1] for row in cursor.fetchall()}

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "staff_phone" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("users", "staff_phone", "VARCHAR(40)", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "staff_position" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("users", "staff_position", "VARCHAR(100) DEFAULT 'Kasir'", "TEXT DEFAULT 'Kasir'")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "joined_date" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("users", "joined_date", "DATE", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "staff_status" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("users", "staff_status", "VARCHAR(40) DEFAULT 'Aktif'", "TEXT DEFAULT 'Aktif'")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "is_active" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("users", "is_active", "TINYINT NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "owner_id" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("users", "owner_id", "BIGINT NULL", "INTEGER")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        create_index_if_missing(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "users",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "idx_users_owner_id",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "CREATE INDEX idx_users_owner_id ON users (owner_id)",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit("CREATE INDEX IF NOT EXISTS idx_users_owner_id ON users (owner_id)")


# Menyiapkan tabel undangan kasir agar kode pendaftaran dapat dilacak masa berlakunya.
def ensure_cashier_invitation_table():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS cashier_invitations (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                owner_id BIGINT NOT NULL,
                invite_code VARCHAR(64) NOT NULL UNIQUE,
                status VARCHAR(40) NOT NULL DEFAULT 'Aktif',
                expires_at DATETIME,
                used_at DATETIME,
                used_by_cashier_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        create_index_if_missing(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "cashier_invitations",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "idx_cashier_invitations_owner_id",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "CREATE INDEX idx_cashier_invitations_owner_id ON cashier_invitations (owner_id)",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS cashier_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                invite_code TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'Aktif',
                expires_at TEXT,
                used_at TEXT,
                used_by_cashier_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_cashier_invitations_owner_id ON cashier_invitations (owner_id);
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def parse_iso_timestamp(value):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return datetime.fromisoformat(str(value))
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except ValueError:
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except ValueError:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return None


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def normalize_invite_code(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    value = str(value or "").strip().upper()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cleaned = "".join(char for char in value if char in allowed)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return cleaned[:64]


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def attach_legacy_transaction_owner_ids():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not table_exists("pos_transactions"):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = get_table_columns("pos_transactions")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "owner_id" not in columns or "staff_id" not in columns:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            UPDATE pos_transactions
            SET owner_id = (
                SELECT owner_id FROM users WHERE users.id = pos_transactions.staff_id
            )
            WHERE owner_id IS NULL
              AND staff_id IS NOT NULL
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Melakukan rollback agar perubahan parsial dibatalkan ketika proses gagal.
        db.rollback()


# Membuat kode undangan unik milik owner dengan batas waktu penggunaan tertentu.
def create_cashier_invitation(owner_id, expires_days=7):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    invitation = None
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for _ in range(5):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        invite_code = f"KASIR-{uuid.uuid4().hex[:10].upper()}"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat(timespec="seconds")
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            cursor = db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                INSERT INTO cashier_invitations (
                    owner_id, invite_code, status, expires_at
                ) VALUES (?, ?, ?, ?)
                """,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (owner_id, invite_code, "Aktif", expires_at),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
            # Melakukan commit agar seluruh perubahan transaksi tersimpan permanen.
            db.commit()
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            invitation = {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "id": cursor.lastrowid,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_id": owner_id,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "invite_code": invite_code,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "status": "Aktif",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "expires_at": expires_at,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "used_at": None,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "used_by_cashier_id": None,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "created_at": datetime.now().isoformat(timespec="seconds"),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
            # Menghentikan perulangan karena tujuan atau kondisi penghentian sudah tercapai.
            break
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except Exception:
            # Melakukan rollback agar perubahan parsial dibatalkan ketika proses gagal.
            db.rollback()
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if invitation is None:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise RuntimeError("Gagal membuat kode undangan kasir. Silakan coba lagi.")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return invitation


# Mengambil undangan berdasarkan kode yang sudah dinormalisasi untuk proses registrasi kasir.
def get_cashier_invitation(invite_code):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    invite_code = normalize_invite_code(invite_code)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not invite_code:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    row = get_db().execute(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "SELECT * FROM cashier_invitations WHERE invite_code = ?",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (invite_code,),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if row is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    invitation = dict(row)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if invitation.get("status") == "Aktif" and invitation.get("expires_at"):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        expires_at = parse_iso_timestamp(invitation["expires_at"])
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if expires_at and expires_at < datetime.now():
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            invitation["status"] = "Kedaluwarsa"
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                execute_commit(
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "UPDATE cashier_invitations SET status = ? WHERE id = ?",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    ("Kedaluwarsa", invitation["id"]),
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                )
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except Exception:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                pass
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return invitation


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_owner_latest_invitation(owner_id):
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    row = get_db().execute(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "SELECT * FROM cashier_invitations WHERE owner_id = ? ORDER BY created_at DESC LIMIT 1",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (owner_id,),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return format_cashier_invitation(dict(row)) if row else None


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_owner_invitations(owner_id, limit=5):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        get_db().execute(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "SELECT * FROM cashier_invitations WHERE owner_id = ? ORDER BY created_at DESC LIMIT ?",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (owner_id, limit),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return [format_cashier_invitation(row) for row in rows]


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_cashier_invitation(invitation):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not invitation:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    expires_at = parse_iso_timestamp(invitation.get("expires_at"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    used_at = parse_iso_timestamp(invitation.get("used_at"))
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if invitation.get("status") == "Aktif" and expires_at and expires_at < datetime.now():
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        invitation["status"] = "Kedaluwarsa"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    invitation["expires_at_display"] = expires_at.strftime("%Y-%m-%d %H:%M") if expires_at else "-"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    invitation["used_at_display"] = used_at.strftime("%Y-%m-%d %H:%M") if used_at else "-"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    invitation["is_active"] = invitation.get("status") == "Aktif"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return invitation


# Menambahkan kolom transaksi POS yang belum ada tanpa menghapus data transaksi lama.
def ensure_pos_transactions_columns():
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not table_exists("pos_transactions"):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = get_table_columns("pos_transactions")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "order_code" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "order_code", "VARCHAR(60)", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "transaction_date" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "transaction_date", "DATE", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "transaction_time" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "transaction_time", "TIME", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "customer_name" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "customer_name", "VARCHAR(255) DEFAULT 'Walk-in Customer'", "TEXT DEFAULT 'Walk-in Customer'")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "payment_method" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "payment_method", "VARCHAR(80) DEFAULT 'Tunai'", "TEXT DEFAULT 'Tunai'")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "subtotal_amount" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "subtotal_amount", "BIGINT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "discount_amount" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "discount_amount", "BIGINT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "tax_amount" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "tax_amount", "BIGINT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "operational_cost" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "operational_cost", "BIGINT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "total_amount" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "total_amount", "BIGINT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "item_count" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "item_count", "INT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "status" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "status", "VARCHAR(40) NOT NULL DEFAULT 'Selesai'", "TEXT NOT NULL DEFAULT 'Selesai'")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "owner_id" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "owner_id", "BIGINT NULL", "INTEGER")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "staff_id" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "staff_id", "BIGINT NULL", "INTEGER")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "created_at" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("pos_transactions", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TEXT")


# Membuat skema pengguna dan menjalankan migrasi kompatibilitas sebelum autentikasi digunakan.
def init_db():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(50) NOT NULL,
                owner_id BIGINT NULL,
                staff_phone VARCHAR(40),
                staff_position VARCHAR(100) DEFAULT 'Kasir',
                joined_date DATE,
                staff_status VARCHAR(40) DEFAULT 'Aktif',
                is_active TINYINT NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                `key` VARCHAR(255) PRIMARY KEY,
                `value` TEXT NOT NULL
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                owner_id INTEGER,
                staff_phone TEXT,
                staff_position TEXT DEFAULT 'Kasir',
                joined_date TEXT,
                staff_status TEXT DEFAULT 'Aktif',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_user_columns()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    attach_legacy_cashiers_to_owner()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_cashier_invitation_table()


# Memastikan tabel menu memiliki kolom harga, stok, gambar, status, dan relasi kategori.
def ensure_menu_columns():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cursor = db.cursor()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor.execute("SHOW COLUMNS FROM menus")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        fetched = cursor.fetchall()
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        columns = {row["Field"] if isinstance(row, dict) else row[0] for row in fetched}
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor.execute("PRAGMA table_info(menus)")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        columns = {row[1] for row in cursor.fetchall()}

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "name" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "name", "VARCHAR(255)", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "category" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "category", "VARCHAR(100)", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "code" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "code", "VARCHAR(100)", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "price" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "price", "BIGINT NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "stock" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "stock", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "description" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "description", "TEXT", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "image" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "image", "TEXT", "TEXT")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "is_active" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "is_active", "INTEGER NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if "category_id" not in columns:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        add_column_if_missing("menus", "category_id", "BIGINT NULL", "INTEGER")

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    migrate_legacy_menu_columns()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        create_index_if_missing(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "menus",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "idx_menus_category_id",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "CREATE INDEX idx_menus_category_id ON menus (category_id)",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit("CREATE INDEX IF NOT EXISTS idx_menus_category_id ON menus (category_id)")


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def first_existing_column(columns, candidates):
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for candidate in candidates:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if candidate in columns:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return candidate
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return None


# Menyalin nilai dari nama kolom menu versi lama ke kolom yang digunakan aplikasi saat ini.
def migrate_legacy_menu_columns():
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not table_exists("menus"):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = get_table_columns("menus")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    name_source = first_existing_column(columns, ("menu_name", "product_name", "item_name", "nama", "nama_menu", "title"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category_source = first_existing_column(columns, ("menu_category", "product_category", "kategori", "category_name"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    price_source = first_existing_column(columns, ("menu_price", "product_price", "harga", "harga_menu"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    image_source = first_existing_column(columns, ("image_url", "photo", "photo_url", "gambar", "gambar_menu"))

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if name_source:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit(f"UPDATE menus SET name = {name_source} WHERE (name IS NULL OR TRIM(name) = '') AND {name_source} IS NOT NULL")
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    execute_commit("UPDATE menus SET name = CONCAT('Menu ', id) WHERE (name IS NULL OR TRIM(name) = '')" if get_db().is_mysql else "UPDATE menus SET name = 'Menu ' || id WHERE (name IS NULL OR TRIM(name) = '')")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category_source:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit(f"UPDATE menus SET category = {category_source} WHERE (category IS NULL OR TRIM(category) = '') AND {category_source} IS NOT NULL")
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    execute_commit("UPDATE menus SET category = 'Uncategorized' WHERE category IS NULL OR TRIM(category) = ''")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if price_source:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit(f"UPDATE menus SET price = {price_source} WHERE (price IS NULL OR price = 0) AND {price_source} IS NOT NULL")
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    execute_commit("UPDATE menus SET price = 0 WHERE price IS NULL")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if image_source:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit(f"UPDATE menus SET image = {image_source} WHERE (image IS NULL OR TRIM(image) = '') AND {image_source} IS NOT NULL")

    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    rows = fetch_all_dict(get_db().execute("SELECT id, name, category, code FROM menus WHERE code IS NULL OR TRIM(code) = ''"))
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_commit(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "UPDATE menus SET code = ? WHERE id = ?",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (generate_menu_code(row.get("category"), row.get("name")), row["id"]),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def legacy_menu_field_values(menu_data):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = get_table_columns("menus")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    aliases = {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "name": ("menu_name", "product_name", "item_name", "nama", "nama_menu", "title"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "category": ("menu_category", "product_category", "kategori", "category_name"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "price": ("menu_price", "product_price", "harga", "harga_menu"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "image": ("image_url", "photo", "photo_url", "gambar", "gambar_menu"),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    values = {}
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for source_key, candidates in aliases.items():
        # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
        for column in candidates:
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if column in columns and source_key in menu_data:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                values[column] = menu_data[source_key]
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return values


# Menyimpan satu menu baru dengan susunan kolom yang sesuai skema database aktif.
def insert_menu_record(menu_data):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    values = {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "name": menu_data["name"],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "category": menu_data["category"],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "category_id": menu_data.get("category_id"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "code": menu_data["code"],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "price": menu_data["price"],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "stock": menu_data.get("stock", 0),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "description": menu_data.get("description", ""),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "image": menu_data.get("image", ""),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "is_active": 1 if menu_data.get("is_active", True) else 0,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    values.update(legacy_menu_field_values(values))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    columns = list(values.keys())
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    placeholders = ", ".join(["?"] * len(columns))
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return execute_commit(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        f"INSERT INTO menus ({', '.join(columns)}) VALUES ({placeholders})",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        tuple(values[column] for column in columns),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Memperbarui menu yang dipilih tanpa mengubah identitas record tersebut.
def update_menu_record(menu_id, menu_data):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    values = {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "name": menu_data["name"],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "category": menu_data["category"],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "category_id": menu_data.get("category_id"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "price": menu_data["price"],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for optional_key in ("stock", "description", "image", "is_active"):
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if optional_key in menu_data:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            values[optional_key] = menu_data[optional_key]
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    values.update(legacy_menu_field_values(values))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    assignments = ", ".join(f"{column} = ?" for column in values)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return execute_commit(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        f"UPDATE menus SET {assignments} WHERE id = ?",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (*values.values(), menu_id),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Menyiapkan tabel menu, kategori, dan migrasi terkait sebelum halaman manajemen atau POS dibuka.
def init_menu_table():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_category_table()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS menus (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                category VARCHAR(100) NOT NULL,
                category_id BIGINT NULL,
                code VARCHAR(100) NOT NULL UNIQUE,
                price BIGINT NOT NULL,
                stock INT NOT NULL DEFAULT 0,
                description TEXT,
                image TEXT,
                is_active TINYINT NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                `key` VARCHAR(255) PRIMARY KEY,
                `value` TEXT NOT NULL
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                category_id INTEGER,
                code TEXT NOT NULL UNIQUE,
                price INTEGER NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                image TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_menu_columns()

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    migration_done = get_app_setting("menus_seed_migration_done")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if migration_done is None:
        # Remove old hard-coded/default menu seed once, without touching users.
        execute_commit("DELETE FROM menus")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not db.is_mysql:
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                execute_commit("DELETE FROM sqlite_sequence WHERE name = 'menus'")
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except Exception:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                pass
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        set_app_setting("menus_seed_migration_done", "1")

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    migrate_menu_categories()


# Membuat tabel transaksi dan detail item yang diperlukan oleh proses checkout POS.
def init_pos_tables():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if db.is_mysql:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS pos_transactions (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                order_code VARCHAR(60) NOT NULL UNIQUE,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        ensure_pos_transactions_columns()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        attach_legacy_transaction_owner_ids()
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS pos_transaction_items (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                transaction_id BIGINT NOT NULL,
                menu_id BIGINT NULL,
                menu_name VARCHAR(255) NOT NULL,
                quantity INT NOT NULL DEFAULT 1,
                unit_price BIGINT NOT NULL DEFAULT 0,
                subtotal BIGINT NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_script_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            CREATE TABLE IF NOT EXISTS pos_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT NOT NULL UNIQUE,
                transaction_date TEXT NOT NULL,
                transaction_time TEXT NOT NULL,
                customer_name TEXT DEFAULT 'Walk-in Customer',
                payment_method TEXT DEFAULT 'Tunai',
                subtotal_amount INTEGER NOT NULL DEFAULT 0,
                discount_amount INTEGER NOT NULL DEFAULT 0,
                tax_amount INTEGER NOT NULL DEFAULT 0,
                operational_cost INTEGER NOT NULL DEFAULT 0,
                total_amount INTEGER NOT NULL DEFAULT 0,
                item_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Selesai',
                owner_id INTEGER,
                staff_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pos_transaction_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                menu_id INTEGER,
                menu_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price INTEGER NOT NULL DEFAULT 0,
                subtotal INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        ensure_pos_transactions_columns()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_pos_transactions_columns()


# Mengambil nama owner dari session untuk ditampilkan pada halaman dashboard.
def get_owner_name():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return (
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.get("full_name")
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        or session.get("name")
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        or session.get("username")
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        or "Owner"
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Menyimpan identitas, role, dan owner terkait ke session setelah autentikasi berhasil.
def set_authenticated_session(user_data):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role = normalize_role_value(user_data.get("role"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_id = user_data.get("id") if role == "owner" else user_data.get("owner_id")

    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session.permanent = True
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["user_id"] = user_data.get("id")
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["full_name"] = user_data.get("full_name")
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["name"] = user_data.get("full_name")
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["username"] = user_data.get("full_name")
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["role"] = role
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["role_label"] = role_display_name(role)
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["owner_id"] = owner_id
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session.modified = True


# Memuat ulang pengguna dari database agar session tidak mempercayai data akun yang sudah berubah.
def get_session_user():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    user_id = session.get("user_id")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not user_id:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None

    # Query ini mengambil data autentikasi terbaru untuk pengguna yang tersimpan di session.
    user = get_db().execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        """
        SELECT id, full_name, email, role, owner_id, is_active
        FROM users
        WHERE id = ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (user_id,),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return row_to_dict(user) if user else None


# Memastikan akun session masih aktif dan masih memiliki role serta relasi owner yang sah.
def refresh_authenticated_session():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    user_data = get_session_user()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not user_data:
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role = normalize_role_value(user_data.get("role"))
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if role == CASHIER_ROLE:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if int(user_data.get("is_active", 1) or 0) != 1 or not user_data.get("owner_id"):
            # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
            session.clear()
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return None
    # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
    elif role != "owner":
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    set_authenticated_session(user_data)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return user_data


# Decorator ini membatasi route umum agar hanya dapat dibuka oleh pengguna yang sudah login.
def login_required(view_func):
    # Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
    @wraps(view_func)
    # Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
    def wrapped_view(**kwargs):
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not refresh_authenticated_session():
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash("Silakan login terlebih dahulu.", "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return redirect(url_for("login"))
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return view_func(**kwargs)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return wrapped_view


# Mengarahkan owner dan kasir ke halaman kerja masing-masing setelah login.
def redirect_for_role():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role = normalize_role_value(session.get("role"))
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if role == "owner":
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_menu"))
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if role == CASHIER_ROLE:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("pos"))
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session.clear()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("login"))


# Decorator ini melindungi POS agar hanya akun kasir aktif yang dapat mengaksesnya.
def staff_required(view_func):
    # Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
    @wraps(view_func)
    # Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
    def wrapped_view(**kwargs):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        user_data = refresh_authenticated_session()
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not user_data:
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash("Silakan login terlebih dahulu.", "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return redirect(url_for("login"))
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if normalize_role_value(user_data.get("role")) != CASHIER_ROLE:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return redirect_for_role()

        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return view_func(**kwargs)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return wrapped_view


# Decorator ini memastikan hanya owner yang dapat membuka fitur manajemen dan laporan.
def owner_required(view_func):
    # Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
    @wraps(view_func)
    # Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
    def wrapped_view(**kwargs):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        user_data = refresh_authenticated_session()
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not user_data:
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash("Silakan login terlebih dahulu.", "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return redirect(url_for("login"))
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if normalize_role_value(user_data.get("role")) != "owner":
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return redirect_for_role()
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return view_func(**kwargs)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return wrapped_view


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_user_by_email(email):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return get_db().execute(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "SELECT * FROM users WHERE email = ?",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (email.strip().lower(),),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_default_owner_id():
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    row = get_db().execute(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "SELECT id FROM users WHERE LOWER(role) = ? ORDER BY id DESC LIMIT 1",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        ("owner",),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if row is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return row["id"] if isinstance(row, dict) else row[0]


# Memeriksa isian autentikasi sebelum query database dijalankan agar pesan kesalahan lebih jelas.
def validate_auth_fields(full_name=None, email=None, password=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    errors = []
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if full_name is not None and not full_name.strip():
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Nama lengkap wajib diisi.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not email or not email.strip():
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Email wajib diisi.")
    # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
    elif "@" not in email or "." not in email.split("@")[-1]:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Format email tidak valid.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not password:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Password wajib diisi.")
    # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
    elif len(password) < 6:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Password minimal 6 karakter.")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return errors


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_pos_category_filters(categories):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category_lookup = {}
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for category in categories:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_name = normalize_category_name(category)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if category_name:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            category_lookup[category_key(category_name)] = category_name
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return [category for _, category in sorted(category_lookup.items(), key=lambda item: item[1].casefold())]


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_report_datetime(value):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"{format_short_date(value.date())} {value:%H:%M} WIB"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_currency(amount):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"Rp{int(amount or 0):,}".replace(",", ".")


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_short_date(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    month_names = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"{value.day} {month_names[value.month - 1]} {value.year}"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_month_name(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    month_names = [
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Januari",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Februari",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Maret",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "April",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Mei",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Juni",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Juli",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Agustus",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "September",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Oktober",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "November",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Desember",
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ]
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"{month_names[value.month - 1]} {value.year}"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_report_period(start_date, end_date):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if start_date == end_date:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return format_short_date(start_date)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if start_date.month == end_date.month and start_date.year == end_date.year:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        month_names = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return f"{start_date.day} - {end_date.day} {month_names[start_date.month - 1]} {start_date.year}"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"{format_short_date(start_date)} - {format_short_date(end_date)}"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def parse_report_date(value):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return datetime.strptime(value, "%Y-%m-%d").date()
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except ValueError:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None


# Menentukan rentang laporan dari parameter URL dan memakai periode bawaan bila input tidak valid.
def resolve_report_period(args):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    today = datetime.now().date()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    default_start = today.replace(day=1)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    start_date = parse_report_date(args.get("date_from")) or default_start
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    end_date = parse_report_date(args.get("date_to")) or today
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if start_date > end_date:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        start_date, end_date = end_date, start_date
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return start_date, end_date


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def shift_month(source_date, month_delta):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    month_index = source_date.month - 1 + month_delta
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    year = source_date.year + month_index // 12
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    month = month_index % 12 + 1
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return date(year, month, 1)


# Menghitung omzet, jumlah transaksi, dan rata-rata transaksi pada periode serta owner yang dipilih.
def get_period_totals(start_date, end_date, owner_id=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_join = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_filter = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    params = [start_date.isoformat(), end_date.isoformat()]
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if owner_id:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_join = "LEFT JOIN users u ON u.id = t.staff_id"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_filter = "AND (t.owner_id = ? OR (t.owner_id IS NULL AND u.owner_id = ?))"
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        params.extend([owner_id, owner_id])

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    row = row_to_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT
                COALESCE(SUM(total_amount), 0) AS revenue,
                COUNT(*) AS transactions
            FROM pos_transactions t
            {owner_join}
            WHERE t.transaction_date BETWEEN ? AND ?
              AND LOWER(t.status) IN ('selesai', 'paid', 'completed', 'complete')
              {owner_filter}
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            params,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ).fetchone()
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    revenue = int(row.get("revenue") or 0)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transactions = int(row.get("transactions") or 0)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "revenue": revenue,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "profit": revenue,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "transactions": transactions,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }


# Membandingkan nilai periode berjalan dan sebelumnya untuk menghasilkan keterangan tren yang mudah dibaca.
def build_trend_text(current_value, previous_value, empty_text="Belum ada transaksi"):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    current_value = int(current_value or 0)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    previous_value = int(previous_value or 0)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if previous_value == 0:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return empty_text if current_value == 0 else "Baru ada transaksi"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    percentage = ((current_value - previous_value) / previous_value) * 100
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    sign = "+" if percentage >= 0 else "-"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"{sign}{abs(percentage):.1f}% dari periode lalu"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def trend_tone(current_value, previous_value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    current_value = int(current_value or 0)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    previous_value = int(previous_value or 0)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if previous_value == 0 or current_value == previous_value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "neutral"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return "positive" if current_value > previous_value else "negative"


# Mengelompokkan transaksi per hari sebagai sumber tabel pendapatan harian.
def fetch_daily_details(start_date, end_date, owner_id=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_join = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_filter = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    params = [start_date.isoformat(), end_date.isoformat()]
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if owner_id:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_join = "LEFT JOIN users u ON u.id = t.staff_id"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_filter = "AND (t.owner_id = ? OR (t.owner_id IS NULL AND u.owner_id = ?))"
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        params.extend([owner_id, owner_id])

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT
                t.transaction_date,
                COUNT(*) AS transactions,
                COALESCE(SUM(t.total_amount), 0) AS income
            FROM pos_transactions t
            {owner_join}
            WHERE t.transaction_date BETWEEN ? AND ?
              AND LOWER(t.status) IN ('selesai', 'paid', 'completed', 'complete')
              {owner_filter}
            GROUP BY t.transaction_date
            ORDER BY t.transaction_date DESC
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            params,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    details = []
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        income = int(row.get("income") or 0)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        detail_date = parse_report_date(str(row.get("transaction_date")))
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        details.append(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "date": format_short_date(detail_date) if detail_date else row.get("transaction_date"),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "transactions": int(row.get("transactions") or 0),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "income": format_currency(income),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "profit": format_currency(income),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return details


# Mengambil transaksi terbaru dalam periode laporan untuk ringkasan aktivitas penjualan.
def fetch_recent_transactions(start_date, end_date, limit=5, owner_id=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_filter = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    params = [start_date.isoformat(), end_date.isoformat()]
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if owner_id:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_filter = "AND (t.owner_id = ? OR (t.owner_id IS NULL AND u.owner_id = ?))"
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        params.extend([owner_id, owner_id])
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    params.append(limit)

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT
                t.order_code,
                t.transaction_date,
                t.transaction_time,
                t.customer_name,
                t.payment_method,
                t.total_amount,
                t.item_count,
                t.status,
                u.full_name AS staff_name
            FROM pos_transactions t
            LEFT JOIN users u ON u.id = t.staff_id
            WHERE t.transaction_date BETWEEN ? AND ?
              AND LOWER(t.status) IN ('selesai', 'paid', 'completed', 'complete')
              {owner_filter}
            ORDER BY t.transaction_date DESC, t.transaction_time DESC, t.id DESC
            LIMIT ?
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            params,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transactions = []
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        transaction_date = parse_report_date(str(row.get("transaction_date")))
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        transaction_time = str(row.get("transaction_time") or "")[:5]
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        transactions.append(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "id": row.get("order_code") or "-",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "date": format_short_date(transaction_date) if transaction_date else row.get("transaction_date"),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "time": transaction_time or "-",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "customer": row.get("customer_name") or "Walk-in Customer",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "method": row.get("payment_method") or "Tunai",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "staff": row.get("staff_name") or "-",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "total": format_currency(row.get("total_amount") or 0),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "items": int(row.get("item_count") or 0),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "status": str(row.get("status") or "Selesai").title(),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return transactions


# Mengelompokkan omzet berdasarkan jam agar waktu penjualan tertinggi dapat terlihat pada grafik.
def fetch_hourly_sales(start_date, end_date, owner_id=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_join = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_filter = ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    params = [start_date.isoformat(), end_date.isoformat()]
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if owner_id:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_join = "LEFT JOIN users u ON u.id = t.staff_id"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_filter = "AND (t.owner_id = ? OR (t.owner_id IS NULL AND u.owner_id = ?))"
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        params.extend([owner_id, owner_id])

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT t.transaction_time, t.total_amount
            FROM pos_transactions t
            {owner_join}
            WHERE t.transaction_date BETWEEN ? AND ?
              AND LOWER(t.status) IN ('selesai', 'paid', 'completed', 'complete')
              {owner_filter}
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            params,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    hourly_values = {hour: 0 for hour in range(8, 23)}
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            hour = int(str(row.get("transaction_time") or "")[:2])
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except ValueError:
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if hour in hourly_values:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            hourly_values[hour] += int(row.get("total_amount") or 0)

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    max_value = max(hourly_values.values()) if hourly_values else 0
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    chart = []
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for hour, amount in hourly_values.items():
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        height = int((amount / max_value) * 100) if max_value else 0
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        chart.append(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "hour": f"{hour:02d}:00",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "amount": format_currency(amount),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "height": height,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "has_value": amount > 0,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "is_peak": max_value > 0 and amount == max_value,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "label_visible": hour % 2 == 0,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return chart


# Menyusun perbandingan omzet beberapa bulan sampai bulan akhir laporan.
def build_monthly_summary(end_date, owner_id=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    current_month = end_date.replace(day=1)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = []
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for month_delta in (-2, -1, 0):
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        month_start = shift_month(current_month, month_delta)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        month_end = shift_month(month_start, 1) - timedelta(days=1)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        totals = get_period_totals(month_start, month_end, owner_id)
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        rows.append(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "month": format_month_name(month_start),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "income": format_currency(totals["revenue"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "profit": format_currency(totals["profit"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "is_current": month_delta == 0,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return rows


# Menggabungkan seluruh query dan perhitungan menjadi satu data laporan yang siap dikirim ke template.
def build_financial_report(args=None):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_pos_tables()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    args = args or request.args
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    start_date, end_date = resolve_report_period(args)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    now = datetime.now()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_id = session.get("user_id") if session.get("role") == "owner" else None
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    totals = get_period_totals(start_date, end_date, owner_id)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    day_count = max((end_date - start_date).days + 1, 1)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    previous_end = start_date - timedelta(days=1)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    previous_start = previous_end - timedelta(days=day_count - 1)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    previous_totals = get_period_totals(previous_start, previous_end, owner_id)

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    today = now.date()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    today_totals = get_period_totals(today, today, owner_id)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    average_income = totals["revenue"] // day_count
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    previous_average = previous_totals["revenue"] // day_count if day_count else 0
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    period_label = format_report_period(start_date, end_date)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    daily_details = fetch_daily_details(start_date, end_date, owner_id)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    recent_transactions = fetch_recent_transactions(start_date, end_date, limit=5, owner_id=owner_id)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "period": period_label,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "calendar_label": period_label,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "printed_at": format_report_datetime(now),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "date_from": start_date.isoformat(),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "date_to": end_date.isoformat(),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "has_data": totals["transactions"] > 0,
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        "dashboard_metrics": [
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "label": "Total Pendapatan",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "value": format_currency(totals["revenue"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "trend": build_trend_text(totals["revenue"], previous_totals["revenue"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "tone": trend_tone(totals["revenue"], previous_totals["revenue"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "label": "Laba Bersih",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "value": format_currency(totals["profit"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "trend": build_trend_text(totals["profit"], previous_totals["profit"], "Belum ada transaksi"),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "tone": trend_tone(totals["profit"], previous_totals["profit"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "label": "Total Transaksi",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "value": str(totals["transactions"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "trend": build_trend_text(totals["transactions"], previous_totals["transactions"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "tone": trend_tone(totals["transactions"], previous_totals["transactions"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "label": "Pendapatan Hari Ini",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "value": format_currency(today_totals["revenue"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "trend": "Dari transaksi tanggal ini",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "tone": "neutral",
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "label": "Rata-rata Pendapatan Harian",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "value": format_currency(average_income),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "trend": build_trend_text(average_income, previous_average),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "tone": trend_tone(average_income, previous_average),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ],
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        "print_summary": [
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            {"label": "Total Pendapatan (Revenue)", "value": format_currency(totals["revenue"]), "tone": "normal"},
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            {"label": "Laba Bersih", "value": format_currency(totals["profit"]), "tone": "success"},
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            {"label": "Total Transaksi", "value": str(totals["transactions"]), "tone": "normal"},
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            {"label": "Rata-rata Pendapatan Harian", "value": format_currency(average_income), "tone": "normal"},
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ],
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "net_profit": format_currency(totals["profit"]),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "net_profit_trend": build_trend_text(totals["profit"], previous_totals["profit"], "Belum ada data periode lalu"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "hourly_sales": fetch_hourly_sales(start_date, end_date, owner_id),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "daily_details": daily_details,
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        "daily_totals": {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "transactions": str(totals["transactions"]),
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "income": format_currency(totals["revenue"]),
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "profit": format_currency(totals["profit"]),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        },
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "recent_transactions": recent_transactions,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "print_transactions": fetch_recent_transactions(start_date, end_date, limit=20, owner_id=owner_id),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "monthly_summary": build_monthly_summary(end_date, owner_id),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "daily_income_rows": daily_details[:6],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }


# Memvalidasi harga menu agar memenuhi batas minimum dan kelipatan nominal yang diterima aplikasi.
def parse_menu_price(price_value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    price = int(price_value)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if price < MIN_MENU_PRICE or price % MIN_MENU_PRICE != 0:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return price


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def build_menu_code_prefix(category, name=""):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    source = str(category or name or "Menu").upper()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cleaned = re.sub(r"[^A-Z0-9]+", " ", source).strip()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    first_word = cleaned.split()[0] if cleaned else "MENU"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    prefix = re.sub(r"[^A-Z0-9]", "", first_word)[:3]
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return (prefix or "MNU").ljust(3, "X")


# Membuat kode menu unik berdasarkan kategori dan nama supaya setiap produk mudah dikenali.
def generate_menu_code(category, name=""):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    prefix = build_menu_code_prefix(category, name)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "SELECT code FROM menus WHERE code LIKE ?",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (f"{prefix}-%",),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    highest_number = 0
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for row in rows:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        match = pattern.match(str(row.get("code") or "").upper())
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if match:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            highest_number = max(highest_number, int(match.group(1)))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    next_number = highest_number + 1
    # Perulangan ini terus berjalan selama kondisi yang ditentukan masih benar.
    while True:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        candidate = f"{prefix}-{next_number:03d}"
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        exists = db.execute("SELECT id FROM menus WHERE code = ?", (candidate,)).fetchone()
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not exists:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return candidate
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        next_number += 1


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def parse_staff_date(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    value = str(value or "").strip()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return ""
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return datetime.strptime(value, date_format).date().isoformat()
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except ValueError:
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return ""


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_staff_date(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    value = str(value or "").strip()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not value:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "-"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    date_part = value[:10]
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    parsed_date = parse_report_date(date_part)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if parsed_date:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return format_short_date(parsed_date)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return value


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def normalize_staff_status(status, is_active=True):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    status = str(status or "Aktif").strip().title()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if status not in STAFF_STATUSES:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        status = "Aktif"
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not is_active:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "Nonaktif"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return status


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def staff_status_tone(status):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    status_key = str(status or "").strip().lower()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if status_key == "aktif":
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "active"
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if status_key == "cuti":
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "leave"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return "inactive"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def staff_initial(name):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    name = str(name or "").strip()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return name[:1].upper() if name else "K"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def format_staff_member(row):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    data = row_to_dict(row)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    is_active = int(data.get("is_active", 1) or 0) == 1
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    status = normalize_staff_status(data.get("staff_status"), is_active)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    joined_date = data.get("joined_date") or data.get("created_at")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "id": data.get("id"),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "full_name": data.get("full_name") or "Kasir",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "initial": staff_initial(data.get("full_name")),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "email": data.get("email") or "-",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "phone": data.get("staff_phone") or "-",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "phone_value": data.get("staff_phone") or "",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "position": "Kasir",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "joined_date": format_staff_date(joined_date),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "joined_date_value": parse_staff_date(joined_date) or datetime.now().date().isoformat(),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "status": status,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "status_tone": staff_status_tone(status),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "is_active": is_active,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }


# Mengambil dan menormalkan field request form kasir sebelum divalidasi atau disimpan.
def get_staff_form_data():
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    is_active = request.form.get("is_active", "1") == "1"
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    status = normalize_staff_status(request.form.get("staff_status", "Aktif"), is_active)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if status == "Nonaktif":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        is_active = False
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        "full_name": request.form.get("full_name", "").strip(),
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        "email": request.form.get("email", "").strip().lower(),
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        "staff_phone": request.form.get("staff_phone", "").strip(),
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        "staff_position": request.form.get("staff_position", "Kasir").strip() or "Kasir",
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        "joined_date": request.form.get("joined_date", "").strip(),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "staff_status": status,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "is_active": is_active,
    }


# Memastikan profil kasir memiliki data wajib dan nilai status yang diperbolehkan.
def validate_staff_form(form_data, require_email=True):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    errors = []
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not form_data["full_name"]:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Nama lengkap wajib diisi.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if require_email:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["email"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Email wajib diisi.")
        # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
        elif "@" not in form_data["email"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Format email tidak valid.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not form_data["staff_phone"]:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Nomor telepon wajib diisi.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not form_data["staff_position"]:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Role kasir wajib diisi.")
    # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
    elif form_data["staff_position"] not in STAFF_POSITIONS:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Role kasir tidak valid.")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    joined_date = parse_staff_date(form_data["joined_date"])
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not joined_date:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Tanggal bergabung wajib diisi dengan format tanggal yang valid.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if form_data["staff_status"] not in STAFF_STATUSES:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Status kasir tidak valid.")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return errors, joined_date


# Menentukan label shift kasir dari waktu saat ini untuk dicatat pada transaksi.
def get_current_shift():
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    current_hour = datetime.now().hour
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if 5 <= current_hour < 12:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "Pagi"
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if 12 <= current_hour < 18:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "Siang"
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return "Malam"


# Mengubah nominal dari request POS menjadi angka dan menolak nilai negatif atau tidak valid.
def parse_pos_amount(value, field_label):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if value in (None, ""):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return 0
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        amount = int(str(value).strip().replace(".", "").replace(",", ""))
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except (TypeError, ValueError):
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError(f"{field_label} harus berupa angka.")
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if amount < 0:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError(f"{field_label} tidak boleh negatif.")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return amount


# Memeriksa bentuk item keranjang agar ID dan jumlah beli aman digunakan dalam transaksi.
def normalize_pos_items(raw_items):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not isinstance(raw_items, list) or not raw_items:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError("Keranjang masih kosong.")

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    items = {}
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for raw_item in raw_items:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not isinstance(raw_item, dict):
            # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
            raise ValueError("Data item POS tidak valid.")
        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            menu_id = int(raw_item.get("menu_id"))
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            quantity = int(raw_item.get("quantity", 1))
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except (TypeError, ValueError):
            # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
            raise ValueError("Data item POS tidak valid.")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if menu_id < 1 or quantity < 1:
            # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
            raise ValueError("Jumlah item POS tidak valid.")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if quantity > 999:
            # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
            raise ValueError("Jumlah item terlalu besar.")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        items[menu_id] = items.get(menu_id, 0) + quantity

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return items


# Membuat kode pesanan unik berbasis waktu dan UUID untuk menghindari benturan antar-checkout.
def generate_order_code(now=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    now = now or datetime.now()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"POS-{now:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4].upper()}"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def generate_invoice_code(now=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    now = now or datetime.now()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"INV{now:%Y%m%d%H%M%S}{uuid.uuid4().hex[:3].upper()}"


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def normalize_order_code(value):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    value = str(value or "").strip().upper()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cleaned = "".join(char for char in value if char in allowed)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return cleaned[:60]


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def build_qris_payload(order_code, total_amount, timestamp):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"ORDER={order_code}\nTOTAL={int(total_amount or 0)}\nTIME={timestamp}"


# Menyimpan detail pembayaran sementara di session agar halaman sukses dan struk dapat menampilkannya.
def remember_payment_details(order_code, payment_method, total_amount, received_amount=None, change_amount=None):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    received = int(received_amount if received_amount is not None else total_amount or 0)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    change = int(change_amount if change_amount is not None else max(received - int(total_amount or 0), 0))
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["last_payment"] = {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "order_code": order_code,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "payment_method": payment_method,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "total_amount": int(total_amount or 0),
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "received_amount": received,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "change_amount": change,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session.modified = True


# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_payment_details(order_code, transaction):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    stored = session.get("last_payment") or {}
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if stored.get("order_code") == order_code:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "method": stored.get("payment_method") or transaction.get("payment_method") or "-",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "received_amount": int(stored.get("received_amount") or 0),
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "change_amount": int(stored.get("change_amount") or 0),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    total_amount = int(transaction.get("total_amount") or 0)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "method": transaction.get("payment_method") or "-",
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "received_amount": total_amount,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "change_amount": 0,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }


# Mengambil header dan item transaksi berdasarkan kode pesanan untuk halaman pembayaran dan struk.
def fetch_transaction_detail(order_code):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_pos_tables()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction = row_to_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            SELECT
                t.id,
                t.order_code,
                t.transaction_date,
                t.transaction_time,
                t.customer_name,
                t.payment_method,
                t.subtotal_amount,
                t.total_amount,
                t.item_count,
                t.status,
                u.full_name AS staff_name
            FROM pos_transactions t
            LEFT JOIN users u ON u.id = t.staff_id
            WHERE t.order_code = ?
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (order_code,),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ).fetchone()
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not transaction:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return None

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    items = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            SELECT menu_name, quantity, unit_price, subtotal
            FROM pos_transaction_items
            WHERE transaction_id = ?
            ORDER BY id ASC
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (transaction["id"],),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction_date = parse_report_date(str(transaction.get("transaction_date") or ""))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction["date_display"] = format_short_date(transaction_date) if transaction_date else transaction.get("transaction_date")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction["time_display"] = str(transaction.get("transaction_time") or "")[:5]
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction["total_display"] = format_currency(transaction.get("total_amount") or 0)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction["subtotal_display"] = format_currency(transaction.get("subtotal_amount") or 0)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction["items"] = [
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            **item,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "unit_price_display": format_currency(item.get("unit_price") or 0),
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "subtotal_display": format_currency(item.get("subtotal") or 0),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
        # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
        for item in items
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ]
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return transaction


# Memvalidasi checkout, mengunci stok, menyimpan transaksi beserta item, lalu melakukan commit sebagai satu proses.
def create_pos_transaction(data):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_pos_tables()

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    items = normalize_pos_items(data.get("items"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    customer_name = str(data.get("customer_name") or "").strip() or "Walk-in Customer"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    payment_method = str(data.get("payment_method") or "Tunai").strip() or "Tunai"
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if payment_method.lower() in {"tunai", "cash"}:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        payment_method = "Cash"
    # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
    elif payment_method.lower() == "qris":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        payment_method = "QRIS"
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError("Metode pembayaran hanya boleh Cash atau QRIS.")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    discount_amount = parse_pos_amount(data.get("discount_amount"), "Diskon")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    tax_amount = 0
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    operational_cost = 0

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    placeholders = ", ".join(["?"] * len(items))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    menu_rows = fetch_all_dict(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT id, name, price, stock, is_active
            FROM menus
            WHERE id IN ({placeholders})
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            tuple(items.keys()),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    menu_map = {int(row["id"]): row for row in menu_rows}

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    prepared_items = []
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    validation_errors = []
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    subtotal_amount = 0
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    item_count = 0

    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for menu_id, quantity in items.items():
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        menu = menu_map.get(menu_id)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if menu is None:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            validation_errors.append(f"Menu ID {menu_id} tidak ditemukan.")
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        menu_name = menu.get("name") or "Menu"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        is_active = int(menu.get("is_active", 0) or 0) == 1
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        stock = int(menu.get("stock") or 0)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        unit_price = int(menu.get("price") or 0)

        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not is_active:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            validation_errors.append(f"{menu_name} sedang nonaktif.")
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if quantity > stock:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            validation_errors.append(f"Stok {menu_name} tidak cukup. Tersedia {stock}.")
            # Melewati sisa iterasi ini dan melanjutkan ke elemen berikutnya.
            continue

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        line_subtotal = unit_price * quantity
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        subtotal_amount += line_subtotal
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        item_count += quantity
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        prepared_items.append(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "menu_id": menu_id,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "menu_name": menu_name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "quantity": quantity,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "unit_price": unit_price,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "subtotal": line_subtotal,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "stock": stock,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if validation_errors:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError(" ".join(validation_errors))
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if discount_amount > subtotal_amount:
        # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
        raise ValueError("Diskon tidak boleh lebih besar dari subtotal.")

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    total_amount = subtotal_amount - discount_amount
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if payment_method == "Cash":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        received_amount = parse_pos_amount(data.get("received_amount"), "Nominal diterima")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if received_amount < total_amount:
            # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
            raise ValueError("Nominal diterima kurang dari total pembayaran.")

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    now = datetime.now()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    order_code = normalize_order_code(data.get("order_code")) or generate_order_code(now)

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_id = session.get("owner_id")
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        cursor = db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            INSERT INTO pos_transactions (
                order_code, transaction_date, transaction_time, customer_name,
                payment_method, subtotal_amount, discount_amount, tax_amount,
                operational_cost, total_amount, item_count, status, owner_id, staff_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            (
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                order_code,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                now.date().isoformat(),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                now.strftime("%H:%M:%S"),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                customer_name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                payment_method,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                subtotal_amount,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                discount_amount,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                tax_amount,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                operational_cost,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                total_amount,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                item_count,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "Selesai",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                owner_id,
                # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
                session.get("user_id"),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            ),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        transaction_id = cursor.lastrowid

        # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
        for item in prepared_items:
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            stock_update = db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                UPDATE menus
                SET stock = stock - ?
                WHERE id = ? AND stock >= ?
                """,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (item["quantity"], item["menu_id"], item["quantity"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if getattr(stock_update, "rowcount", 0) != 1:
                # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
                raise ValueError(f"Stok {item['menu_name']} baru saja berubah. Silakan cek ulang keranjang.")

            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                INSERT INTO pos_transaction_items (
                    transaction_id, menu_id, menu_name, quantity, unit_price, subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                (
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    transaction_id,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    item["menu_id"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    item["menu_name"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    item["quantity"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    item["unit_price"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    item["subtotal"],
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                ),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            item["stock_remaining"] = item["stock"] - item["quantity"]

        # Melakukan commit agar seluruh perubahan transaksi tersimpan permanen.
        db.commit()
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Melakukan rollback agar perubahan parsial dibatalkan ketika proses gagal.
        db.rollback()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        raise

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return {
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "order_code": order_code,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "subtotal_amount": subtotal_amount,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "discount_amount": discount_amount,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "total_amount": total_amount,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "item_count": item_count,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "items": prepared_items,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    }


# Memvalidasi dan menyimpan gambar menu ke Cloudinary atau folder lokal sesuai konfigurasi.
def save_menu_image(uploaded_file):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not uploaded_file or not uploaded_file.filename:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "", None

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    extension = Path(uploaded_file.filename).suffix.lower()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    allowed_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if extension not in allowed_extensions:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "", "Format gambar tidak valid. Gunakan PNG, JPG, JPEG, atau WEBP."

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    cloudinary_ready = CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if cloudinary_ready:
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if cloudinary is None:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return "", "Paket Cloudinary belum terpasang. Jalankan pip install -r requirements.txt."

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        filename = secure_filename(uploaded_file.filename)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        public_id = f"{Path(filename).stem}-{uuid.uuid4().hex[:12]}"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        upload_options = {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "public_id": public_id,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "resource_type": "image",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "overwrite": False,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if CLOUDINARY_FOLDER:
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            upload_options["folder"] = CLOUDINARY_FOLDER

        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            uploaded_file.stream.seek(0)
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            result = cloudinary.uploader.upload(uploaded_file.stream, **upload_options)
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except Exception:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return "", "Gagal mengunggah gambar ke Cloudinary. Periksa konfigurasi .env Anda."

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        image_url = result.get("secure_url") or result.get("url")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not image_url:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return "", "Cloudinary tidak mengembalikan URL gambar."
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return image_url, None

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    filename = secure_filename(uploaded_file.filename)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    target_path = app.config["UPLOAD_FOLDER"] / unique_name
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    uploaded_file.stream.seek(0)
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    uploaded_file.save(target_path)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return f"uploads/menu/{unique_name}", None


# Helper ini tersedia di Jinja untuk memilih URL gambar remote atau aset lokal secara aman.
@app.template_global()
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def menu_image_url(image_path):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not image_path:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return ""

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    image_path = str(image_path).strip()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if image_path.startswith(("http://", "https://", "//")):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return image_path
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return url_for("static", filename=image_path.lstrip("/"))


# Route pembuka menampilkan pilihan masuk, kecuali pengguna sudah memiliki session yang valid.
@app.route("/")
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def opening():
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id") and refresh_authenticated_session():
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect_for_role()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id"):
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template("opening.html")


# Route login menerima tampilan form melalui GET dan memproses kredensial melalui POST.
@app.route("/login", methods=["GET", "POST"])
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def login():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id") and refresh_authenticated_session():
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect_for_role()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id"):
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        email = request.form.get("email", "").strip().lower()
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        password = request.form.get("password", "")

        # Validasi awal mencegah query autentikasi dijalankan dengan isian kosong atau format email salah.
        errors = validate_auth_fields(email=email, password=password)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if errors:
            # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
            for error in errors:
                # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
                flash(error, "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template("login.html", email=email)

        # Password hash dibandingkan setelah akun ditemukan agar password asli tidak pernah disimpan.
        user = get_user_by_email(email)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if user is None or not check_password_hash(user["password_hash"], password):
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash("Email atau password salah. Cek lagi email yang terdaftar dan password saat registrasi.", "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template("login.html", email=email)

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        user_data = row_to_dict(user)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        user_role = normalize_role_value(user_data.get("role"))
        # Kasir nonaktif ditolak meskipun password benar karena owner telah membatasi aksesnya.
        if user_role == CASHIER_ROLE and int(user_data.get("is_active", 1) or 0) != 1:
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash("Akun kasir ini sedang nonaktif. Silakan hubungi Owner.", "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template("login.html", email=email)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if user_role == CASHIER_ROLE and not user_data.get("owner_id"):
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash("Akun kasir belum terhubung dengan Owner. Silakan hubungi Owner untuk dibuatkan ulang.", "error")
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template("login.html", email=email)

        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        set_authenticated_session(user_data)
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash(f"Login sebagai {role_display_name(user_role)} berhasil.", "success")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect_for_role()

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    registered_email = session.pop("registered_email", "")
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    query_email = request.args.get("email", "").strip().lower()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template("login.html", email=query_email or registered_email)


# Memproses form registrasi owner atau kasir berdasarkan parameter role yang diberikan route.
def register_user(role):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role = normalize_role_value(role)
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    full_name = request.form.get("full_name", "").strip()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    email = request.form.get("email", "").strip().lower()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    password = request.form.get("password", "")
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    password_confirm = request.form.get("password_confirm", "")
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    staff_phone = request.form.get("staff_phone", "").strip()

    # Seluruh field diperiksa sebelum pembuatan password hash dan penyimpanan akun.
    errors = validate_auth_fields(full_name=full_name, email=email, password=password)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if password != password_confirm:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors.append("Password dan konfirmasi password harus sama.")

    # Akun kasir harus terkait dengan owner agar data POS dan laporan memiliki pemilik yang jelas.
    if role == CASHIER_ROLE:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_id = get_default_owner_id()
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not owner_id:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Belum ada akun Owner. Daftarkan Owner terlebih dahulu sebelum membuat akun kasir.")
    # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
    else:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_id = None

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if errors:
        # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
        for error in errors:
            # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
            flash(error, "error")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        template_name = "register_owner.html" if role == "owner" else "register_staff.html"
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return render_template(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            template_name,
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            full_name=full_name,
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            email=email,
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            staff_phone=staff_phone,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    password_hash = generate_password_hash(password)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Penyimpanan dibungkus transaksi agar akun tidak tersimpan sebagian jika database gagal.
    try:
        # Query kasir menyimpan profil operasional tambahan, sedangkan owner hanya memerlukan data akun utama.
        if role == CASHIER_ROLE:
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            cursor = db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                INSERT INTO users (
                    full_name, email, password_hash, role, owner_id,
                    staff_phone, staff_position, joined_date, staff_status, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                (
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    full_name,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    email,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    password_hash,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    role,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    owner_id,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    staff_phone,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Kasir",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    datetime.now().date().isoformat(),
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Aktif",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    1,
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                ),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            cashier_id = cursor.lastrowid
        # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
        else:
            # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
            cursor = db.execute(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                INSERT INTO users (full_name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (full_name, email, password_hash, role),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            owner_id = cursor.lastrowid
        # Melakukan commit agar seluruh perubahan transaksi tersimpan permanen.
        db.commit()  # Menetapkan pendaftaran setelah seluruh query akun berhasil.
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Melakukan rollback agar perubahan parsial dibatalkan ketika proses gagal.
        db.rollback()  # Membatalkan perubahan parsial agar database tetap konsisten.
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Email sudah terdaftar atau database sedang bermasalah. Silakan gunakan email lain atau coba lagi.", "error")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        template_name = "register_owner.html" if role == "owner" else "register_staff.html"
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return render_template(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            template_name,
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            full_name=full_name,
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            email=email,
            # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
            staff_phone=staff_phone,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role_label = role_display_name(role)

    # Email konfirmasi memberi tahu pengguna bahwa akun dan role berhasil didaftarkan.
    send_email(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        email,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "Registrasi Kyloffee Berhasil",
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        <h2>Halo {full_name}</h2>
        <p>Akun Kyloffee kamu berhasil dibuat.</p>
        <p>Role akun: <b>{role_label}</b></p>
        <p>Silakan login menggunakan email dan password yang sudah didaftarkan.</p>
        <br>
        <p>Kyloffee Team</p>
        """
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
    flash(f"Registrasi {role_label} berhasil, silakan login.", "success")
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session["registered_email"] = email
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("login", email=email))  # Mengarahkan pengguna ke login dengan email yang baru terdaftar.


# Route ini menampilkan dan memproses form pendaftaran khusus owner.
@app.route("/register/owner", methods=["GET", "POST"])
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def register_owner():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id") and refresh_authenticated_session():
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect_for_role()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id"):
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return register_user("owner")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template("register_owner.html")


# Route ini menampilkan dan memproses form kasir dengan role staff internal.
@app.route("/register/kasir", methods=["GET", "POST"])
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def register_cashier():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id") and refresh_authenticated_session():
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect_for_role()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if session.get("user_id"):
        # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
        session.clear()
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return register_user("staff")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template("register_staff.html")


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/register/staff", methods=["GET", "POST"])
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def register_staff():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return register_cashier()


# Dashboard umum memakai decorator login lalu meneruskan pengguna sesuai role-nya.
@app.route("/dashboard")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@login_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def dashboard():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect_for_role()


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/owner/dashboard")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_dashboard():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("owner_menu"))


# Route owner ini menampilkan menu secara bertahap dengan pagination agar tabel tetap ringan.
@app.route("/owner/menu")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_menu():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    page = request.args.get("page", 1, type=int)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    per_page = 8

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if page < 1:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        page = 1

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    offset = (page - 1) * per_page
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    total = fetch_scalar(db.execute("SELECT COUNT(*) FROM menus"))
    # Query menggabungkan menu dan kategori agar nama kategori terbaru tampil di tabel owner.
    menus = db.execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        """
        SELECT
            m.id,
            m.name,
            COALESCE(c.name, m.category) AS category,
            m.category_id,
            m.code,
            m.price,
            m.stock,
            m.image,
            m.is_active
        FROM menus m
        LEFT JOIN categories c ON c.id = m.category_id
        ORDER BY m.id DESC
        LIMIT ? OFFSET ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (per_page, offset),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchall()

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    total_pages = max(1, (total + per_page - 1) // per_page)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_menu.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="menu",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        menus=menus,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        page=page,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        total_pages=total_pages,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        total=total,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        per_page=per_page,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route ini dibatasi untuk owner dan menangani tampilan serta penyimpanan menu baru.
@app.route("/owner/menu/add", methods=["GET", "POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_menu_add():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category_options = get_category_options()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data = {
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "name": request.form.get("name", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "category_id": request.form.get("category_id", "").strip(),
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "code": "",
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "price": request.form.get("price", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "stock": request.form.get("stock", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "description": request.form.get("description", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "is_active": request.form.get("is_active", "1") == "1",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        selected_category = get_menu_category_from_value(form_data["category_id"])

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors = []
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["name"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Nama item wajib diisi.")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not category_options:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Belum ada kategori. Tambahkan kategori terlebih dahulu.")
        # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
        elif not form_data["category_id"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Kategori wajib dipilih.")
        # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
        elif not selected_category:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Kategori tidak valid.")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["price"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Harga satuan wajib diisi.")
        # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
        else:
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                price = parse_menu_price(form_data["price"])
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except ValueError:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                errors.append("Harga satuan harus berupa angka minimal Rp 500 dan kelipatan Rp 500.")
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                price = None
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["stock"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Stok wajib diisi.")
        # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
        else:
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                stock = int(form_data["stock"])
                # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
                if stock < 0:
                    # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
                    raise ValueError
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except ValueError:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                errors.append("Stok harus berupa angka.")
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                stock = None
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["description"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Deskripsi wajib diisi.")

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        image_path = ""
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if request.files.get("image") and request.files["image"].filename:
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            image_path, image_error = save_menu_image(request.files["image"])
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if image_error:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                errors.append(image_error)

        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if errors:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_menu_add.html",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                owner_name=get_owner_name(),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                active_page="menu",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                category_options=category_options,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                form_data=form_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                errors=errors,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_name = selected_category["name"]
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        menu_code = generate_menu_code(category_name, form_data["name"])

        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        insert_menu_record(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "name": form_data["name"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category": category_name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category_id": selected_category["id"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "code": menu_code,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "price": price,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "stock": stock,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "description": form_data["description"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "image": image_path,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "is_active": form_data["is_active"],
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Menu berhasil ditambahkan.", "success")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_menu"))

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_menu_add.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="menu",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_options=category_options,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data={},
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors=[],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route edit menerima ID menu dari URL dan hanya menyimpan perubahan setelah validasi form berhasil.
@app.route("/owner/menu/<int:menu_id>/edit", methods=["GET", "POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_menu_edit(menu_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    menu = db.execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        """
        SELECT m.*, COALESCE(c.name, m.category) AS category_name
        FROM menus m
        LEFT JOIN categories c ON c.id = m.category_id
        WHERE m.id = ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (menu_id,),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if menu is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Menu tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_menu"))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category_options = get_category_options()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data = {
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "name": request.form.get("name", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "category_id": request.form.get("category_id", "").strip(),
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "code": menu["code"],
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "price": request.form.get("price", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "stock": request.form.get("stock", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "description": request.form.get("description", "").strip(),
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            "is_active": request.form.get("is_active", "1") == "1",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        selected_category = get_menu_category_from_value(form_data["category_id"])

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors = []
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["name"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Nama item wajib diisi.")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not category_options:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Belum ada kategori. Tambahkan kategori terlebih dahulu.")
        # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
        elif not form_data["category_id"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Kategori wajib dipilih.")
        # Cabang ini diperiksa ketika kondisi sebelumnya tidak terpenuhi.
        elif not selected_category:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Kategori tidak valid.")
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["price"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Harga satuan wajib diisi.")
        # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
        else:
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                price = parse_menu_price(form_data["price"])
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except ValueError:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                errors.append("Harga satuan harus berupa angka minimal Rp 500 dan kelipatan Rp 500.")
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                price = None
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["stock"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Stok wajib diisi.")
        # Cabang alternatif ini dijalankan ketika kondisi sebelumnya tidak terpenuhi.
        else:
            # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
            try:
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                stock = int(form_data["stock"])
                # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
                if stock < 0:
                    # Menghentikan proses dengan error terkontrol karena data tidak memenuhi aturan.
                    raise ValueError
            # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
            except ValueError:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                errors.append("Stok harus berupa angka.")
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                stock = None
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if not form_data["description"]:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            errors.append("Deskripsi wajib diisi.")

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        image_path = menu["image"] or ""
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if request.files.get("image") and request.files["image"].filename:
            # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
            image_path, image_error = save_menu_image(request.files["image"])
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if image_error:
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                errors.append(image_error)

        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if errors:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_menu_edit.html",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                owner_name=get_owner_name(),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                active_page="menu",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                category_options=category_options,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                menu=dict(menu),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                form_data=form_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                errors=errors,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_name = selected_category["name"]
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        update_menu_record(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            menu_id,
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "name": form_data["name"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category": category_name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category_id": selected_category["id"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "price": price,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "stock": stock,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "description": form_data["description"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "image": image_path,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "is_active": 1 if form_data["is_active"] else 0,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Menu berhasil diperbarui.", "success")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_menu"))

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_menu_edit.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="menu",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_options=category_options,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        menu=dict(menu),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data={},
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors=[],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Penghapusan menu dibatasi ke POST dan owner untuk mencegah perubahan data dari tautan biasa.
@app.route("/owner/menu/<int:menu_id>/delete", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_menu_delete(menu_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    menu = db.execute("SELECT id FROM menus WHERE id = ?", (menu_id,)).fetchone()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if menu is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Menu tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_menu"))

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    execute_commit("DELETE FROM menus WHERE id = ?", (menu_id,))
    # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
    flash("Menu berhasil dihapus.", "success")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("owner_menu"))


# Menyiapkan data kategori, pencarian, dan kondisi modal sebelum merender halaman manajemen kategori.
def render_owner_categories(category_form=None):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    search = request.args.get("q", "").strip()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_categories.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="categories",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        categories=fetch_category_management_rows(search),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        search=search,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_form=category_form or {},
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route kategori menampilkan daftar melalui GET dan membuat kategori baru melalui POST.
@app.route("/owner/categories", methods=["GET", "POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_categories():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        payload, errors = validate_category_payload(request.form)
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if errors:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_owner_categories(
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                {
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "mode": "create",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "name": payload["name"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "description": payload["description"] or "",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "errors": errors,
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                }
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            execute_commit(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                INSERT INTO categories (name, name_key, description)
                VALUES (?, ?, ?)
                """,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                (payload["name"], category_key(payload["name"]), payload["description"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except Exception:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_owner_categories(
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                {
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "mode": "create",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "name": payload["name"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "description": payload["description"] or "",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "errors": {"name": "Nama kategori sudah digunakan."},
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                }
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Kategori berhasil ditambahkan.", "success")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_categories"))

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_owner_categories()


# Route ini memperbarui kategori tertentu setelah memastikan ID dan nama kategori valid.
@app.route("/owner/categories/<int:category_id>/edit", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_category_edit(category_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_category_by_id(category_id)

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Kategori tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_categories"))

    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    payload, errors = validate_category_payload(request.form, exclude_id=category_id)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if errors:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return render_owner_categories(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "mode": "edit",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "id": category_id,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "name": payload["name"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "description": payload["description"] or "",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "errors": errors,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            UPDATE categories
            SET name = ?, name_key = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (payload["name"], category_key(payload["name"]), payload["description"], category_id),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit("UPDATE menus SET category = ? WHERE category_id = ?", (payload["name"], category_id))
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return render_owner_categories(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "mode": "edit",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "id": category_id,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "name": payload["name"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "description": payload["description"] or "",
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "errors": {"name": "Nama kategori sudah digunakan."},
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )

    # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
    flash("Kategori berhasil diperbarui.", "success")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("owner_categories"))


# Kategori hanya dapat dihapus bila aturan relasi menu mengizinkannya agar data menu tidak kehilangan kategori.
@app.route("/owner/categories/<int:category_id>/delete", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_category_delete(category_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_category_by_id(category_id)

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Kategori tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_categories"))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    menu_count = fetch_scalar(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        get_db().execute("SELECT COUNT(*) FROM menus WHERE category_id = ?", (category_id,))
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ) or 0
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if menu_count > 0:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            f"Kategori ini masih digunakan oleh {menu_count} menu. Pindahkan menu ke kategori lain sebelum menghapus kategori.",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "error",
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_categories"))

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    execute_commit("DELETE FROM categories WHERE id = ?", (category_id,))
    # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
    flash("Kategori berhasil dihapus.", "success")
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("owner_categories"))


# Endpoint JSON ini menyediakan daftar kategori untuk antarmuka owner tanpa merender HTML baru.
@app.route("/api/owner/categories", methods=["GET"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_owner_categories():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    search = request.args.get("q", "").strip()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify({"success": True, "categories": fetch_category_management_rows(search)})


# Endpoint POST memvalidasi payload JSON sebelum membuat kategori melalui antarmuka dinamis.
@app.route("/api/owner/categories", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def add_owner_category():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    data = request.get_json(silent=True) or {}
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    payload, errors = validate_category_payload(data)

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if errors:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": next(iter(errors.values())), "errors": errors}), 400

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        cursor = execute_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            INSERT INTO categories (name, name_key, description)
            VALUES (?, ?, ?)
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (payload["name"], category_key(payload["name"]), payload["description"]),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category = get_category_by_id(cursor.lastrowid)
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Nama kategori sudah digunakan."}), 400

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify(
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "success": True,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "message": "Kategori berhasil ditambahkan.",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "category": row_to_dict(category),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/api/owner/categories/<int:category_id>", methods=["PUT", "PATCH"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def update_owner_category(category_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_category_by_id(category_id)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Kategori tidak ditemukan."}), 404

    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    data = request.get_json(silent=True) or {}
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    payload, errors = validate_category_payload(data, exclude_id=category_id)

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if errors:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": next(iter(errors.values())), "errors": errors}), 400

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        execute_commit(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            """
            UPDATE categories
            SET name = ?, name_key = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (payload["name"], category_key(payload["name"]), payload["description"], category_id),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        execute_commit("UPDATE menus SET category = ? WHERE category_id = ?", (payload["name"], category_id))
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Nama kategori sudah digunakan."}), 400

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify(
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "success": True,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "message": "Kategori berhasil diperbarui.",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "category": row_to_dict(get_category_by_id(category_id)),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/api/owner/categories/<int:category_id>", methods=["DELETE"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def delete_owner_category(category_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_category_by_id(category_id)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Kategori tidak ditemukan."}), 404

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    menu_count = fetch_scalar(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        get_db().execute("SELECT COUNT(*) FROM menus WHERE category_id = ?", (category_id,))
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ) or 0
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if menu_count > 0:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "success": False,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "message": f"Kategori ini masih digunakan oleh {menu_count} menu. Pindahkan menu ke kategori lain sebelum menghapus kategori.",
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        ), 400

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    execute_commit("DELETE FROM categories WHERE id = ?", (category_id,))
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify({"success": True, "message": "Kategori berhasil dihapus."})


# Endpoint ini mengirim daftar menu dalam JSON untuk kebutuhan antarmuka manajemen owner.
@app.route("/api/owner/menus", methods=["GET"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def get_owner_menus():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()

    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    page = request.args.get("page", 1, type=int)
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    per_page = request.args.get("per_page", 6, type=int)
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    search = request.args.get("q", "").strip()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    category_id = request.args.get("category_id", type=int)

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if page < 1:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        page = 1

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    offset = (page - 1) * per_page
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    where_parts = []
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    params = []

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if search:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        where_parts.append("(m.name LIKE ? OR COALESCE(c.name, m.category) LIKE ? OR m.code LIKE ?)")
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        keyword = f"%{search}%"
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        params.extend([keyword, keyword, keyword])

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if category_id:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        where_parts.append("m.category_id = ?")
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        params.append(category_id)

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    total = fetch_scalar(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            f"""
            SELECT COUNT(*)
            FROM menus m
            LEFT JOIN categories c ON c.id = m.category_id
            {where_clause}
            """,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            params,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    cursor = db.execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        SELECT
            m.id,
            m.name,
            m.category_id,
            COALESCE(c.name, m.category) AS category,
            m.code,
            m.price
        FROM menus m
        LEFT JOIN categories c ON c.id = m.category_id
        {where_clause}
        ORDER BY m.id ASC
        LIMIT ? OFFSET ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        params + [per_page, offset],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    menus = fetch_all_dict(cursor)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify(
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "menus": menus,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "page": page,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "per_page": per_page,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "total": total,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "total_pages": (total + per_page - 1) // per_page,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Endpoint ini menambahkan menu dari payload JSON setelah pemeriksaan field dan kategori.
@app.route("/api/owner/menus", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def add_owner_menu():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    data = request.get_json(silent=True) or {}

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    name = str(data.get("name", "")).strip()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_menu_category_from_value(data.get("category_id"), data.get("category"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    price_value = data.get("price")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not name or not category or price_value is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Semua field wajib diisi."}), 400

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        price = parse_menu_price(price_value)
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except (TypeError, ValueError):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Harga harus berupa angka minimal Rp 500 dan kelipatan Rp 500."}), 400

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_name = category["name"]
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        code = generate_menu_code(category_name, name)
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        insert_menu_record(
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "name": name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category": category_name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category_id": category["id"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "code": code,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "price": price,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            }
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": True, "message": "Menu berhasil ditambahkan.", "code": code})
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Kode menu sudah digunakan atau data tidak valid."}), 400


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/api/owner/menus/<int:menu_id>", methods=["PUT"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def update_owner_menu(menu_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    data = request.get_json(silent=True) or {}

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    name = str(data.get("name", "")).strip()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    category = get_menu_category_from_value(data.get("category_id"), data.get("category"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    price_value = data.get("price")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if not name or not category or price_value is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Semua field wajib diisi."}), 400

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        price = parse_menu_price(price_value)
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except (TypeError, ValueError):
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Harga harus berupa angka minimal Rp 500 dan kelipatan Rp 500."}), 400

    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category_name = category["name"]
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        update_menu_record(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            menu_id,
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "name": name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category": category_name,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "category_id": category["id"],
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "price": price,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": True, "message": "Menu berhasil diperbarui."})
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Gagal memperbarui menu."}), 400


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/owner/products")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_products():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "dashboard_placeholder.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        full_name=session.get("username", "Owner"),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        role="Owner",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        page_title="Produk Owner",
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route laporan hanya untuk owner dan menyusun metrik berdasarkan filter tanggal dari query string.
@app.route("/owner/reports")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_reports():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_financial_reports.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="reports",
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        report=build_financial_report(request.args),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route cetak memakai data laporan yang sama agar angka pada layar dan dokumen cetak konsisten.
@app.route("/owner/reports/print")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_reports_print():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_financial_report_print.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="reports",
        # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
        report=build_financial_report(request.args),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route manajemen pengguna mengambil kasir milik owner aktif dengan pagination.
@app.route("/owner/users")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_users():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    page = request.args.get("page", 1, type=int)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    per_page = 6
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    owner_id = session.get("user_id")

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if page < 1:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        page = 1

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role_where = cashier_role_filter("role")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    total = fetch_scalar(
        # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
        db.execute(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            f"SELECT COUNT(*) FROM users WHERE {role_where} AND owner_id = ?",
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            (*CASHIER_ROLE_ALIASES, owner_id),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ) or 0
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    total_pages = max(1, (total + per_page - 1) // per_page)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if total > 0 and page > total_pages:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_staff", page=total_pages))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    offset = (page - 1) * per_page
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    staff_rows = db.execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        SELECT id, full_name, email, staff_phone, staff_position, joined_date, staff_status, is_active, created_at
        FROM users
        WHERE {role_where} AND owner_id = ?
        ORDER BY id ASC
        LIMIT ? OFFSET ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (*CASHIER_ROLE_ALIASES, owner_id, per_page, offset),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchall()

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_staff.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="staff",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff_members=[format_staff_member(staff) for staff in staff_rows],
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        page=page,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        total_pages=total_pages,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        total=total,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        per_page=per_page,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/owner/staff/invite", methods=["GET", "POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_staff_invite():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("owner_staff"))


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/owner/staff")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_staff():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return owner_users()


# Route tambah kasir memvalidasi profil, membuat password awal, dan mengaitkan akun ke owner aktif.
@app.route("/owner/users/add", methods=["GET", "POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_users_add():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data = get_staff_form_data()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors, joined_date = validate_staff_form(form_data)

        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if errors:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_staff_add.html",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                owner_name=get_owner_name(),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                active_page="staff",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                form_data=form_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff_positions=STAFF_POSITIONS,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                errors=errors,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            execute_commit(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                """
                INSERT INTO users (
                    full_name, email, password_hash, role, owner_id, staff_phone, staff_position,
                    joined_date, staff_status, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                (
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["full_name"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["email"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    generate_password_hash(STAFF_DEFAULT_PASSWORD),
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    CASHIER_ROLE,
                    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
                    session.get("user_id"),
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["staff_phone"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Kasir",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    joined_date,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Aktif",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    1,
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                ),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except Exception:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_staff_add.html",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                owner_name=get_owner_name(),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                active_page="staff",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                form_data=form_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff_positions=STAFF_POSITIONS,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                errors=["Email sudah terdaftar. Gunakan email kasir yang berbeda."],
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash(f"Kasir berhasil ditambahkan. Password awal: {STAFF_DEFAULT_PASSWORD}", "success")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_staff"))

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_staff_add.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="staff",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data={},
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff_positions=STAFF_POSITIONS,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors=[],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route edit memastikan kasir yang diubah benar-benar berada di bawah owner yang sedang login.
@app.route("/owner/users/<int:staff_id>/edit", methods=["GET", "POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_users_edit(staff_id):
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    role_where = cashier_role_filter("role")
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    staff = db.execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        f"""
        SELECT id, full_name, email, staff_phone, staff_position, joined_date, staff_status, is_active, created_at
        FROM users
        WHERE id = ? AND {role_where} AND owner_id = ?
        """,
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        (staff_id, *CASHIER_ROLE_ALIASES, session.get("user_id")),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchone()

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if staff is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Data kasir tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_staff"))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    staff_data = format_staff_member(staff)

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.method == "POST":
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data = get_staff_form_data()
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        errors, joined_date = validate_staff_form(form_data)

        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if errors:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_staff_edit.html",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                owner_name=get_owner_name(),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                active_page="staff",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff=staff_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                form_data=form_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff_positions=STAFF_POSITIONS,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff_statuses=STAFF_STATUSES,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                errors=errors,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
        try:
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            execute_commit(
                # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
                f"""
                UPDATE users
                SET full_name = ?, email = ?, staff_phone = ?, staff_position = ?,
                    joined_date = ?, staff_status = ?, is_active = ?
                WHERE id = ? AND {role_where} AND owner_id = ?
                """,
                # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
                (
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["full_name"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["email"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["staff_phone"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    "Kasir",
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    joined_date,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    form_data["staff_status"],
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    1 if form_data["is_active"] else 0,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    staff_id,
                    # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                    *CASHIER_ROLE_ALIASES,
                    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
                    session.get("user_id"),
                # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
                ),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )
        # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
        except Exception:
            # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
            return render_template(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "owner_staff_edit.html",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                owner_name=get_owner_name(),
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                active_page="staff",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff=staff_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                form_data=form_data,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff_positions=STAFF_POSITIONS,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                staff_statuses=STAFF_STATUSES,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                errors=["Email sudah digunakan akun lain. Gunakan email kasir yang berbeda."],
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            )

        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Data kasir berhasil diperbarui.", "success")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("owner_staff"))

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "owner_staff_edit.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        owner_name=get_owner_name(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        active_page="staff",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff=staff_data,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        form_data={},
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff_positions=STAFF_POSITIONS,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff_statuses=STAFF_STATUSES,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        errors=[],
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/owner/<path:unused_path>")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@owner_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def owner_fallback(unused_path):
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("owner_menu"))


# Halaman POS hanya dapat dibuka kasir dan memuat menu aktif beserta stok serta filter kategorinya.
@app.route("/pos")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def pos():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_menu_table()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_pos_tables()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    db = get_db()
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    products = db.execute(
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        """
        SELECT
            m.id,
            m.name,
            m.description,
            m.price,
            m.image,
            m.stock,
            COALESCE(c.name, m.category) AS category,
            m.category_id,
            m.code,
            m.is_active
        FROM menus m
        LEFT JOIN categories c ON c.id = m.category_id
        WHERE m.is_active = 1
        ORDER BY m.id DESC
        """
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    ).fetchall()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    products = [dict(product) for product in products]
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    active_categories = []
    # Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
    for product in products:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        category = str(product.get("category") or "").strip()
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        product["category"] = category
        # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
        if category:
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            active_categories.append(category)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "pos.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        shift=get_current_shift(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff_name=session.get("full_name", "Kasir"),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        menu_categories=get_pos_category_filters(active_categories),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        products=products,
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Halaman pembayaran membaca keranjang yang disimpan browser dan menyediakan pilihan tunai atau QRIS.
@app.route("/pos/payment")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def pos_payment():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    init_pos_tables()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "pos_payment.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        shift=get_current_shift(),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        staff_name=session.get("full_name", "Kasir"),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Endpoint checkout menerima JSON pembayaran, membuat transaksi, lalu mengembalikan URL halaman sukses.
@app.route("/api/pos/checkout", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def pos_checkout():
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    data = request.get_json(silent=True) or {}  # Membaca payload dengan aman agar JSON kosong tidak menyebabkan error.
    # Kesalahan validasi dikirim sebagai respons 400, sedangkan gangguan tak terduga dicatat sebagai error server.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        transaction = create_pos_transaction(data)
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        payment_method = "QRIS" if str(data.get("payment_method") or "").strip().lower() == "qris" else "Cash"
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        received_amount = (
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            transaction["total_amount"]
            # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
            if payment_method == "QRIS"
            # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
            else parse_pos_amount(data.get("received_amount"), "Nominal diterima")
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        change_amount = max(received_amount - transaction["total_amount"], 0)
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        remember_payment_details(
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            transaction["order_code"],
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            payment_method,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            transaction["total_amount"],
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            received_amount,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            change_amount,
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        )
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except ValueError as exc:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": str(exc)}), 400
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except Exception:
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        app.logger.exception("POS checkout failed.")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Gagal menyimpan transaksi POS. Silakan coba lagi."}), 500

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify(
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "success": True,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "message": f"Transaksi {transaction['order_code']} berhasil disimpan.",
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            "transaction": {
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                **transaction,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "subtotal_display": format_currency(transaction["subtotal_amount"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "discount_display": format_currency(transaction["discount_amount"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "total_display": format_currency(transaction["total_amount"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "received_amount": received_amount,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "received_display": format_currency(received_amount),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "change_amount": change_amount,
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "change_display": format_currency(change_amount),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "success_url": url_for("payment_success", order_code=transaction["order_code"]),
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "receipt_url": url_for("pos_receipt", order_code=transaction["order_code"]),
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            },
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Endpoint QRIS membuat payload pembayaran dari total keranjang tanpa langsung menyimpan transaksi.
@app.route("/api/pos/qris", methods=["POST"])
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def pos_qris_payload():
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    data = request.get_json(silent=True) or {}
    # Blok try menjaga agar kegagalan operasi dapat ditangani secara terkontrol.
    try:
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        total_amount = parse_pos_amount(data.get("total_amount"), "Total pembayaran")
    # Blok except menangani kesalahan supaya alur aplikasi tidak berhenti tanpa respons.
    except ValueError as exc:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": str(exc)}), 400

    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if total_amount <= 0:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return jsonify({"success": False, "message": "Total pembayaran harus lebih dari Rp 0."}), 400

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    timestamp = datetime.now().replace(microsecond=0).isoformat(timespec="minutes")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    order_code = normalize_order_code(data.get("order_code")) or generate_invoice_code()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    payload = build_qris_payload(order_code, total_amount, timestamp)

    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return jsonify(
        # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
        {
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "success": True,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "order_code": order_code,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "timestamp": timestamp,
            # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
            "payload": payload,
            # Memulai susunan nilai atau pemanggilan yang dilanjutkan pada baris berikutnya.
            "qr_url": url_for(
                # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
                "pos_qris_code",
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                order_code=order_code,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                total=total_amount,
                # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
                timestamp=timestamp,
            # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
            ),
        # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
        }
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route ini mengubah payload QRIS pada URL menjadi gambar PNG yang dapat dipindai pelanggan.
@app.route("/pos/qris-code/<order_code>.png")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def pos_qris_code(order_code):
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if qrcode is None:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return "Paket qrcode belum terpasang. Jalankan pip install -r requirements.txt.", 503

    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    total_amount = parse_pos_amount(request.args.get("total"), "Total pembayaran")
    # Membaca data request yang dikirim browser untuk diproses dan divalidasi oleh server.
    timestamp = request.args.get("timestamp", datetime.now().replace(microsecond=0).isoformat(timespec="minutes"))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    order_code = normalize_order_code(order_code) or generate_invoice_code()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    payload = build_qris_payload(order_code, total_amount, timestamp)

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    qr = qrcode.QRCode(version=None, box_size=12, border=2)
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    qr.add_data(payload)
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    qr.make(fit=True)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    image = qr.make_image(fill_color="#3A1E1A", back_color="white")
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    buffer = BytesIO()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    image.save(buffer, format="PNG")
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    buffer.seek(0)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return send_file(buffer, mimetype="image/png", download_name=f"{order_code}.png")


# Halaman sukses hanya menampilkan transaksi yang ditemukan berdasarkan kode pesanan.
@app.route("/pos/payment/success/<order_code>")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def payment_success(order_code):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    order_code = normalize_order_code(order_code)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction = fetch_transaction_detail(order_code)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if transaction is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Transaksi tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("pos"))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    payment = get_payment_details(order_code, transaction)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "payment_success.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        transaction=transaction,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        payment=payment,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        total_display=format_currency(transaction.get("total_amount") or 0),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        received_display=format_currency(payment["received_amount"]),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        change_display=format_currency(payment["change_amount"]),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Route struk menyiapkan detail transaksi untuk tampilan dan proses cetak bukti pembayaran.
@app.route("/pos/receipt/<order_code>")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@staff_required
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def pos_receipt(order_code):
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    order_code = normalize_order_code(order_code)
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    transaction = fetch_transaction_detail(order_code)
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if transaction is None:
        # Menyimpan pesan flash agar hasil proses dapat ditampilkan pada halaman berikutnya.
        flash("Transaksi tidak ditemukan.", "error")
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return redirect(url_for("pos"))

    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    payment = get_payment_details(order_code, transaction)
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return render_template(
        # Menambahkan nilai ini ke susunan argumen atau data yang sedang dibentuk.
        "receipt.html",
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        transaction=transaction,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        payment=payment,
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        received_display=format_currency(payment["received_amount"]),
        # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
        change_display=format_currency(payment["change_amount"]),
    # Menutup susunan data atau pemanggilan yang dimulai pada baris sebelumnya.
    )


# Logout menghapus seluruh session agar identitas pengguna tidak tersisa di browser.
@app.route("/logout")
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def logout():
    # Memperbarui session agar identitas atau keadaan pengguna tersedia pada request berikutnya.
    session.clear()
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return redirect(url_for("login"))


# Menjalankan seluruh inisialisasi skema yang dibutuhkan oleh autentikasi, menu, kategori, dan POS.
def initialize_database():
    # Context manager ini mengelola resource dan menutupnya kembali secara aman.
    with app.app_context():
        # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
        init_db()
        init_menu_table()
        init_pos_tables()


# Flag global mencegah migrasi skema yang sama dijalankan berulang pada setiap request.
def ensure_schema_ready():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    global SCHEMA_READY
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if SCHEMA_READY:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return

    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    initialize_database()
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    SCHEMA_READY = True


# Flask memeriksa kesiapan skema sebelum route diproses agar tabel yang diperlukan selalu tersedia.
@app.before_request
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def prepare_database_for_request():
    # Kondisi ini menentukan apakah blok berikut perlu dijalankan berdasarkan keadaan saat ini.
    if request.endpoint == "static" or request.path in {"/favicon.ico", "/favicon.png"}:
        # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
        return
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_schema_ready()


# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/favicon.ico")
# Decorator ini menerapkan perilaku tambahan pada fungsi tepat di bawahnya.
@app.route("/favicon.png")
# Mendefinisikan fungsi beserta parameter yang menjadi data masuk proses ini.
def favicon():
    # Mengembalikan hasil ini kepada pemanggil dan mengakhiri fungsi.
    return "", 204


# Server development hanya dijalankan ketika file ini dieksekusi langsung, bukan saat diimpor.
if __name__ == "__main__":
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    ensure_schema_ready()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    app.run(debug=True)
