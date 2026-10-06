"""Imports every model so ``Base.metadata`` is complete (used by Alembic and tests).

New modules register their models here.
"""

from app.db.base import Base
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import User, UserSession
from app.modules.organizations.models import Invitation, Membership, Organization
from app.security.models import RateLimitBucket

__all__ = [
    "AuditEvent",
    "Base",
    "Invitation",
    "Membership",
    "Organization",
    "RateLimitBucket",
    "User",
    "UserSession",
]
