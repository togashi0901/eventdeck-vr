import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    form_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("form_items.id", ondelete="CASCADE")
    )
    answer_text: Mapped[str | None]
    # none_as_null: CHECK (answer_text IS NOT NULL OR answer_json IS NOT NULL) を
    # JSON 'null' が誤って満たさないよう SQL NULL で保存する
    answer_json: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
