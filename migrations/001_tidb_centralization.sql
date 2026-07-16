-- Jalankan setelah membuat backup. Aplikasi juga melakukan pemeriksaan idempoten
-- terhadap kolom/index ini saat startup.

ALTER TABLE users ADD UNIQUE INDEX uq_users_email (email);
ALTER TABLE menus ADD UNIQUE INDEX uq_menus_code (code);
ALTER TABLE menus ADD COLUMN normalized_name VARCHAR(255) NULL;
-- Skema legacy memakai menu_name NOT NULL. Data sudah disalin ke kolom name oleh
-- migrasi aplikasi, jadi kolom lama harus nullable agar insert canonical tidak gagal.
ALTER TABLE menus MODIFY COLUMN menu_name VARCHAR(255) NULL;
ALTER TABLE cashier_invitations ADD UNIQUE INDEX uq_cashier_invitations_code (invite_code);
ALTER TABLE pos_transactions ADD UNIQUE INDEX uq_pos_transactions_order_code (order_code);
ALTER TABLE pos_transaction_items ADD COLUMN menu_code VARCHAR(100) NULL;

CREATE TABLE IF NOT EXISTS menu_code_sequences (
    prefix VARCHAR(16) PRIMARY KEY,
    next_value BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

UPDATE pos_transaction_items i
LEFT JOIN menus m ON m.id = i.menu_id
SET i.menu_code = m.code
WHERE (i.menu_code IS NULL OR TRIM(i.menu_code) = '') AND m.id IS NOT NULL;

-- Audit awal (case-insensitive + trim). Audit Python wajib tetap dijalankan karena
-- query ini tidak mengabaikan seluruh variasi jumlah spasi di tengah nama.
SELECT
    LOWER(TRIM(name)) AS normalized_name,
    COUNT(*) AS total,
    GROUP_CONCAT(id ORDER BY id) AS menu_ids,
    GROUP_CONCAT(code ORDER BY id) AS menu_codes,
    GROUP_CONCAT(name ORDER BY id) AS menu_names
FROM menus
WHERE name IS NOT NULL AND TRIM(name) <> ''
GROUP BY LOWER(TRIM(name))
HAVING COUNT(*) > 1;

-- Jangan menambahkan uq_menus_normalized_name dari SQL ini. Jalankan:
--     python migrations/002_menu_name_uniqueness.py
-- Script tersebut melakukan audit Python, backfill transaksional, lalu baru
-- membuat unique index bila tidak ada duplikat.
