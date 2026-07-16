import inspect
import subprocess
import sys
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pymysql

from app import create_app
from app.auth import services as auth_services
from app.auth import routes as auth_routes
from app.cashier import routes as cashier_routes
from app.cashier import services as cashier_services
from app.menu import routes as menu_routes
from app.menu import services as menu_services
from app.pos import routes as pos_routes
from app.pos import services as pos_services
from app.reports import routes as report_routes
from app.reports import services as report_services
from app.routing import find_duplicate_routes, route_inventory
from app.utils.validators import validate_email, validate_password
from werkzeug.security import check_password_hash


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    AUTO_MIGRATE = False
    TIDB_HOST = "test"
    TIDB_PORT = 4000
    TIDB_USER = "test"
    TIDB_PASSWORD = "test"
    TIDB_DATABASE = "test"
    TIDB_SSL_CA = ""
    TIDB_SSL_VERIFY_CERT = False
    UPLOAD_FOLDER = "static/uploads/menu"
    STAFF_DEFAULT_PASSWORD = "123456"
    RESEND_API_KEY = ""
    CLOUDINARY_CLOUD_NAME = ""
    CLOUDINARY_API_KEY = ""
    CLOUDINARY_API_SECRET = ""


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    @staticmethod
    def sample_report():
        return {
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "period": "1 Jul 2026 - 31 Jul 2026",
            "dashboard_metrics": [
                {"label": "Total Pendapatan", "value": "Rp20.000", "trend": "+10%", "tone": "positive"}
            ],
            "hourly_sales": [
                {"hour": "08:00", "amount": "Rp20.000", "height": 100, "is_peak": True, "label_visible": True}
            ],
            "has_data": True,
            "recent_transactions": [
                {"id": "POS-1", "time": "08:00", "items": 1, "customer": "Walk-in Customer", "staff": "Kasir", "total": "Rp20.000", "status": "Selesai"}
            ],
            "monthly_summary": [
                {"month": "Juli 2026", "income": "Rp20.000", "profit": "Rp20.000", "is_current": True}
            ],
            "daily_income_rows": [
                {"date": "14 Jul 2026", "transactions": 1, "income": "Rp20.000"}
            ],
            "printed_at": "14 Jul 2026 12:00 WIB",
            "print_summary": [],
            "print_transactions": [],
            "daily_details": [],
            "daily_totals": {"transactions": "1", "income": "Rp20.000", "profit": "Rp20.000"},
            "net_profit": "Rp20.000",
            "net_profit_trend": "+10%",
        }

    def test_lowercase_email_is_accepted(self):
        value, error = validate_email("  nama@gmail.com  ")
        self.assertEqual(value, "nama@gmail.com")
        self.assertIsNone(error)

    def test_uppercase_email_is_rejected_without_silent_conversion(self):
        value, error = validate_email("Nama@gmail.com")
        self.assertEqual(value, "Nama@gmail.com")
        self.assertIn("huruf kecil", error)

    def test_password_length(self):
        self.assertIsNotNone(validate_password("12345"))
        self.assertIsNone(validate_password("123456"))

    def test_registered_password_is_hashed(self):
        captured = {}

        class Cursor:
            lastrowid = 11

            def execute(self, query, params):
                captured["query"] = query
                captured["params"] = params

        class Connection:
            def cursor(self):
                return Cursor()

        @contextmanager
        def fake_transaction():
            yield Connection()

        form = {
            "full_name": "Owner Baru",
            "email": "owner@gmail.com",
            "password": "rahasia",
            "password_confirm": "rahasia",
        }
        with patch.object(auth_services, "find_user_by_email", return_value=None), patch.object(
            auth_services, "transaction", fake_transaction
        ):
            user, _form_data, errors = auth_services.register_user("owner", form)
        self.assertEqual(errors, [])
        self.assertEqual(user["id"], 11)
        stored_hash = captured["params"][2]
        self.assertNotEqual(stored_hash, "rahasia")
        self.assertTrue(check_password_hash(stored_hash, "rahasia"))

    def test_invitation_is_locked_and_consumed_in_registration_transaction(self):
        queries = []

        class Cursor:
            lastrowid = 17
            rowcount = 1

            def execute(self, query, params):
                queries.append(" ".join(query.split()))

            def fetchone(self):
                return {
                    "id": 4,
                    "owner_id": 2,
                    "status": "Aktif",
                    "expires_at": datetime.now() + timedelta(days=1),
                }

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        @contextmanager
        def fake_transaction():
            yield Connection()

        form = {
            "full_name": "Kasir Baru",
            "email": "kasir@gmail.com",
            "password": "123456",
            "password_confirm": "123456",
            "invite_code": "KASIR-ABC123",
        }
        with patch.object(auth_services, "find_user_by_email", return_value=None), patch.object(
            auth_services, "transaction", fake_transaction
        ):
            user, _form_data, errors = auth_services.register_user("staff", form)
        self.assertEqual(errors, [])
        self.assertEqual(user["owner_id"], 2)
        self.assertTrue(any("FOR UPDATE" in query for query in queries))
        self.assertTrue(any("SET status = 'Digunakan'" in query for query in queries))

    def test_public_url_contract_is_preserved(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        expected = {
            "/login",
            "/register/owner",
            "/register/kasir",
            "/owner/menu",
            "/owner/categories",
            "/owner/reports",
            "/owner/staff",
            "/api/owner/menus",
            "/pos",
            "/api/pos/menus",
            "/api/pos/checkout",
        }
        self.assertTrue(expected.issubset(rules))

    def test_create_app_blueprints_and_routes_are_unique(self):
        self.assertEqual(find_duplicate_routes(self.app), {})
        expected_blueprints = {"auth", "owner", "cashier", "menu", "reports", "pos"}
        self.assertEqual(set(self.app.blueprints), expected_blueprints)
        self.assertEqual(len(self.app.teardown_appcontext_funcs), 1)
        inventory = route_inventory(self.app)
        self.assertTrue(any(item["endpoint"] == "reports.owner_reports" for item in inventory))
        database_source = inspect.getsource(__import__("app.database", fromlist=["get_db"]))
        self.assertNotIn("sqlite3", database_source)
        self.assertNotIn("database.db", database_source)

    def test_public_auth_pages_open_without_database_access(self):
        for path in ("/login", "/register/owner", "/register/kasir"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_vercel_loader_can_import_index_app(self):
        project_root = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
        loader_code = """
from index import app
assert app.__class__.__name__ == "Flask"
print("VERCEL_LOADER_OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", loader_code],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VERCEL_LOADER_OK", result.stdout)

    def test_auto_migrate_failure_is_logged_but_does_not_block_public_route(self):
        class AutoMigrateConfig(TestConfig):
            AUTO_MIGRATE = True
            SCHEMA_RETRY_SECONDS = 60

        app = create_app(AutoMigrateConfig)
        with patch("app.ensure_schema", side_effect=RuntimeError("simulated migration failure")):
            with self.assertLogs(app.logger, level="ERROR") as logs:
                response = app.test_client().get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(app.extensions["tidb_schema_last_error"], "RuntimeError")
        self.assertTrue(any("AUTO_MIGRATE gagal" in message for message in logs.output))

    def test_register_staff_is_redirect_alias(self):
        response = self.client.get("/register/staff")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/register/kasir"))

    def test_role_redirect_destinations(self):
        with self.app.test_request_context("/"):
            from flask import session

            session["role"] = "owner"
            self.assertTrue(auth_services.redirect_for_role().location.endswith("/owner/menu"))
            session["role"] = "staff"
            self.assertTrue(auth_services.redirect_for_role().location.endswith("/pos"))

    def test_login_routes_owner_and_cashier_to_their_existing_urls(self):
        owner = {"id": 1, "full_name": "Owner", "email": "owner@gmail.com", "role": "owner", "owner_id": None}
        with patch.object(auth_routes, "authenticate_user", return_value=(owner, owner["email"], [])):
            response = self.client.post(
                "/login", data={"email": owner["email"], "password": "123456"}
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/owner/menu"))
        self.client.get("/logout")

        cashier = {"id": 2, "full_name": "Kasir", "email": "kasir@gmail.com", "role": "staff", "owner_id": 1}
        with patch.object(auth_routes, "authenticate_user", return_value=(cashier, cashier["email"], [])):
            response = self.client.post(
                "/login", data={"email": cashier["email"], "password": "123456"}
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/pos"))

    def test_cashier_cannot_open_owner_page(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 9
            session["role"] = "staff"
        with patch("app.utils.decorators.current_user", return_value={"id": 9, "role": "staff"}):
            response = self.client.get("/owner/menu")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/pos"))

    def test_report_page_preserves_owner_css_sidebar_topbar_and_chart(self):
        owner = {"id": 1, "full_name": "Owner", "role": "owner", "is_active": 1}
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "owner"
        with patch("app.utils.decorators.current_user", return_value=owner), patch.object(
            report_routes, "build_financial_report", return_value=self.sample_report()
        ):
            response = self.client.get("/owner/reports")
            print_response = self.client.get("/owner/reports/print")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(print_response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('/static/css/owner_shell.css', html)
        self.assertIn('/static/css/owner_menu.css', html)
        self.assertIn('class="owner-sidebar"', html)
        self.assertIn('class="owner-topbar owner-topbar--spread"', html)
        self.assertIn('class="sales-chart"', html)
        self.assertIn('--bar-height: 100%;', html)
        self.assertIn('/static/js/owner_shell.js', html)

    def test_all_static_assets_return_200(self):
        assets = (
            "/static/css/style.css",
            "/static/css/owner_shell.css",
            "/static/css/owner_menu.css",
            "/static/css/owner_menu_form.css",
            "/static/js/script.js",
            "/static/js/owner_shell.js",
            "/static/js/owner_categories.js",
            "/static/js/owner_menu_form.js",
            "/static/assets/logo-coffee.png",
            "/static/assets/logo-kyloffee.png",
        )
        for path in assets:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_owner_sidebar_stays_in_viewport_while_main_content_scrolls(self):
        source = (Path(__file__).resolve().parent.parent / "static" / "css" / "owner_shell.css").read_text()
        compact = " ".join(source.split())
        self.assertIn("body { margin: 0;", compact)
        self.assertIn("overflow: hidden;", compact)
        self.assertIn(".owner-page {", compact)
        self.assertIn("height: 100dvh;", compact)
        self.assertIn(".owner-main {", compact)
        self.assertIn("overflow-y: auto;", compact)
        self.assertIn(".owner-sidebar { position: relative;", compact)
        self.assertIn("--sidebar-expanded-width: 280px;", compact)
        self.assertIn(".owner-nav { width: 100%;", compact)
        self.assertIn(".owner-nav__link, .owner-logout { width: 100%;", compact)
        self.assertIn("min-height: 52px;", compact)
        self.assertIn(".owner-nav__icon { width: 40px; min-width: 40px;", compact)
        self.assertNotIn("fit-content", source)

    def test_category_search_normalizes_query_and_uses_bound_parameters(self):
        calls = []

        def fake_fetch_all(query, params=()):
            calls.append((" ".join(query.split()), params))
            return []

        with patch.object(menu_services, "fetch_all", side_effect=fake_fetch_all):
            menu_services.list_categories("black")
            menu_services.list_categories("BLACK")
            menu_services.list_categories("series")
            menu_services.list_categories("  BLACK   Series  ")
            menu_services.list_categories("")

        for index, expected_keyword in enumerate(("%black%", "%black%", "%series%")):
            self.assertEqual(calls[index][1][0], expected_keyword)
            self.assertEqual(calls[index][1][1], expected_keyword)

        search_query, search_params = calls[3]
        self.assertIn("LOWER(TRIM(c.name)) LIKE %s", search_query)
        self.assertIn("LOWER(TRIM(COALESCE(c.description, ''))) LIKE %s", search_query)
        self.assertIn("LOWER(REPLACE(TRIM(c.name), ' ', '')) LIKE %s", search_query)
        self.assertIn(
            "LOWER(REPLACE(TRIM(COALESCE(c.description, '')), ' ', '')) LIKE %s",
            search_query,
        )
        self.assertNotIn("c.normalized_name", search_query)
        self.assertEqual(
            search_params,
            (
                "%black series%",
                "%black series%",
                "%blackseries%",
                "%blackseries%",
            ),
        )
        self.assertNotIn("WHERE", calls[4][0])
        self.assertEqual(calls[4][1], ())

    def test_category_search_page_handles_empty_query_results_and_reset(self):
        owner = {"id": 1, "full_name": "Owner", "role": "owner", "is_active": 1}
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "owner"

        with patch("app.utils.decorators.current_user", return_value=owner), patch.object(
            menu_routes, "list_categories", return_value=[]
        ) as list_mock:
            response = self.client.get("/owner/categories?q=%20%20BLACK%20%20series%20%20")
        self.assertEqual(response.status_code, 200)
        list_mock.assert_called_once_with("BLACK series")
        html = response.get_data(as_text=True)
        self.assertIn('value="BLACK series"', html)
        self.assertIn('autocomplete="off"', html)
        self.assertIn("Kategori tidak ditemukan.", html)
        self.assertIn(">Reset</a>", html)
        self.assertNotIn("Belum ada kategori.", html)

        with patch("app.utils.decorators.current_user", return_value=owner), patch.object(
            menu_routes, "list_categories", return_value=[]
        ) as empty_mock:
            empty_response = self.client.get("/owner/categories?q=")
        empty_mock.assert_called_once_with("")
        empty_html = empty_response.get_data(as_text=True)
        self.assertIn("Belum ada kategori.", empty_html)
        self.assertNotIn("Kategori tidak ditemukan.", empty_html)
        self.assertNotIn(">Reset</a>", empty_html)

    def test_category_name_normalization_ignores_case_and_all_spaces(self):
        variants = (
            "Black Series",
            "black series",
            "blackseries",
            " Black   Series ",
            "BLACKSERIES",
        )
        normalized = {menu_services.normalize_category_name(value)[1] for value in variants}
        self.assertEqual(normalized, {"blackseries"})
        self.assertEqual(
            menu_services.normalize_category_name(" Black   Series "),
            ("Black Series", "blackseries"),
        )

    def test_category_create_allows_only_one_normalized_variant(self):
        stored = {}
        insert_count = 0

        def fake_find(normalized_name, exclude_id=None):
            if normalized_name in stored and stored[normalized_name]["id"] != exclude_id:
                return stored[normalized_name]
            return None

        class Cursor:
            lastrowid = 1

        def fake_commit(_query, params=()):
            nonlocal insert_count
            insert_count += 1
            stored[params[2]] = {"id": 1, "name": params[0]}
            return Cursor()

        variants = (
            "Black Series",
            "black series",
            "blackseries",
            " Black   Series ",
            "BLACKSERIES",
        )
        results = []
        with patch.object(
            menu_services, "find_category_by_normalized_name", side_effect=fake_find
        ), patch.object(menu_services, "commit", side_effect=fake_commit), patch.object(
            menu_services, "get_category_by_id", return_value={"id": 1, "name": "Black Series"}
        ):
            for value in variants:
                results.append(menu_services.create_category({"name": value}))

        self.assertEqual(insert_count, 1)
        self.assertEqual(sum(1 for category, _payload, errors in results if category and not errors), 1)
        self.assertEqual(
            sum(
                1
                for _category, _payload, errors in results
                if errors.get("name") == menu_services.CATEGORY_DUPLICATE_MESSAGE
            ),
            4,
        )

    def test_category_update_allows_own_name_and_rejects_another_category(self):
        executed = []

        class Cursor:
            def execute(self, query, params=()):
                executed.append((" ".join(query.split()), params))

        class Connection:
            def cursor(self):
                return Cursor()

        @contextmanager
        def fake_transaction():
            yield Connection()

        with patch.object(
            menu_services, "find_category_by_normalized_name", return_value=None
        ) as duplicate_check, patch.object(
            menu_services, "transaction", fake_transaction
        ), patch.object(
            menu_services,
            "get_category_by_id",
            return_value={"id": 1, "name": "Black Series"},
        ):
            category, payload, errors = menu_services.update_category(
                1, {"name": " BLACK   SERIES ", "description": "Signature"}
            )
        self.assertEqual(errors, {})
        self.assertEqual(category["id"], 1)
        self.assertEqual(payload["name"], "BLACK SERIES")
        duplicate_check.assert_called_once_with("blackseries", exclude_id=1)
        self.assertTrue(any("normalized_name = %s" in query for query, _params in executed))

        with patch.object(
            menu_services,
            "find_category_by_normalized_name",
            return_value={"id": 2, "name": "Black Series"},
        ), patch.object(menu_services, "transaction") as rejected_transaction:
            category, _payload, errors = menu_services.update_category(
                1, {"name": "blackseries"}
            )
        self.assertIsNone(category)
        self.assertEqual(errors["name"], menu_services.CATEGORY_DUPLICATE_MESSAGE)
        rejected_transaction.assert_not_called()

    def test_category_unique_index_handles_concurrent_creation(self):
        stored_names = set()
        lock = threading.Lock()

        class Cursor:
            lastrowid = 1

        def concurrent_commit(_query, params=()):
            with lock:
                if params[2] in stored_names:
                    raise pymysql.err.IntegrityError(
                        1062,
                        "Duplicate entry 'blackseries' for key "
                        "'categories.uq_categories_normalized_name'",
                    )
                stored_names.add(params[2])
            return Cursor()

        results = []

        def worker(name):
            results.append(menu_services.create_category({"name": name}))

        with patch.object(
            menu_services, "find_category_by_normalized_name", return_value=None
        ), patch.object(menu_services, "commit", side_effect=concurrent_commit), patch.object(
            menu_services,
            "get_category_by_id",
            return_value={"id": 1, "name": "Black Series"},
        ):
            threads = [
                threading.Thread(target=worker, args=("Black Series",)),
                threading.Thread(target=worker, args=("blackseries",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sum(1 for category, _payload, errors in results if category and not errors), 1)
        self.assertEqual(
            sum(
                1
                for _category, _payload, errors in results
                if errors.get("name") == menu_services.CATEGORY_DUPLICATE_MESSAGE
            ),
            1,
        )

    def test_category_cleanup_keeps_most_used_and_moves_menu_relations(self):
        from app import schema

        rows = [
            {
                "id": 10,
                "name": "Black Series",
                "description": "Utama",
                "menu_count": 5,
            },
            {
                "id": 11,
                "name": "blackseries",
                "description": None,
                "menu_count": 2,
            },
            {
                "id": 20,
                "name": "Coffee",
                "description": None,
                "menu_count": 2,
            },
        ]
        executed = []

        class Cursor:
            rowcount = 0

            def execute(self, query, params=()):
                compact = " ".join(query.split())
                executed.append((compact, params))
                if compact.startswith("UPDATE menus") and params[-1] == 11:
                    self.rowcount = 2
                elif compact.startswith("DELETE FROM categories"):
                    self.rowcount = 1
                else:
                    self.rowcount = 0

            def fetchall(self):
                return []

        class Connection:
            def cursor(self):
                return Cursor()

        @contextmanager
        def fake_transaction():
            yield Connection()

        with patch.object(schema, "category_rows_with_menu_counts", return_value=rows), patch.object(
            schema, "transaction", fake_transaction
        ), patch.object(schema, "fetch_value", return_value=0), patch.object(
            schema, "column_is_nullable", return_value=True
        ), patch.object(schema, "index_exists", return_value=False), patch.object(
            schema, "commit"
        ) as commit_mock:
            result = schema.migrate_category_name_uniqueness(cleanup_duplicates=True)

        self.assertEqual(result["deleted_categories"], 1)
        self.assertEqual(result["moved_menus"], 2)
        self.assertEqual(
            schema._category_keeper(
                [
                    {"id": 9, "menu_count": 2},
                    {"id": 8, "menu_count": 2},
                ]
            )["id"],
            8,
        )
        self.assertTrue(
            any(
                query.startswith("UPDATE menus SET category_id = %s")
                and params == (10, "Black Series", 11)
                for query, params in executed
            )
        )
        self.assertTrue(
            any(
                query == "DELETE FROM categories WHERE id = %s" and params == (11,)
                for query, params in executed
            )
        )
        created_indexes = [call.args[0] for call in commit_mock.call_args_list]
        self.assertIn(
            "ALTER TABLE categories MODIFY COLUMN normalized_name VARCHAR(255) NOT NULL",
            created_indexes,
        )
        self.assertIn(
            "CREATE UNIQUE INDEX uq_categories_normalized_name ON categories (normalized_name)",
            created_indexes,
        )
        self.assertFalse(any("pos_transactions" in query for query, _params in executed))

    def test_category_migration_checks_column_through_information_schema(self):
        from app import schema

        with patch.object(schema, "fetch_value", return_value=1) as fetch_mock:
            self.assertTrue(schema.column_exists("categories", "normalized_name"))
        query, params, default = fetch_mock.call_args.args
        self.assertIn("information_schema.columns", query)
        self.assertEqual(params, ("categories", "normalized_name"))
        self.assertEqual(default, 0)

    def test_cashier_status_is_single_source_and_syncs_is_active(self):
        self.assertEqual(cashier_services.normalize_status("Aktif", True), "active")
        self.assertEqual(cashier_services.normalize_status("Cuti", False), "leave")
        self.assertEqual(cashier_services.normalize_status("Nonaktif", False), "inactive")

        form_data = cashier_services.cashier_form_data(
            {
                "full_name": "Kasir",
                "email": "kasir@gmail.com",
                "staff_phone": "0812",
                "joined_date": "2026-07-01",
                "staff_status": "leave",
                "is_active": "1",
            }
        )
        self.assertEqual(form_data["staff_status"], "leave")
        self.assertFalse(form_data["is_active"])

        class Cursor:
            rowcount = 1

        with patch.object(
            cashier_services,
            "validate_cashier_form",
            return_value=("kasir@gmail.com", datetime(2026, 7, 1).date(), []),
        ), patch.object(cashier_services, "commit", return_value=Cursor()) as commit_mock:
            errors = cashier_services.update_cashier(7, form_data)
        self.assertEqual(errors, [])
        query, params = commit_mock.call_args.args
        self.assertIn("UPDATE users", query)
        self.assertNotIn("pos_transactions", query)
        self.assertNotIn("DELETE", query.upper())
        self.assertEqual(params[4], "leave")
        self.assertEqual(params[5], 0)

    def test_invalid_cashier_status_is_rejected(self):
        data = cashier_services.cashier_form_data(
            {
                "full_name": "Kasir",
                "email": "kasir@gmail.com",
                "staff_phone": "0812",
                "joined_date": "2026-07-01",
                "staff_status": "suspended",
            }
        )
        with patch.object(cashier_services, "fetch_one", return_value=None):
            _email, _joined_date, errors = cashier_services.validate_cashier_form(
                data, exclude_id=7
            )
        self.assertIn("Status kasir tidak valid.", errors)

    def test_cashier_login_respects_active_leave_and_inactive_status(self):
        password_hash = auth_services.generate_password_hash("123456")
        base_user = {
            "id": 7,
            "full_name": "Kasir",
            "email": "kasir@gmail.com",
            "password_hash": password_hash,
            "role": "staff",
            "owner_id": 1,
        }
        scenarios = (
            ("active", 1, None),
            ("leave", 0, "Akun kasir sedang berstatus cuti dan belum dapat digunakan."),
            ("inactive", 0, "Akun kasir telah dinonaktifkan."),
        )
        for status, is_active, expected_error in scenarios:
            with self.subTest(status=status), patch.object(
                auth_services,
                "find_user_by_email",
                return_value={**base_user, "staff_status": status, "is_active": is_active},
            ):
                user, _email, errors = auth_services.authenticate_user(
                    "kasir@gmail.com", "123456"
                )
            if expected_error:
                self.assertIsNone(user)
                self.assertEqual(errors, [expected_error])
            else:
                self.assertEqual(user["id"], 7)
                self.assertEqual(errors, [])

    def test_cashier_edit_form_has_only_status_dropdown(self):
        template = (
            Path(__file__).resolve().parent.parent / "templates" / "owner_staff_edit.html"
        ).read_text()
        self.assertEqual(template.count('name="staff_status"'), 1)
        self.assertNotIn("Akun Aktif", template)
        self.assertNotIn('name="is_active"', template)
        self.assertNotIn('id="statusToggle"', template)

        owner = {"id": 1, "full_name": "Owner", "role": "owner", "is_active": 1}
        cashier_row = {
            "id": 7,
            "full_name": "Kasir Cuti",
            "email": "kasir@gmail.com",
            "role": "staff",
            "staff_phone": "0812",
            "staff_position": "Kasir",
            "joined_date": datetime(2026, 7, 1).date(),
            "staff_status": "leave",
            "is_active": 0,
            "created_at": datetime(2026, 7, 1),
            "invite_code": "KASIR-TEST",
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "owner"
        with patch("app.utils.decorators.current_user", return_value=owner), patch.object(
            cashier_routes, "get_cashier", return_value=cashier_row
        ):
            response = self.client.get("/owner/users/7/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<option value="leave" selected>Cuti</option>', html)
        self.assertNotIn("Akun Aktif", html)

    def test_cashier_status_migration_uses_internal_values(self):
        from app import schema

        source = inspect.getsource(schema._normalize_users)
        self.assertIn("THEN 'active'", source)
        self.assertIn("THEN 'leave'", source)
        self.assertIn("THEN 'inactive'", source)
        self.assertIn("CASE WHEN staff_status = 'active' THEN 1 ELSE 0 END", source)

    def test_menu_code_renders_on_pos_and_checkout_route_is_wired(self):
        cashier = {"id": 2, "full_name": "Kasir", "role": "staff", "is_active": 1}
        product = {
            "id": 7,
            "code": "COF-007",
            "name": "Americano",
            "description": "Coffee",
            "price": 20000,
            "image": "",
            "stock": 5,
            "category": "Coffee",
            "category_id": 1,
            "is_active": 1,
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 2
            session["role"] = "staff"
        with patch("app.utils.decorators.current_user", return_value=cashier), patch.object(
            pos_routes, "list_active_menus", return_value=[product]
        ):
            response = self.client.get("/pos")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-code="COF-007"', html)
        self.assertIn('class="mock-product-code">COF-007', html)

        transaction = {
            "order_code": "POS-TEST-1",
            "subtotal_amount": 20000,
            "discount_amount": 0,
            "total_amount": 20000,
            "item_count": 1,
            "items": [{"menu_id": 7, "menu_code": "COF-007", "quantity": 1}],
        }
        with patch("app.utils.decorators.current_user", return_value=cashier), patch.object(
            pos_routes, "create_transaction", return_value=transaction
        ):
            checkout = self.client.post(
                "/api/pos/checkout",
                json={"payment_method": "qris", "items": [{"menu_id": 7, "quantity": 1}]},
            )
        self.assertEqual(checkout.status_code, 200)
        self.assertEqual(checkout.get_json()["transaction"]["items"][0]["menu_code"], "COF-007")

    def test_reports_have_no_owner_scope_filter(self):
        source = inspect.getsource(report_services)
        self.assertNotIn("owner_id =", source)
        self.assertIn("transaction_date BETWEEN %s AND %s", source)

    def test_cashier_listing_is_role_scoped_not_owner_scoped(self):
        source = inspect.getsource(cashier_services.list_cashiers)
        self.assertNotIn("owner_id =", source)
        self.assertIn("LOWER", inspect.getsource(cashier_services.cashier_role_sql))

    def test_menu_code_uses_lock_retry_and_database_unique_index(self):
        source = inspect.getsource(menu_services.create_menu)
        self.assertIn("FOR UPDATE", source)
        self.assertIn("MAX_CODE_RETRIES", source)
        schema_source = inspect.getsource(__import__("app.schema", fromlist=["ensure_schema"]))
        self.assertIn("CREATE UNIQUE INDEX uq_menus_code", schema_source)

    def test_menu_name_normalization_collapses_case_and_whitespace(self):
        variants = (
            "DARK CHOCO",
            "Dark Choco",
            " dark   choco ",
            "DARK    CHOCO",
            "darkchoco",
        )
        self.assertEqual({menu_services.normalize_menu_name(value) for value in variants}, {"darkchoco"})
        self.assertEqual(menu_services.clean_menu_name(" Dark   Choco "), "Dark Choco")

    def test_create_rejects_all_duplicate_menu_name_variants_before_generating_code(self):
        existing = {"id": 5, "code": "NON-005", "name": "Dark Choco"}
        variants = ("DARK CHOCO", "dark choco", " Dark Choco ", "Dark   Choco", "darkchoco")
        for name in variants:
            with self.subTest(name=name), patch.object(
                menu_services, "get_category", return_value={"id": 1, "name": "Non Coffee"}
            ), patch.object(
                menu_services, "find_menu_by_normalized_name", return_value=existing
            ), patch.object(menu_services, "transaction") as transaction_mock:
                menu, payload, errors = menu_services.create_menu(
                    {"name": name, "category_id": 1, "price": 10000, "stock": 5}
                )
            self.assertIsNone(menu)
            self.assertEqual(payload["normalized_name"], "darkchoco")
            self.assertIn(menu_services.MENU_NAME_CREATE_DUPLICATE, errors)
            transaction_mock.assert_not_called()

    def test_edit_allows_own_name_but_rejects_another_menu_name(self):
        existing = {
            "id": 5,
            "name": "Dark Choco",
            "category_id": 1,
            "category_name": "Non Coffee",
            "code": "NON-005",
            "price": 10000,
            "stock": 5,
            "description": "Chocolate",
            "image": "",
            "is_active": 1,
        }
        with patch.object(menu_services, "get_menu", side_effect=[existing, existing]), patch.object(
            menu_services, "get_category", return_value={"id": 1, "name": "Non Coffee"}
        ), patch.object(menu_services, "find_menu_by_normalized_name", return_value=None) as duplicate_check, patch.object(
            menu_services, "commit"
        ) as commit_mock:
            updated, payload, errors = menu_services.update_menu(5, {"name": " Dark   Choco "})
        self.assertEqual(errors, [])
        self.assertEqual(updated["id"], 5)
        self.assertEqual(payload["name"], "Dark Choco")
        duplicate_check.assert_called_once_with("darkchoco", exclude_id=5)
        self.assertIn("normalized_name = %s", " ".join(commit_mock.call_args.args[0].split()))

        with patch.object(menu_services, "get_menu", return_value=existing), patch.object(
            menu_services, "get_category", return_value={"id": 1, "name": "Non Coffee"}
        ), patch.object(
            menu_services,
            "find_menu_by_normalized_name",
            return_value={"id": 8, "name": "Dark Choco", "code": "NON-008"},
        ), patch.object(menu_services, "commit") as rejected_commit:
            updated, _payload, errors = menu_services.update_menu(5, {"name": "dark choco"})
        self.assertIsNone(updated)
        self.assertIn(menu_services.MENU_NAME_EDIT_DUPLICATE, errors)
        rejected_commit.assert_not_called()

    def test_menu_name_queries_use_normalized_column_and_exclude_edited_id(self):
        queries = []

        def fake_fetch_one(query, params):
            queries.append((" ".join(query.split()), params))
            return None

        with patch.object(menu_services, "fetch_one", side_effect=fake_fetch_one), patch.object(
            menu_services, "fetch_all", return_value=[]
        ):
            menu_services.find_menu_by_normalized_name("darkchoco")
            menu_services.find_menu_by_normalized_name("darkchoco", exclude_id=5)
        self.assertIn("WHERE normalized_name = %s", queries[0][0])
        self.assertNotIn("id <>", queries[0][0])
        self.assertIn("AND id <> %s", queries[1][0])
        self.assertEqual(queries[1][1], ("darkchoco", 5))

    def test_legacy_duplicate_audit_uses_python_whitespace_normalization(self):
        from app.schema import audit_menu_name_duplicates

        rows = [
            {"id": 3, "code": "NON-006", "name": "DARK CHOCO"},
            {"id": 4, "code": "NON-007", "name": " dark   choco "},
            {"id": 8, "code": "BLA-011", "name": "Coffee Ginger"},
        ]
        duplicates = audit_menu_name_duplicates(rows)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["normalized_name"], "darkchoco")
        self.assertEqual([menu["id"] for menu in duplicates[0]["menus"]], [3, 4])

    def test_migration_defers_backfill_and_unique_index_when_legacy_duplicates_exist(self):
        from app import schema

        rows = [
            {"id": 3, "code": "NON-006", "name": "DARK CHOCO"},
            {"id": 4, "code": "NON-007", "name": "Dark   Choco"},
        ]
        with patch.object(schema, "fetch_all", return_value=rows), patch.object(
            schema, "transaction"
        ) as transaction_mock, patch.object(schema, "commit") as commit_mock:
            result = schema.migrate_menu_name_uniqueness()
        self.assertEqual(result["backfill"], "blocked")
        self.assertEqual(result["unique_index"], "not_created")
        transaction_mock.assert_not_called()
        commit_mock.assert_not_called()

    def test_legacy_menu_name_column_is_made_nullable_for_canonical_inserts(self):
        from app import schema

        with patch.object(schema, "table_columns", return_value={"id", "menu_name", "name"}), patch.object(
            schema, "commit"
        ) as commit_mock:
            schema._relax_legacy_menu_columns()
        commit_mock.assert_called_once_with("ALTER TABLE menus MODIFY COLUMN menu_name VARCHAR(255) NULL")

    def test_pos_does_not_hide_duplicate_rows_and_search_is_case_insensitive(self):
        pos_query_source = inspect.getsource(pos_services.list_active_menus).upper()
        self.assertNotIn("DISTINCT", pos_query_source)
        self.assertNotIn("GROUP BY", pos_query_source)
        script_source = (Path(__file__).resolve().parent.parent / "static" / "js" / "script.js").read_text()
        self.assertIn(".toLowerCase().replace(/\\s+/g, \" \")", script_source)

    def test_database_unique_name_index_allows_only_one_concurrent_insert(self):
        stored_names = set()
        lock = threading.Lock()

        class Cursor:
            lastrowid = 1

            def execute(self, query, params):
                if "INSERT INTO menus" not in " ".join(query.split()):
                    return
                with lock:
                    if params[1] in stored_names:
                        raise pymysql.err.IntegrityError(
                            1062,
                            "Duplicate entry 'coffee latte' for key 'menus.uq_menus_normalized_name'",
                        )
                    stored_names.add(params[1])

        class Connection:
            def cursor(self):
                return Cursor()

        @contextmanager
        def fake_transaction():
            yield Connection()

        results = []

        def worker():
            results.append(
                menu_services.create_menu(
                    {
                        "name": "Coffee Latte",
                        "category_id": 1,
                        "code": "LAT-001",
                        "price": 10000,
                        "stock": 5,
                    }
                )
            )

        with patch.object(menu_services, "get_category", return_value={"id": 1, "name": "Coffee"}), patch.object(
            menu_services, "find_menu_by_normalized_name", return_value=None
        ), patch.object(menu_services, "transaction", fake_transaction), patch.object(
            menu_services, "get_menu", return_value={"id": 1, "code": "LAT-001"}
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sum(1 for menu, _payload, errors in results if menu and not errors), 1)
        self.assertEqual(
            sum(1 for _menu, _payload, errors in results if menu_services.MENU_NAME_CONCURRENT_DUPLICATE in errors),
            1,
        )

    def test_concurrent_menu_creation_produces_distinct_codes(self):
        state = {"next": 1, "menus": {}, "last_id": 0}
        lock = threading.Lock()

        class Cursor:
            lastrowid = None
            selected = None

            def execute(self, query, params):
                compact = " ".join(query.split())
                if compact.startswith("SELECT next_value"):
                    self.selected = state["next"]
                elif compact.startswith("UPDATE menu_code_sequences"):
                    state["next"] = int(params[0])
                elif compact.startswith("INSERT INTO menus"):
                    state["last_id"] += 1
                    self.lastrowid = state["last_id"]
                    state["menus"][self.lastrowid] = params[4]

            def fetchone(self):
                return {"next_value": self.selected}

        class Connection:
            def cursor(self):
                return Cursor()

        @contextmanager
        def locked_transaction():
            with lock:
                yield Connection()

        def fake_get_menu(menu_id):
            return {"id": menu_id, "code": state["menus"][menu_id]}

        results = []

        def worker(number):
            menu, _payload, errors = menu_services.create_menu(
                {"name": f"Americano {number}", "category_id": 1, "price": 10000, "stock": 5}
            )
            self.assertEqual(errors, [])
            results.append(menu["code"])

        with patch.object(menu_services, "get_category", return_value={"id": 1, "name": "Coffee"}), patch.object(
            menu_services, "find_menu_by_normalized_name", return_value=None
        ), patch.object(
            menu_services, "transaction", locked_transaction
        ), patch.object(menu_services, "get_menu", side_effect=fake_get_menu):
            threads = [threading.Thread(target=worker, args=(number,)) for number in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(len(results), 8)
        self.assertEqual(len(set(results)), 8)

    def test_pos_keeps_menu_id_and_snapshots_menu_code(self):
        source = inspect.getsource(pos_services.create_transaction)
        self.assertIn('"menu_id"', source)
        self.assertIn('"menu_code"', source)
        self.assertIn("INSERT INTO pos_transaction_items", source)

    def test_checkout_service_saves_transaction_reduces_stock_and_feeds_global_report(self):
        state = {"stock": 5, "transactions": [], "items": []}

        class Cursor:
            lastrowid = None
            rowcount = 0

            def execute(self, query, params):
                compact = " ".join(query.split())
                if compact.startswith("INSERT INTO pos_transactions"):
                    self.lastrowid = 31
                    state["transactions"].append({"total": params[7], "params": params})
                    self.rowcount = 1
                elif compact.startswith("UPDATE menus SET stock"):
                    quantity = int(params[0])
                    if state["stock"] >= quantity:
                        state["stock"] -= quantity
                        self.rowcount = 1
                    else:
                        self.rowcount = 0
                elif compact.startswith("INSERT INTO pos_transaction_items"):
                    state["items"].append(params)
                    self.rowcount = 1

        class Connection:
            def cursor(self):
                return Cursor()

            def commit(self):
                return None

            def rollback(self):
                return None

        menu_row = {"id": 7, "code": "COF-007", "name": "Americano", "price": 20000, "stock": 5, "is_active": 1}
        with self.app.test_request_context("/api/pos/checkout"):
            from flask import session

            session["user_id"] = 2
            session["owner_id"] = 1
            with patch.object(pos_services, "fetch_all", return_value=[menu_row]), patch.object(
                pos_services, "get_db", return_value=Connection()
            ):
                transaction = pos_services.create_transaction(
                    {
                        "payment_method": "Cash",
                        "received_amount": 20000,
                        "items": [{"menu_id": 7, "quantity": 1}],
                    }
                )

        self.assertEqual(transaction["total_amount"], 20000)
        self.assertEqual(state["stock"], 4)
        self.assertEqual(len(state["transactions"]), 1)
        self.assertEqual(state["items"][0][1], 7)
        self.assertEqual(state["items"][0][2], "COF-007")

        with patch.object(
            report_services,
            "fetch_one",
            return_value={"revenue": state["transactions"][0]["total"], "transactions": 1},
        ):
            totals = report_services.get_period_totals(
                datetime(2026, 7, 1).date(), datetime(2026, 7, 31).date()
            )
        self.assertEqual(totals["revenue"], 20000)
        self.assertEqual(totals["transactions"], 1)


if __name__ == "__main__":
    unittest.main()
