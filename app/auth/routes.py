from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.auth.services import (
    authenticate_user,
    redirect_for_role,
    register_user,
    set_authenticated_session,
)
from app.utils.decorators import current_user
from app.utils.email import send_email
from app.utils.roles import role_label


bp = Blueprint("auth", __name__)


@bp.route("/")
def opening():
    if session.get("user_id") and current_user():
        return redirect_for_role()
    session.clear()
    return render_template("opening.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") and current_user():
        return redirect_for_role()
    if session.get("user_id"):
        session.clear()

    if request.method == "POST":
        user, email, errors = authenticate_user(request.form.get("email"), request.form.get("password", ""))
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("login.html", email=email)
        session.clear()
        set_authenticated_session(user)
        flash(f"Login sebagai {role_label(user['role'])} berhasil.", "success")
        return redirect_for_role()

    return render_template(
        "login.html",
        email=request.args.get("email", "").strip() or session.pop("registered_email", ""),
    )


def _register(role, template_name):
    if session.get("user_id") and current_user():
        return redirect_for_role()
    if request.method == "GET":
        return render_template(template_name)

    user, form_data, errors = register_user(role, request.form)
    if errors:
        for error in errors:
            flash(error, "error")
        return render_template(template_name, **form_data)

    label = role_label(user["role"])
    send_email(
        user["email"],
        "Registrasi Kyloffee Berhasil",
        f"<h2>Halo {user['full_name']}</h2><p>Akun {label} Kyloffee berhasil dibuat.</p>",
    )
    flash(f"Registrasi {label} berhasil, silakan login.", "success")
    session["registered_email"] = user["email"]
    return redirect(url_for("auth.login", email=user["email"]))


@bp.route("/register/owner", methods=["GET", "POST"])
def register_owner():
    return _register("owner", "register_owner.html")


@bp.route("/register/kasir", methods=["GET", "POST"])
def register_cashier():
    return _register("staff", "register_staff.html")


@bp.route("/register/staff", methods=["GET", "POST"])
def register_staff():
    return redirect(url_for("auth.register_cashier"), code=307 if request.method == "POST" else 302)


@bp.route("/dashboard")
def dashboard():
    if not current_user():
        flash("Silakan login terlebih dahulu.", "error")
        return redirect(url_for("auth.login"))
    return redirect_for_role()


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/favicon.ico")
@bp.route("/favicon.png")
def favicon():
    return "", 204
