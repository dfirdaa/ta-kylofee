from flask import Flask, jsonify, render_template, request

from config import BASE_DIR, Config

from app import database
from app.database import DatabaseUnavailable
from app.integrations import menu_image_url
from app.menu.services import category_key
from app.schema import ensure_schema


def create_app(config_object=Config):
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_object)
    app.config.setdefault("AUTO_MIGRATE", True)
    database.init_app(app)

    from app.auth.routes import bp as auth_bp
    from app.cashier.routes import bp as cashier_bp
    from app.menu.routes import bp as menu_bp
    from app.owner.routes import bp as owner_bp
    from app.pos.routes import bp as pos_bp
    from app.reports.routes import bp as reports_bp

    for blueprint in (auth_bp, owner_bp, cashier_bp, menu_bp, reports_bp, pos_bp):
        app.register_blueprint(blueprint)

    app.add_template_global(category_key, "category_key")
    app.add_template_global(menu_image_url, "menu_image_url")

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

