import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Checkin(Base):
    """当日の入場記録。API は M5 で実装 (M4 では抽選 filter 評価で参照のみ)。"""

    __tablename__ = "checkins"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    method: Mapped[str] = mapped_column(server_default=text("'code'"), default="code")
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    checked_in_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
