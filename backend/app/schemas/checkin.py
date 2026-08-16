from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CheckinMethod = Literal["code", "qr", "manual"]


class CheckinCreateRequest(BaseModel):
    """`application_id` または `short_code` のどちらかで照合する (§2.8)。"""

    application_id: str | None = None
    short_code: str | None = Field(default=None, min_length=8, max_length=8)
    method: CheckinMethod = "code"

    @model_validator(mode="after")
    def exactly_one(self) -> "CheckinCreateRequest":
        if (self.application_id is None) == (self.short_code is None):
            raise ValueError("application_id か short_code のどちらか一方を指定してください")
        return self


class CheckinItem(BaseModel):
    id: str
    application_id: str
    short_code: str
    display_name: str | None
    vrchat_username: str | None
    method: str
    operator_email: str | None
    checked_in_at: datetime


class CheckinListResponse(BaseModel):
    items: list[CheckinItem]
    won_count: int
    checkin_count: int
    checkin_rate: float
    """参加率 = checkins数 / won数 (01_DB設計書 §5)。won 0件のときは 0.0。"""
