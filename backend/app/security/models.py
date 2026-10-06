from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitBucket(Base):
    """Backing store for ``app.security.rate_limit``. Keys hold HMAC fingerprints only."""

    __tablename__ = "rate_limit_buckets"

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    window_started_at: Mapped[datetime]
    hits: Mapped[int]
