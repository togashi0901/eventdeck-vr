import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FormItem(Base):
    __tablename__ = "form_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    label: Mapped[str]
    help_text: Mapped[str | None]
    item_type: Mapped[str]
    # none_as_null: Python None を JSON 'null' でなく SQL NULL として保存する
    # (CHECK制約 (選択式) = (options IS NOT NULL) を満たすため)
    options: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    is_required: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    autofill_key: Mapped[str | None]
    sort_order: Mapped[int] = mapped_column(server_default=text("0"), default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
