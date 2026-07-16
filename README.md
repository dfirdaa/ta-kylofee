# Kyloffee POS

Aplikasi Flask modular untuk autentikasi Owner/Kasir, manajemen kategori dan menu, POS, kode undangan kasir, serta laporan keuangan bersama. Seluruh data aplikasi menggunakan satu database TiDB/MySQL; tidak ada fallback ke database lokal lain.

## Struktur utama

```text
.
|-- index.py               # entry point WSGI/Vercel
|-- run.py                 # launcher lokal
|-- config.py              # konfigurasi environment
|-- app/
|   |-- __init__.py        # application factory
|   |-- database.py        # koneksi dan transaksi TiDB
|   |-- schema.py          # pemeriksaan/migrasi skema idempoten
|   |-- routing.py         # inventaris dan deteksi duplicate route
|   |-- auth/              # login, registrasi, logout
|   |-- owner/             # shell/dashboard owner
|   |-- cashier/           # akun kasir dan kode undangan
|   |-- menu/              # kategori dan menu
|   |-- pos/               # transaksi POS, QRIS, struk
|   |-- reports/           # laporan global semua owner
|   `-- utils/             # decorator, validator, formatter, role, email
|-- migrations/
|   `-- 001_tidb_centralization.sql
|-- templates/
`-- static/
```

## Environment

Salin `.env.example` menjadi `.env`, lalu isi salah satu bentuk koneksi berikut:

```env
DATABASE_URL=mysql://user:password@host:4000/database?ssl_ca=certs/tidb-ca.pem
```

atau variabel terpisah:

```env
TIDB_HOST=
TIDB_PORT=4000
TIDB_USER=
TIDB_PASSWORD=
TIDB_DATABASE=
TIDB_SSL_CA=certs/tidb-ca.pem
TIDB_SSL_VERIFY_CERT=1
AUTO_MIGRATE=0
```

Alias lama `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, dan `DB_SSL_CA` masih dibaca untuk mempermudah deployment lama, tetapi semuanya tetap diarahkan ke koneksi TiDB yang sama.

Variabel aplikasi lainnya:

```env
SECRET_KEY=
SESSION_COOKIE_SECURE=0
STAFF_DEFAULT_PASSWORD=kyloffee123
RESEND_API_KEY=
RESEND_FROM_EMAIL=
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_FOLDER=kyloffee/menu
```

## Menjalankan

```bash
python -m venv .venv
pip install -r requirements.txt
python run.py
```

Audit route dan jalankan pengujian:

```bash
flask --app index.py routes
flask --app index.py audit-routes
python -m unittest discover -s tests -v
```

Deployment Vercel menggunakan auto-detection Flask melalui top-level `app` di
`index.py`; konfigurasi legacy `builds` tidak diperlukan. Pastikan semua environment
variable ditambahkan untuk Production (dan Preview bila dipakai), lalu uji entry
point dan migrasi dari mesin tepercaya sebelum deploy:

```powershell
python -c "from index import app; print('Vercel entrypoint berhasil:', app.name)"
$env:AUTO_MIGRATE = "0"
flask --app index.py migrate-db
python migrations/004_category_uniqueness.py
python migrations/004_category_uniqueness.py --apply
vercel --prod --force
```

Di Vercel, `AUTO_MIGRATE` default-nya nonaktif agar beberapa cold start tidak
menjalankan DDL bersamaan. Jalankan `flask --app index.py migrate-db` sekali setelah
backup database. Audit kategori dengan migrasi `004` tanpa flag, periksa keeper yang
dipilih, lalu jalankan kembali dengan `--apply` untuk memindahkan relasi menu,
membersihkan kategori duplikat, dan membuat unique index. Biarkan `AUTO_MIGRATE=0`
di Production. Jika migrasi otomatis
sengaja diaktifkan dan gagal, aplikasi mencatat traceback, melanjutkan request, dan
mencoba lagi setelah `SCHEMA_RETRY_SECONDS`. Status konfigurasi aman dapat diperiksa
melalui `/_health`. SQL referensi tersedia di `migrations/001_tidb_centralization.sql`.

## Perubahan aturan data

- Email harus diketik lowercase; backend menolak input yang mengandung huruf kapital dan tidak mengubahnya diam-diam.
- Password minimal enam karakter dan selalu disimpan sebagai hash Werkzeug.
- Semua owner membaca laporan, kasir, menu, kategori, transaksi, dan undangan yang sama. `owner_id` dipertahankan hanya sebagai audit.
- Daftar kasir menggunakan filter role global, bukan `owner_id`.
- Registrasi kasir memerlukan kode undangan. Kode dikunci dengan `SELECT ... FOR UPDATE`, lalu akun dibuat dan kode ditandai digunakan dalam satu transaksi.
- Kode menu dibuat dari sequence per-prefix dengan row locking, retry terbatas, dan unique index database.
- POS menggunakan `menu_id` sebagai foreign key bisnis transaksi dan menyimpan `menu_code` sebagai snapshot untuk struk/pelacakan.

## Query laporan: sebelum dan sesudah

Sebelumnya query menambahkan filter `t.owner_id = owner_id` (atau owner kasir), sehingga Owner B tidak melihat transaksi Owner A. Sekarang laporan hanya memfilter periode dan status selesai:

```sql
WHERE t.transaction_date BETWEEN %s AND %s
  AND LOWER(t.status) IN ('selesai', 'paid', 'completed', 'complete')
```

## Query kasir: sebelum dan sesudah

Sebelumnya daftar menggunakan `WHERE role IN (...) AND owner_id = %s`. Sekarang identitas utama adalah `users.id` dan seluruh kasir dibaca berdasarkan role:

```sql
WHERE LOWER(u.role) IN (%s, %s, %s)
```

Kode undangan ditampilkan melalui relasi `cashier_invitations.used_by_cashier_id` bila tersedia.
