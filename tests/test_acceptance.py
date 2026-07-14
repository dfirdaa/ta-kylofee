import inspect
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.auth import services as auth_services
from app.auth import routes as auth_routes
from app.cashier import services as cashier_services
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
        legacy_database = Path(__file__).resolve().parent.parent / ("database" + ".db")
        self.assertFalse(legacy_database.exists())

    def test_public_auth_pages_open_without_database_access(self):
        for path in ("/login", "/register/owner", "/register/kasir"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

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
