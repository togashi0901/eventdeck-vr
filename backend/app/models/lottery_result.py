import uuid

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LotteryResult(Base):
    """抽選対象と結果の明細。**追記専用: UPDATE/DELETE を書かない** (不変条件1)。"""

    __tablename__ = "lottery_results"

    lottery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lotteries.id", ondelete="CASCADE"), primary_key=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    result: Mapped[str]
    draw_rank: Mapped[int]
    quota_name: Mapped[str] = mapped_column(server_default=text("'general'"), default="general")
