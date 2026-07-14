from functools import wraps

from flask import flash, redirect, session, url_for

from app.auth.services import CASHIER_ROLE, normalize_role, role_label
from app.database import fetch_one


def set_authenticated_session(user):
    role = normalize_role(user.get("role"))
    session.permanent = True
    session["user_id"] = user.get("id")
    session["full_name"] = user.get("full_name")
    session["name"] = user.get("full_name")
    session["username"] = user.get("full_name")
    session["role"] = role
    session["role_label"] = role_label(role)
    session["owner_id"] = user.get("id") if role == "owner" else user.get("owner_id")


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = fetch_one(
        "SELECT id, full_name, email, role, owner_id, is_active FROM users WHERE id = %s",
        (user_id,),
    )
    if not user:
        session.clear()
        return None
    role = normalize_role(user.get("role"))
    active_value = user.get("is_active")
    if role not in {"owner", CASHIER_ROLE} or int(1 if active_value is None else active_value) != 1:
        session.clear()
        return None
    set_authenticated_session(user)
    return user


def redirect_for_role():
    if normalize_role(session.get("role")) == "owner":
        return redirect(url_for("menu.owner_menu"))
    if normalize_role(session.get("role")) == CASHIER_ROLE:
        return redirect(url_for("pos.pos"))
    session.clear()
    return redirect(url_for("auth.login"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Silakan login terlebih dahulu.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Silakan login terlebih dahulu.", "error")
                return redirect(url_for("auth.login"))
            if normalize_role(user.get("role")) != required_role:
                return redirect_for_role()
            return view(*args, **kwargs)

        return wrapped

    return decorator


owner_required = role_required("owner")
cashier_required = role_required(CASHIER_ROLE)
staff_required = cashier_required
