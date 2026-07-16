from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from app.database import commit
from app.menu.services import (
    CATEGORY_DUPLICATE_MESSAGE,
    category_options,
    create_category,
    create_menu,
    delete_category,
    get_category_by_id,
    get_menu,
    list_categories,
    list_menus,
    save_menu_image,
    update_category,
    update_menu,
)
from app.utils.decorators import owner_required


bp = Blueprint("menu", __name__)


def menu_owner_name():
    return session.get("full_name") or "Owner"


@bp.route("/owner/menu")
@owner_required
def owner_menu():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 8
    menus, total = list_menus(page, per_page)
    return render_template(
        "owner_menu.html",
        owner_name=menu_owner_name(),
        active_page="menu",
        menus=menus,
        page=page,
        total_pages=max(1, (total + per_page - 1) // per_page),
        total=total,
        per_page=per_page,
    )


def _menu_form_data(existing=None):
    return {
        "name": request.form.get("name", "").strip(),
        "category_id": request.form.get("category_id", "").strip(),
        "code": request.form.get("code", "").strip() or (existing.get("code") if existing else ""),
        "price": request.form.get("price", "").strip(),
        "stock": request.form.get("stock", "").strip(),
        "description": request.form.get("description", "").strip(),
        "image": existing.get("image", "") if existing else "",
        "is_active": request.form.get("is_active", "1") == "1",
    }


@bp.route("/owner/menu/add", methods=["GET", "POST"])
@owner_required
def owner_menu_add():
    options = category_options()
    form_data = _menu_form_data() if request.method == "POST" else {}
    errors = []
    if request.method == "POST":
        image, image_error = save_menu_image(request.files.get("image"))
        form_data["image"] = image
        if image_error:
            errors.append(image_error)
        if not errors:
            menu, _payload, errors = create_menu(form_data, require_stock=True)
            if menu:
                flash(f"Menu berhasil ditambahkan dengan kode {menu['code']}.", "success")
                return redirect(url_for("menu.owner_menu"))
    return render_template(
        "owner_menu_add.html",
        owner_name=menu_owner_name(),
        active_page="menu",
        category_options=options,
        form_data=form_data,
        errors=errors,
    )


@bp.route("/owner/menu/<int:menu_id>/edit", methods=["GET", "POST"])
@owner_required
def owner_menu_edit(menu_id):
    existing = get_menu(menu_id)
    if not existing:
        flash("Menu tidak ditemukan.", "error")
        return redirect(url_for("menu.owner_menu"))
    form_data = _menu_form_data(existing) if request.method == "POST" else {}
    errors = []
    if request.method == "POST":
        image, image_error = save_menu_image(request.files.get("image"))
        if image_error:
            errors.append(image_error)
        if image:
            form_data["image"] = image
        if not errors:
            updated, _payload, errors = update_menu(menu_id, form_data, require_stock=True)
            if updated:
                flash("Menu berhasil diperbarui.", "success")
                return redirect(url_for("menu.owner_menu"))
    return render_template(
        "owner_menu_edit.html",
        owner_name=menu_owner_name(),
        active_page="menu",
        category_options=category_options(),
        menu=existing,
        form_data=form_data,
        errors=errors,
    )


@bp.route("/owner/menu/<int:menu_id>/delete", methods=["POST"])
@owner_required
def owner_menu_delete(menu_id):
    if not get_menu(menu_id):
        flash("Menu tidak ditemukan.", "error")
    else:
        commit("DELETE FROM menus WHERE id = %s", (menu_id,))
        flash("Menu berhasil dihapus.", "success")
    return redirect(url_for("menu.owner_menu"))


def _render_categories(category_form=None):
    search_query = " ".join(request.args.get("q", "").strip().split())
    return render_template(
        "owner_categories.html",
        owner_name=menu_owner_name(),
        active_page="categories",
        categories=list_categories(search_query),
        search_query=search_query,
        category_form=category_form or {},
    )


@bp.route("/owner/categories", methods=["GET", "POST"])
@owner_required
def owner_categories():
    if request.method == "POST":
        category, payload, errors = create_category(request.form)
        if errors:
            if errors.get("name") == CATEGORY_DUPLICATE_MESSAGE:
                flash(CATEGORY_DUPLICATE_MESSAGE, "error")
            return _render_categories({"mode": "create", **payload, "errors": errors})
        flash("Kategori berhasil ditambahkan.", "success")
        return redirect(url_for("menu.owner_categories"))
    return _render_categories()


@bp.route("/owner/categories/<int:category_id>/edit", methods=["POST"])
@owner_required
def owner_category_edit(category_id):
    if not get_category_by_id(category_id):
        flash("Kategori tidak ditemukan.", "error")
        return redirect(url_for("menu.owner_categories"))
    category, payload, errors = update_category(category_id, request.form)
    if errors:
        if errors.get("name") == CATEGORY_DUPLICATE_MESSAGE:
            flash(CATEGORY_DUPLICATE_MESSAGE, "error")
        return _render_categories({"mode": "edit", "id": category_id, **payload, "errors": errors})
    flash("Kategori berhasil diperbarui.", "success")
    return redirect(url_for("menu.owner_categories"))


@bp.route("/owner/categories/<int:category_id>/delete", methods=["POST"])
@owner_required
def owner_category_delete(category_id):
    if not get_category_by_id(category_id):
        flash("Kategori tidak ditemukan.", "error")
    else:
        error = delete_category(category_id)
        flash(error or "Kategori berhasil dihapus.", "error" if error else "success")
    return redirect(url_for("menu.owner_categories"))


@bp.route("/api/owner/categories", methods=["GET", "POST"])
@owner_required
def owner_categories_api():
    if request.method == "GET":
        search_query = " ".join(request.args.get("q", "").strip().split())
        return jsonify({"success": True, "categories": list_categories(search_query)})
    category, _payload, errors = create_category(request.get_json(silent=True) or {})
    if errors:
        return jsonify({"success": False, "message": next(iter(errors.values())), "errors": errors}), 400
    return jsonify({"success": True, "message": "Kategori berhasil ditambahkan.", "category": category})


@bp.route("/api/owner/categories/<int:category_id>", methods=["PUT", "PATCH", "DELETE"])
@owner_required
def owner_category_api(category_id):
    if not get_category_by_id(category_id):
        return jsonify({"success": False, "message": "Kategori tidak ditemukan."}), 404
    if request.method == "DELETE":
        error = delete_category(category_id)
        if error:
            return jsonify({"success": False, "message": error}), 400
        return jsonify({"success": True, "message": "Kategori berhasil dihapus."})
    category, _payload, errors = update_category(category_id, request.get_json(silent=True) or {})
    if errors:
        return jsonify({"success": False, "message": next(iter(errors.values())), "errors": errors}), 400
    return jsonify({"success": True, "message": "Kategori berhasil diperbarui.", "category": category})


@bp.route("/api/owner/menus", methods=["GET", "POST"])
@owner_required
def owner_menus_api():
    if request.method == "POST":
        menu, _payload, errors = create_menu(request.get_json(silent=True) or {})
        if errors:
            return jsonify({"success": False, "message": errors[0]}), 400
        return jsonify({"success": True, "message": "Menu berhasil ditambahkan.", "code": menu["code"], "menu": menu})

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = max(1, min(request.args.get("per_page", 6, type=int), 100))
    menus, total = list_menus(
        page,
        per_page,
        request.args.get("q", "").strip(),
        request.args.get("category_id", type=int),
    )
    return jsonify(
        {
            "menus": menus,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        }
    )


@bp.route("/api/owner/menus/<int:menu_id>", methods=["PUT"])
@owner_required
def owner_menu_api(menu_id):
    menu, _payload, errors = update_menu(menu_id, request.get_json(silent=True) or {})
    if errors:
        return jsonify({"success": False, "message": errors[0]}), 400
    return jsonify({"success": True, "message": "Menu berhasil diperbarui.", "menu": menu})
