import inspect
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app
from app.auth import services as auth_services
from app.cashier import services as cashier_services
from app.menu import services as menu_services
from app.pos import services as pos_services
from app.reports import services as report_services
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

    def test_cashier_cannot_open_owner_page(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 9
            session["role"] = "staff"
        with patch("app.utils.decorators.current_user", return_value={"id": 9, "role": "staff"}):
            response = self.client.get("/owner/menu")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/pos"))

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
                    state["menus"][self.lastrowid] = params[3]

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

        def worker():
            menu, _payload, errors = menu_services.create_menu(
                {"name": "Americano", "category_id": 1, "price": 10000, "stock": 5}
            )
            self.assertEqual(errors, [])
            results.append(menu["code"])

        with patch.object(menu_services, "get_category", return_value={"id": 1, "name": "Coffee"}), patch.object(
            menu_services, "transaction", locked_transaction
        ), patch.object(menu_services, "get_menu", side_effect=fake_get_menu):
            threads = [threading.Thread(target=worker) for _ in range(8)]
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


if __name__ == "__main__":
    unittest.main()
