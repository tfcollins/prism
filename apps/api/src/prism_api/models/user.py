"""User model."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Nullable: directory (LDAP) users have no local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "local" (bcrypt password) or "ldap" (authenticated against the directory).
    auth_provider: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="local", default="local"
    )
