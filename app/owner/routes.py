from flask import Blueprint, redirect, render_template, session, url_for

from app.utils.decorators import owner_required


bp = Blueprint("owner", __name__)


@bp.route("/owner/dashboard")
@owner_required
def owner_dashboard():
    return redirect(url_for("menu.owner_menu"))


@bp.route("/owner/products")
@owner_required
def owner_products():
    return render_template(
        "dashboard_placeholder.html",
        full_name=session.get("full_name", "Owner"),
        role="Owner",
        page_title="Produk Owner",
    )


@bp.route("/owner/<path:unused_path>")
@owner_required
def owner_fallback(unused_path):
    return redirect(url_for("menu.owner_menu"))

