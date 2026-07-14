-- Jalankan setelah membuat backup. Aplikasi juga melakukan pemeriksaan idempoten
-- terhadap kolom/index ini saat startup.

ALTER TABLE users ADD UNIQUE INDEX uq_users_email (email);
ALTER TABLE menus ADD UNIQUE INDEX uq_menus_code (code);
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

