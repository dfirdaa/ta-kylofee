from datetime import date, timedelta

from app.database import fetch_all, fetch_one
from app.utils.formatters import format_currency, format_short_date, parse_date
from app.utils.timezone import jakarta_now_naive, jakarta_today, transaction_datetime_jakarta


COMPLETED_STATUSES = "('selesai', 'paid', 'completed', 'complete')"


def resolve_report_period(args):
    today = jakarta_today()
    start = parse_date(args.get("date_from")) or today.replace(day=1)
    end = parse_date(args.get("date_to")) or today
    return (end, start) if start > end else (start, end)


def format_period(start, end):
    return format_short_date(start) if start == end else f"{format_short_date(start)} - {format_short_date(end)}"


def get_period_totals(start, end):
    row = fetch_one(
        f"""
        SELECT COALESCE(SUM(t.total_amount), 0) AS revenue, COUNT(*) AS transactions
        FROM pos_transactions t
        WHERE t.transaction_date BETWEEN %s AND %s
          AND LOWER(t.status) IN {COMPLETED_STATUSES}
        """,
        (start, end),
    ) or {"revenue": 0, "transactions": 0}
    revenue = int(row.get("revenue") or 0)
    return {"revenue": revenue, "profit": revenue, "transactions": int(row.get("transactions") or 0)}


def trend_text(current, previous, empty="Belum ada transaksi"):
    current, previous = int(current or 0), int(previous or 0)
    if previous == 0:
        return empty if current == 0 else "Baru ada transaksi"
    percentage = ((current - previous) / previous) * 100
    return f"{'+' if percentage >= 0 else '-'}{abs(percentage):.1f}% dari periode lalu"


def trend_tone(current, previous):
    if int(current or 0) == int(previous or 0) or int(previous or 0) == 0:
        return "neutral"
    return "positive" if current > previous else "negative"


def fetch_daily_details(start, end):
    rows = fetch_all(
        f"""
        SELECT t.transaction_date, COUNT(*) AS transactions, COALESCE(SUM(t.total_amount), 0) AS income
        FROM pos_transactions t
        WHERE t.transaction_date BETWEEN %s AND %s
          AND LOWER(t.status) IN {COMPLETED_STATUSES}
        GROUP BY t.transaction_date
        ORDER BY t.transaction_date DESC
        """,
        (start, end),
    )
    return [
        {
            "date": format_short_date(row["transaction_date"]),
            "transactions": int(row.get("transactions") or 0),
            "income": format_currency(row.get("income")),
            "profit": format_currency(row.get("income")),
        }
        for row in rows
    ]


def fetch_recent_transactions(start, end, limit=5):
    rows = fetch_all(
        f"""
        SELECT t.order_code, t.transaction_date, t.transaction_time, t.customer_name,
               t.payment_method, t.total_amount, t.item_count, t.status, t.created_at,
               u.full_name AS staff_name
        FROM pos_transactions t
        LEFT JOIN users u ON u.id = t.staff_id
        WHERE t.transaction_date BETWEEN %s AND %s
          AND LOWER(t.status) IN {COMPLETED_STATUSES}
        ORDER BY t.transaction_date DESC, t.transaction_time DESC, t.id DESC
        LIMIT %s
        """,
        (start, end, limit),
    )
    result = []
    for row in rows:
        local_datetime = transaction_datetime_jakarta(
            row.get("transaction_date"),
            row.get("transaction_time"),
            row.get("created_at"),
        )
        result.append(
            {
                "id": row.get("order_code") or "-",
                "date": format_short_date(
                    local_datetime.date() if local_datetime else row.get("transaction_date")
                ),
                "time": (
                    local_datetime.strftime("%H:%M")
                    if local_datetime
                    else str(row.get("transaction_time") or "")[:5] or "-"
                ),
                "customer": row.get("customer_name") or "Walk-in Customer",
                "method": row.get("payment_method") or "Tunai",
                "staff": row.get("staff_name") or "-",
                "total": format_currency(row.get("total_amount")),
                "items": int(row.get("item_count") or 0),
                "status": str(row.get("status") or "Selesai").title(),
            }
        )
    return result


