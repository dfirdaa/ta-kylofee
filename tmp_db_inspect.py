# Script diagnostik ini membaca struktur database lokal tanpa mengubah isi tabel.
import sqlite3
import os
path = os.path.join(os.path.dirname(__file__), 'database.db')  # Menentukan database yang berada di folder project.
conn = sqlite3.connect(path)  # Membuka koneksi SQLite untuk pemeriksaan tabel dan data contoh.
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print('db exists', os.path.exists(path))
# Perulangan memeriksa keberadaan tabel utama autentikasi dan transaksi POS.
for tbl in ['users', 'pos_transactions', 'pos_transaction_items']:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
    row = cur.fetchone()
    print(tbl, 'exists', bool(row))
print('--- users columns ---')
# Query PRAGMA berikut menampilkan kolom tiap tabel agar skema mudah diperiksa saat belajar atau debugging.
for r in cur.execute('PRAGMA table_info(users)').fetchall():
    print(r)
print('--- pos_transactions columns ---')
for r in cur.execute('PRAGMA table_info(pos_transactions)').fetchall():
    print(r)
print('--- pos_transaction_items columns ---')
for r in cur.execute('PRAGMA table_info(pos_transaction_items)').fetchall():
    print(r)
print('count users', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0])
print('count pos_transactions', cur.execute('SELECT COUNT(*) FROM pos_transactions').fetchone()[0])
print('sample firdakasir', [dict(row) for row in cur.execute('SELECT id, full_name, email, role, owner_id, is_active, staff_status, joined_date FROM users WHERE email=?', ('firdakasir@gmail.com',)).fetchall()])
conn.close()  # Menutup koneksi setelah seluruh pemeriksaan selesai.
