from pathlib import Path

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
    app.config.setdefault("AUTO_MIGRATE", True)
    register_database(app)

    from app.auth.routes import bp as auth_bp
    from app.cashier.routes import bp as cashier_bp
    from app.menu.routes import bp as menu_bp
    from app.owner.routes import bp as owner_bp
    from app.pos.routes import bp as pos_bp
    from app.reports.routes import bp as reports_bp

    for blueprint in (auth_bp, owner_bp, cashier_bp, menu_bp, reports_bp, pos_bp):
        app.register_blueprint(blueprint)

    register_template_helpers(app)
    assert_no_duplicate_routes(app)
    register_route_audit_cli(app)

    @app.before_request
    def prepare_tidb_schema():
        if not app.config.get("AUTO_MIGRATE", True):
            return None
        if request.endpoint == "static" or request.path in {"/favicon.ico", "/favicon.png"}:
            return None
        ensure_schema()
        return None

    @app.errorhandler(DatabaseUnavailable)
    def handle_database_unavailable(exc):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": str(exc)}), 503
        return render_template("database_error.html", message=str(exc)), 503

    return app
