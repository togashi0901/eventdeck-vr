from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BroadcastType = Literal["reminder", "announcement"]
BroadcastTarget = Literal["won", "all_applicants"]
Channel = Literal["in_app", "email", "push"]


class BroadcastRequest(BaseModel):
    """主催者からの一斉配信 (§2.9)。"""

    type: BroadcastType
    target: BroadcastTarget
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    channels: list[Channel] = Field(min_length=1)


class BroadcastResponse(BaseModel):
    queued: int


class NotificationItem(BaseModel):
    id: str
    event_id: str | None
    type: str
    channel: str
    title: str
    body: str
    status: str
    read_at: datetime | None
    created_at: datetime


class NotificationSummaryRow(BaseModel):
    type: str
    channel: str
    status: str
    count: int


class NotificationHistoryResponse(BaseModel):
    summary: list[NotificationSummaryRow]
    items: list[NotificationItem]


class PushSubscribeRequest(BaseModel):
    fcm_token: str = Field(min_length=1, max_length=512)
    user_agent: str | None = Field(default=None, max_length=300)
