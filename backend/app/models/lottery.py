import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Lottery(Base):
    """抽選の実行記録 (公平性の証跡)。**追記専用: UPDATE/DELETE を書かない** (不変条件1)。"""

    __tablename__ = "lotteries"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    round: Mapped[int] = mapped_column(server_default=text("1"))
    executed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    seed: Mapped[int] = mapped_column(BigInteger)  # 63bit シード (schema.sql: bigint)
    algorithm_version: Mapped[str] = mapped_column(server_default=text("'v1'"), default="v1")
    winner_quota: Mapped[int]
    waitlist_quota: Mapped[int] = mapped_column(server_default=text("0"), default=0)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    executed_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
