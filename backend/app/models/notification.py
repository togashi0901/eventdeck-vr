import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Notification(Base):
    """通知の配信履歴 (アプリ内通知の実体も兼ねる)。1宛先×1チャネルで1行。"""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL")
    )
    type: Mapped[str]
    channel: Mapped[str]
    title: Mapped[str]
    body: Mapped[str]
    status: Mapped[str] = mapped_column(server_default=text("'queued'"), default="queued")
    error_detail: Mapped[str | None]
    sent_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
