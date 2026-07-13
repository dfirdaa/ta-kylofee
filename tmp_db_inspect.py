# Script diagnostik ini membaca struktur database lokal tanpa mengubah isi tabel.
import sqlite3
# Mengimpor komponen yang dibutuhkan oleh proses pada bagian ini.
import os
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
path = os.path.join(os.path.dirname(__file__), 'database.db')  # Menentukan database yang berada di folder project.
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
conn = sqlite3.connect(path)  # Membuka koneksi SQLite untuk pemeriksaan tabel dan data contoh.
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
conn.row_factory = sqlite3.Row
# Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
cur = conn.cursor()
# Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
print('db exists', os.path.exists(path))
# Perulangan memeriksa keberadaan tabel utama autentikasi dan transaksi POS.
for tbl in ['users', 'pos_transactions', 'pos_transaction_items']:
    # Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
    # Menyimpan nilai pada variabel agar dapat digunakan oleh langkah berikutnya.
    row = cur.fetchone()
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    print(tbl, 'exists', bool(row))
# Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
print('--- users columns ---')
# Query PRAGMA berikut menampilkan kolom tiap tabel agar skema mudah diperiksa saat belajar atau debugging.
for r in cur.execute('PRAGMA table_info(users)').fetchall():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    print(r)
# Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
print('--- pos_transactions columns ---')
# Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
for r in cur.execute('PRAGMA table_info(pos_transactions)').fetchall():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    print(r)
# Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
print('--- pos_transaction_items columns ---')
# Perulangan ini memproses setiap elemen agar mendapat perlakuan yang sama.
for r in cur.execute('PRAGMA table_info(pos_transaction_items)').fetchall():
    # Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
    print(r)
# Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
print('count users', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0])
# Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
print('count pos_transactions', cur.execute('SELECT COUNT(*) FROM pos_transactions').fetchone()[0])
# Menjalankan query database dengan parameter terpisah agar data dapat diproses secara aman.
print('sample firdakasir', [dict(row) for row in cur.execute('SELECT id, full_name, email, role, owner_id, is_active, staff_status, joined_date FROM users WHERE email=?', ('firdakasir@gmail.com',)).fetchall()])
# Menjalankan langkah ini sebagai bagian dari alur fungsi atau proses yang sedang berlangsung.
conn.close()  # Menutup koneksi setelah seluruh pemeriksaan selesai.
