from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.cashier.services import (
    STAFF_POSITIONS,
    STAFF_STATUS_OPTIONS,
    cashier_form_data,
    create_cashier,
    create_invitation,
    format_cashier,
    get_cashier,
    list_cashiers,
    list_invitations,
    update_cashier,
)
from app.utils.decorators import owner_required


bp = Blueprint("cashier", __name__)


def cashier_owner_name():
    return session.get("full_name") or "Owner"


@bp.route("/owner/users")
@owner_required
def owner_users():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 6
    staff_members, total = list_cashiers(page, per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if total and page > total_pages:
        return redirect(url_for("cashier.owner_staff", page=total_pages))
    return render_template(
        "owner_staff.html",
        owner_name=cashier_owner_name(),
        active_page="staff",
        staff_members=staff_members,
        invitations=list_invitations(),
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=per_page,
    )


@bp.route("/owner/staff")
@owner_required
def owner_staff():
    return owner_users()


@bp.route("/owner/staff/invite", methods=["GET", "POST"])
@owner_required
def owner_staff_invite():
    if request.method == "POST":
        code = create_invitation(session["user_id"])
        flash(f"Kode undangan berhasil dibuat: {code}", "success")
    return redirect(url_for("cashier.owner_staff"))


@bp.route("/owner/users/add", methods=["GET", "POST"])
@owner_required
def owner_users_add():
    form_data = cashier_form_data(request.form) if request.method == "POST" else {}
    errors = []
    if request.method == "POST":
        errors = create_cashier(form_data, session["user_id"])
        if not errors:
            flash("Kasir berhasil ditambahkan. Password awal tidak ditampilkan demi keamanan.", "success")
            return redirect(url_for("cashier.owner_staff"))
    return render_template(
        "owner_staff_add.html",
        owner_name=cashier_owner_name(),
        active_page="staff",
        form_data=form_data,
        staff_positions=STAFF_POSITIONS,
        errors=errors,
    )


@bp.route("/owner/users/<int:staff_id>/edit", methods=["GET", "POST"])
@owner_required
def owner_users_edit(staff_id):
    row = get_cashier(staff_id)
    if not row:
        flash("Data kasir tidak ditemukan.", "error")
        return redirect(url_for("cashier.owner_staff"))
    staff = format_cashier(row)
    form_data = cashier_form_data(request.form) if request.method == "POST" else {}
    errors = []
    if request.method == "POST":
        errors = update_cashier(staff_id, form_data)
        if not errors:
            flash("Data kasir berhasil diperbarui.", "success")
            return redirect(url_for("cashier.owner_staff"))
    return render_template(
        "owner_staff_edit.html",
        owner_name=cashier_owner_name(),
        active_page="staff",
        staff=staff,
        form_data=form_data,
        staff_positions=STAFF_POSITIONS,
        staff_statuses=STAFF_STATUS_OPTIONS,
        errors=errors,
    )
