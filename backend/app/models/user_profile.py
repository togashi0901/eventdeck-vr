import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str]
    vrchat_username: Mapped[str | None]
    platform: Mapped[str] = mapped_column(server_default=text("'unknown'"), default="unknown")
    device_note: Mapped[str | None]
    x_account: Mapped[str | None]
    discord_account: Mapped[str | None]
    bio: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
