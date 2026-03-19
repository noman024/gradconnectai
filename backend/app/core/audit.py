"""
Audit logging: who did what, when. Store in audit_log table or append to log.
"""
from __future__ import annotations

from typing import Any

from app.db.models import AuditLog
from app.db.session import get_session
from app.core.timezone import to_dhaka


def log_audit(
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Persist an audit log entry to the audit_log table."""
    with get_session() as db:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
        db.add(entry)
        db.commit()


def get_recent_audit(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent audit entries (for admin/debug)."""
    with get_session() as db:
        rows = (
            db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(r.id),
                "user_id": r.user_id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "details": r.details,
                "created_at": to_dhaka(r.created_at).isoformat() if r.created_at else None,
            }
            for r in rows
        ]
