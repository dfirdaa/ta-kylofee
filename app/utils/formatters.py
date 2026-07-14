from datetime import datetime


def format_currency(amount):
    return f"Rp{int(amount or 0):,}".replace(",", ".")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def format_short_date(value):
    if not value:
        return "-"
    if not hasattr(value, "month"):
        value = parse_date(value)
    if not value:
        return "-"
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{value.day} {months[value.month - 1]} {value.year}"

