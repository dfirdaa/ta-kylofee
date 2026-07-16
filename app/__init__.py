from pathlib import Path
from time import monotonic

from flask import Flask, jsonify, render_template, request

from config import Config

from app.database import DatabaseUnavailable, init_app as init_database
from app.menu.services import category_key, menu_image_url
from app.routing import assert_no_duplicate_routes, register_route_audit_cli
from app.schema import ensure_schema


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def register_database(app):
    init_database(app)


def register_template_helpers(app):
    app.add_template_global(category_key, "category_key")
    app.add_template_global(menu_image_url, "menu_image_url")


def create_app(config_object=Config):
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_object)
    app.config.setdefault("AUTO_MIGRATE", False)
    app.config.setdefault("SCHEMA_RETRY_SECONDS", 60)
    register_database(app)

    try:
        from app.auth.routes import bp as auth_bp
        from app.cashier.routes import bp as cashier_bp
        from app.menu.routes import bp as menu_bp
        from app.owner.routes import bp as owner_bp
        from app.pos.routes import bp as pos_bp
        from app.reports.routes import bp as reports_bp
    except Exception:
        app.logger.exception("Import Blueprint gagal saat create_app().")
        raise

    for blueprint in (auth_bp, owner_bp, cashier_bp, menu_bp, reports_bp, pos_bp):
        app.register_blueprint(blueprint)

    register_template_helpers(app)
    assert_no_duplicate_routes(app)
    register_route_audit_cli(app)

    app.extensions.setdefault("tidb_schema_last_error", None)
    app.extensions.setdefault("tidb_schema_retry_at", 0.0)

    @app.before_request
    def prepare_tidb_schema():
        if not app.config.get("AUTO_MIGRATE", False):
            return None
        if request.endpoint == "static" or request.path in {"/favicon.ico", "/favicon.png"}:
            return None
        if monotonic() < app.extensions["tidb_schema_retry_at"]:
            return None
        try:
            ensure_schema()
            app.extensions["tidb_schema_last_error"] = None
        except Exception as exc:
            # Migrasi tidak boleh membuat seluruh Function gagal. Route publik tetap
            # hidup; route yang membutuhkan DB akan menghasilkan 503 yang aman.
            app.extensions["tidb_schema_last_error"] = type(exc).__name__
            app.extensions["tidb_schema_retry_at"] = monotonic() + int(
                app.config.get("SCHEMA_RETRY_SECONDS", 60)
            )
            app.logger.exception(
                "AUTO_MIGRATE gagal; request dilanjutkan dan migrasi akan dicoba ulang."
            )
        return None

    @app.get("/_health")
    def health():
        config_errors = list(app.config.get("CONFIG_ERRORS", ()))
        database_errors = app.config.get("DB_CONFIG_ERRORS", ())
        migration_error = app.extensions.get("tidb_schema_last_error")
        database_configured = not database_errors and all(
            app.config.get(name)
            for name in ("TIDB_HOST", "TIDB_USER", "TIDB_PASSWORD", "TIDB_DATABASE")
        )
        status = "degraded" if not database_configured or migration_error else "ok"
        return jsonify(
            {
                "status": status,
                "database_configured": database_configured,
                "auto_migrate": bool(app.config.get("AUTO_MIGRATE")),
                "migration_error": migration_error,
                "config_errors": config_errors,
            }
        ), (200 if status == "ok" else 503)

    @app.cli.command("migrate-db")
    def migrate_db_command():
        """Run the idempotent TiDB schema migration outside request handling."""
        ensure_schema()
        app.logger.info("Migrasi TiDB selesai.")

    @app.errorhandler(DatabaseUnavailable)
    def handle_database_unavailable(exc):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": str(exc)}), 503
        return render_template("database_error.html", message=str(exc)), 503

    return app
