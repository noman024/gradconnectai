"""
Audit logging: who did what, when. Store in audit_log table or append to log.
"""
from __future__ import annotations

from typing import Any

# In-memory audit trail when DB not used; replace with DB insert in production
_audit_entries: list[dict[str, Any]] = []


def log_audit(
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    entry = {
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
    }
    _audit_entries.append(entry)
    # In production: insert into audit_log table with created_at


def get_recent_audit(limit: int = 100) -> list[dict[str, Any]]:
    return list(reversed(_audit_entries[-limit:]))
