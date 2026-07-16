"""Audit, clean up, and enforce normalized category-name uniqueness."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import commit
from app.schema import (
    audit_category_name_duplicates,
    column_exists,
    migrate_category_name_uniqueness,
)
from config import Config


def print_duplicate_report(duplicates):
    if not duplicates:
        print("Tidak ada nama kategori duplikat.")
        return

    for group in duplicates:
        categories = sorted(
            group["categories"],
            key=lambda category: (-int(category.get("menu_count") or 0), int(category["id"])),
        )
        keeper = categories[0]
        print(f"\nNormalized name: {group['normalized_name']}")
        for category in categories:
            marker = "KEEPER" if int(category["id"]) == int(keeper["id"]) else "DUPLICATE"
            print(
                f"- {marker}: ID {category['id']}, {category.get('name') or '-'}, "
                f"{int(category.get('menu_count') or 0)} menu"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Pindahkan relasi menu, hapus kategori duplikat, backfill, dan buat unique index.",
    )
    args = parser.parse_args()

    app = create_app(Config)
    app.config["AUTO_MIGRATE"] = False
    with app.app_context():
        if not column_exists("categories", "normalized_name"):
            if not args.apply:
                print("Kolom normalized_name belum ada; jalankan dengan --apply setelah backup.")
            else:
                commit("ALTER TABLE categories ADD COLUMN normalized_name VARCHAR(255) NULL")

        duplicates = audit_category_name_duplicates()
        print_duplicate_report(duplicates)
        if not args.apply:
            if duplicates:
                print(
                    "\nDRY_RUN: kategori dengan menu terbanyak akan dipertahankan; "
                    "jika sama, ID terkecil menjadi keeper."
                )
            else:
                print("\nAUDIT_OK: jalankan kembali dengan --apply untuk backfill dan unique index.")
            return 0

        result = migrate_category_name_uniqueness(cleanup_duplicates=True)
        print(f"\nBACKFILL={result['backfill']}")
        print(f"UNIQUE_INDEX={result['unique_index']}")
        print(f"REFERENSI_MENU_DIPINDAH={result['moved_menus']}")
        print(f"KATEGORI_DUPLIKAT_DIHAPUS={result['deleted_categories']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
