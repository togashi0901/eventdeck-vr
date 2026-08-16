import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str]
    description: Mapped[str] = mapped_column(server_default=text("''"), default="")
    platform: Mapped[str] = mapped_column(server_default=text("'vrchat'"), default="vrchat")
    world_name: Mapped[str | None]
    world_url: Mapped[str | None]
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    capacity: Mapped[int]
    selection_method: Mapped[str] = mapped_column(
        server_default=text("'lottery'"), default="lottery"
    )
    apply_starts_at: Mapped[datetime]
    apply_ends_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(server_default=text("'draft'"), default="draft")
    visibility: Mapped[str] = mapped_column(server_default=text("'public'"), default="public")
    header_image_url: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
