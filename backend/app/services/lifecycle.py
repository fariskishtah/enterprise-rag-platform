from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def demo_expiry(retention_hours: int) -> datetime | None:
    if retention_hours <= 0:
        return None
    return datetime.now(UTC) + timedelta(hours=retention_hours)


def mark_accessed(value: Any) -> None:
    now = datetime.now(UTC)
    previous_access = value.last_accessed_at
    expires_at = value.expires_at
    if previous_access.tzinfo is None:
        now = now.replace(tzinfo=None)
    value.last_accessed_at = now
    if expires_at is not None:
        retention = expires_at - previous_access
        if retention.total_seconds() > 0:
            value.expires_at = now + retention
