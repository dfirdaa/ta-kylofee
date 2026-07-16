"""Remove confirmed legacy menu duplicates and preserve transaction references."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import fetch_all, transaction
from app.menu.services import normalize_menu_name
from config import Config

DUPLICATE_GROUPS = {
    30005: (150001, 150002, 150003, 150004, 150005, 150006, 150007, 150008),
    180001: (180002, 180003),
    90002: (210001,),
    180004: (180005, 180006),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Terapkan pembersihan yang sudah dikonfirmasi.")
    args = parser.parse_args()

    app = create_app(Config)
    app.config["AUTO_MIGRATE"] = False
    all_ids = tuple(menu_id for keeper, duplicates in DUPLICATE_GROUPS.items() for menu_id in (keeper, *duplicates))

    with app.app_context():
        placeholders = ", ".join(["%s"] * len(all_ids))
        rows = fetch_all(
            f"SELECT id, code, name FROM menus WHERE id IN ({placeholders}) ORDER BY id",
            all_ids,
        )
        by_id = {int(row["id"]): row for row in rows}

        for keeper_id, duplicate_ids in DUPLICATE_GROUPS.items():
            keeper = by_id.get(keeper_id)
            if not keeper:
                raise RuntimeError(f"Menu utama ID {keeper_id} tidak ditemukan; pembersihan dibatalkan.")
            keeper_key = normalize_menu_name(keeper["name"])
            for duplicate_id in duplicate_ids:
                duplicate = by_id.get(duplicate_id)
                if duplicate and normalize_menu_name(duplicate["name"]) != keeper_key:
                    raise RuntimeError(
                        f"ID {duplicate_id} bukan lagi duplikat ID {keeper_id}; pembersihan dibatalkan."
                    )

        existing_duplicates = [
            duplicate_id
            for duplicate_ids in DUPLICATE_GROUPS.values()
            for duplicate_id in duplicate_ids
            if duplicate_id in by_id
        ]
        if not existing_duplicates:
            print("Tidak ada duplicate ID terkonfirmasi yang tersisa.")
            return 0

        print("Menu yang akan dipertahankan:")
        for keeper_id in DUPLICATE_GROUPS:
            keeper = by_id[keeper_id]
            print(f"- ID {keeper_id}, {keeper['code']}, {keeper['name']}")
        print(f"Duplicate ID yang akan dihapus: {', '.join(map(str, existing_duplicates))}")
        if not args.apply:
            print("DRY_RUN: tambahkan --apply untuk menjalankan transaksi.")
            return 0

        moved_references = 0
        deleted_menus = 0
        with transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT id FROM menus WHERE id IN ({placeholders}) FOR UPDATE",
                all_ids,
            )
            cursor.fetchall()
            for keeper_id, duplicate_ids in DUPLICATE_GROUPS.items():
                present_ids = tuple(menu_id for menu_id in duplicate_ids if menu_id in by_id)
                if not present_ids:
                    continue
                group_placeholders = ", ".join(["%s"] * len(present_ids))
                cursor.execute(
                    f"UPDATE pos_transaction_items SET menu_id = %s WHERE menu_id IN ({group_placeholders})",
                    (keeper_id, *present_ids),
                )
                moved_references += int(cursor.rowcount or 0)
                cursor.execute(
                    f"DELETE FROM menus WHERE id IN ({group_placeholders})",
                    present_ids,
                )
                deleted_menus += int(cursor.rowcount or 0)

        print(f"REFERENSI_TRANSAKSI_DIPINDAH={moved_references}")
        print(f"MENU_DUPLIKAT_DIHAPUS={deleted_menus}")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
s