def fetch_hourly_sales(start, end):
    rows = fetch_all(
        f"""
        SELECT t.transaction_date, t.transaction_time, t.created_at, t.total_amount
        FROM pos_transactions t
        WHERE t.transaction_date BETWEEN %s AND %s
          AND LOWER(t.status) IN {COMPLETED_STATUSES}
        """,
        (start, end),
    )
    values = {hour: 0 for hour in range(8, 23)}
    for row in rows:
        local_datetime = transaction_datetime_jakarta(
            row.get("transaction_date"),
            row.get("transaction_time"),
            row.get("created_at"),
        )
        if not local_datetime:
            continue
        hour = local_datetime.hour
        if hour in values:
            values[hour] += int(row.get("total_amount") or 0)
    peak = max(values.values()) if values else 0
    return [
        {
            "hour": f"{hour:02d}:00",
            "amount": format_currency(amount),
            "height": int((amount / peak) * 100) if peak else 0,
            "has_value": amount > 0,
            "is_peak": peak > 0 and amount == peak,
            "label_visible": hour % 2 == 0,
        }
        for hour, amount in values.items()
    ]


def shift_month(source, delta):
    index = source.month - 1 + delta
    return date(source.year + index // 12, index % 12 + 1, 1)


def build_monthly_summary(end):
    months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    current = end.replace(day=1)
    rows = []
    for delta in (-2, -1, 0):
        start = shift_month(current, delta)
        month_end = shift_month(start, 1) - timedelta(days=1)
        result = get_period_totals(start, month_end)
        rows.append(
            {
                "month": f"{months[start.month - 1]} {start.year}",
                "income": format_currency(result["revenue"]),
                "profit": format_currency(result["profit"]),
                "is_current": delta == 0,
            }
        )
    return rows


def build_financial_report(args):
    start, end = resolve_report_period(args)
    now = jakarta_now_naive()
    current = get_period_totals(start, end)
    days = max((end - start).days + 1, 1)
    previous_end = start - timedelta(days=1)
    previous = get_period_totals(previous_end - timedelta(days=days - 1), previous_end)
    local_today = jakarta_today()
    today = get_period_totals(local_today, local_today)
    average = current["revenue"] // days
    previous_average = previous["revenue"] // days
    period = format_period(start, end)
    details = fetch_daily_details(start, end)
    recent = fetch_recent_transactions(start, end, 5)
    metrics = [
        ("Total Pendapatan", current["revenue"], previous["revenue"]),
        ("Laba Bersih", current["profit"], previous["profit"]),
        ("Total Transaksi", current["transactions"], previous["transactions"]),
    ]
    dashboard = [
        {
            "label": label,
            "value": str(value) if label == "Total Transaksi" else format_currency(value),
            "trend": trend_text(value, old),
            "tone": trend_tone(value, old),
        }
        for label, value, old in metrics
    ]
    dashboard.extend(
        [
            {"label": "Pendapatan Hari Ini", "value": format_currency(today["revenue"]), "trend": "Dari transaksi tanggal ini", "tone": "neutral"},
            {"label": "Rata-rata Pendapatan Harian", "value": format_currency(average), "trend": trend_text(average, previous_average), "tone": trend_tone(average, previous_average)},
        ]
    )
    return {
        "period": period,
        "calendar_label": period,
        "printed_at": f"{format_short_date(now.date())} {now:%H:%M} WIB",
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "has_data": current["transactions"] > 0,
        "dashboard_metrics": dashboard,
        "print_summary": [
            {"label": "Total Pendapatan (Revenue)", "value": format_currency(current["revenue"]), "tone": "normal"},
            {"label": "Laba Bersih", "value": format_currency(current["profit"]), "tone": "success"},
            {"label": "Total Transaksi", "value": str(current["transactions"]), "tone": "normal"},
            {"label": "Rata-rata Pendapatan Harian", "value": format_currency(average), "tone": "normal"},
        ],
        "net_profit": format_currency(current["profit"]),
        "net_profit_trend": trend_text(current["profit"], previous["profit"], "Belum ada data periode lalu"),
        "hourly_sales": fetch_hourly_sales(start, end),
        "daily_details": details,
        "daily_totals": {"transactions": str(current["transactions"]), "income": format_currency(current["revenue"]), "profit": format_currency(current["profit"])},
        "recent_transactions": recent,
        "print_transactions": fetch_recent_transactions(start, end, 20),
        "monthly_summary": build_monthly_summary(end),
        "daily_income_rows": details[:6],
    }
