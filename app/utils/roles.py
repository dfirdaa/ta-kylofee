CASHIER_ROLE = "staff"
CASHIER_ROLE_ALIASES = ("staff", "kasir", "cashier")


def normalize_role(role):
    value = str(role or "").strip().lower()
    return CASHIER_ROLE if value in CASHIER_ROLE_ALIASES else value


def role_label(role):
    role = normalize_role(role)
    return "Owner" if role == "owner" else "Kasir" if role == CASHIER_ROLE else "Pengguna"

