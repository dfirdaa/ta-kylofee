"""Audit and safely apply global menu-name uniqueness for TiDB/MySQL."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import commit, fetch_all
from app.schema import audit_menu_name_duplicates, migrate_menu_name_uniqueness, table_columns
from config import Config


def recommendation(name, position):
    display_name = " ".join(str(name or "Menu").strip().split()).title()
    suffixes = ("", "Large", "Special", "Hot", "Ice")
    suffix = suffixes[position] if position < len(suffixes) else str(position + 1)
    return f"{display_name} {suffix}".strip()


def print_duplicate_report(duplicates):
    if not duplicates:
        print("Tidak ada nama menu duplikat.")
        return
    for group in duplicates:
        print(f"\nNormalized name: {group['normalized_name']}")
        for position, menu in enumerate(group["menus"]):
            print(f"- ID {menu['id']}, {menu.get('code') or '-'}, {menu.get('name') or '-'}")
            print(f"  Rekomendasi: {recommendation(menu.get('name'), position)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Backfill normalized_name dan buat unique index hanya jika audit bersih.",
    )
    args = parser.parse_args()

    app = create_app(Config)
    app.config["AUTO_MIGRATE"] = False
    with app.app_context():
        if "normalized_name" not in table_columns("menus"):
            if not args.apply:
                print("Kolom normalized_name belum ada; jalankan dengan --apply setelah backup.")
            else:
                commit("ALTER TABLE menus ADD COLUMN normalized_name VARCHAR(255) NULL")

        rows = fetch_all("SELECT id, code, name FROM menus ORDER BY id ASC")
        duplicates = audit_menu_name_duplicates(rows)
        print_duplicate_report(duplicates)
        if duplicates:
            print("\nMIGRATION_BLOCKED: data tidak diubah dan unique index tidak dibuat.")
            return 2
        if not args.apply:
            print("\nAUDIT_OK: jalankan kembali dengan --apply untuk backfill dan unique index.")
            return 0

        result = migrate_menu_name_uniqueness()
        print(f"\nBACKFILL={result['backfill']}")
        print(f"UNIQUE_INDEX={result['unique_index']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
