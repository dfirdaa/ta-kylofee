from datetime import datetime, time, timedelta, timezone


JAKARTA_TIMEZONE = timezone(timedelta(hours=7), name="WIB")


def jakarta_now():
    return datetime.now(JAKARTA_TIMEZONE)


def jakarta_now_naive():
    return jakarta_now().replace(tzinfo=None)


def jakarta_today():
    return jakarta_now().date()


def _parse_time(value):
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return time(hours, minutes, seconds)

    text = str(value or "").strip()
    for pattern, length in (("%H:%M:%S", 8), ("%H:%M", 5)):
        try:
            return datetime.strptime(text[:length], pattern).time()
        except ValueError:
            continue
    return None


def _utc_naive(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def transaction_datetime_jakarta(transaction_date, transaction_time, created_at=None):
    """Return WIB time and transparently repair legacy Vercel UTC transactions."""
    parsed_time = _parse_time(transaction_time)
    if not transaction_date or not parsed_time:
        return None
    if isinstance(transaction_date, datetime):
        transaction_date = transaction_date.date()
    elif not hasattr(transaction_date, "year"):
        try:
            transaction_date = datetime.strptime(str(transaction_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    stored = datetime.combine(transaction_date, parsed_time)
    created_utc = _utc_naive(created_at)
    if created_utc is None:
        return stored

    created_jakarta = (
        created_utc.replace(tzinfo=timezone.utc)
        .astimezone(JAKARTA_TIMEZONE)
        .replace(tzinfo=None)
    )
    utc_gap = abs((stored - created_utc).total_seconds())
    jakarta_gap = abs((stored - created_jakarta).total_seconds())

    if utc_gap < jakarta_gap:
        return (
            stored.replace(tzinfo=timezone.utc)
            .astimezone(JAKARTA_TIMEZONE)
            .replace(tzinfo=None)
        )
    return stored
