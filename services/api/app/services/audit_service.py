"""
Thin wrapper for writing audit log entries. Never pass secrets
(passwords, raw tokens) into `metadata`.
"""
import uuid
from typing import Optional

from flask import request

from app.extensions import db
from app.models import AuditLog


class AuditService:
    def log(
        self,
        *,
        event_type: str,
        user_id: Optional[uuid.UUID] = None,
        institute_id: Optional[uuid.UUID] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        entry = AuditLog(
            event_type=event_type,
            user_id=user_id,
            institute_id=institute_id,
            metadata_json=metadata or {},
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
        )
        db.session.add(entry)
        db.session.flush()
