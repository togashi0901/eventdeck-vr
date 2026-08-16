from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PageMeta

QuotaFilter = Literal["all", "first_timer", "repeater"]


class QuotaIn(BaseModel):
    """抽選枠 (02_抽選仕様書 §2)。count=null は残枠吸収の一般枠 (最後に1つだけ)。"""

    name: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=100)
    count: int | None = Field(default=None, ge=1)
    filter: QuotaFilter = "all"


def default_quotas() -> list[QuotaIn]:
    return [QuotaIn(name="general", label="一般枠", count=None, filter="all")]


class LotteryRequest(BaseModel):
    """preview / 実行の共通ボディ (§2.7)。"""

    quotas: list[QuotaIn] = Field(default_factory=default_quotas, min_length=1)
    waitlist_count: int = Field(default=0, ge=0)


class PreviewResponse(BaseModel):
    target_count: int
    remaining_capacity: int
    quota_matches: dict[str, int]


class ExecuteResponse(BaseModel):
    lottery_id: str
    round: int
    won: int
    waitlisted: int
    lost: int
    executed_at: datetime


class LotteryHistoryItem(BaseModel):
    id: str
    round: int
    executed_by_email: str
    algorithm_version: str
    winner_quota: int
    waitlist_quota: int
    config: dict
    executed_at: datetime


class LotteryResultItem(BaseModel):
    application_id: str
    display_name: str | None
    result: str
    draw_rank: int
    quota_name: str
    current_status: str
    """応募の現在status (キャンセル・繰り上げ後の状態確認用)。"""


class LotteryResultsResponse(BaseModel):
    items: list[LotteryResultItem]
    meta: PageMeta
