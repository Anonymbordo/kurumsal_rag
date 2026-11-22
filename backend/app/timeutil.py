from datetime import UTC, datetime


def utcnow() -> datetime:
    """Saat dilimi bilgisi olmayan UTC zaman (veritabanında bu biçimde tutulur)."""
    return datetime.now(UTC).replace(tzinfo=None)
