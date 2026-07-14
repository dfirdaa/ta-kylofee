from functools import wraps

from flask import flash, redirect, session, url_for

from app.auth.services import redirect_for_role, set_authenticated_session
from app.database import fetch_one
from app.utils.roles import CASHIER_ROLE, normalize_role


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


def login_required(view):
    @wraps(view)
    def login_checked_view(*args, **kwargs):
        if not current_user():
            flash("Silakan login terlebih dahulu.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return login_checked_view


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def role_checked_view(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Silakan login terlebih dahulu.", "error")
                return redirect(url_for("auth.login"))
            if normalize_role(user.get("role")) != required_role:
                return redirect_for_role()
            return view(*args, **kwargs)

        return role_checked_view

    return decorator


owner_required = role_required("owner")
cashier_required = role_required(CASHIER_ROLE)
staff_required = cashier_required
