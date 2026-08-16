from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.schemas.common import PageMeta

EventPlatform = Literal["vrchat", "cluster", "resonite", "real", "other"]
SelectionMethod = Literal["lottery", "first_come"]
Visibility = Literal["public", "unlisted"]


class EventUpsertRequest(BaseModel):
    """作成・更新共通 (PUT は全置換)。日時は timezone-aware 必須。"""

    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    platform: EventPlatform = "vrchat"
    world_name: str | None = Field(default=None, max_length=100)
    world_url: str | None = Field(default=None, max_length=500)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    capacity: int = Field(gt=0)
    selection_method: SelectionMethod = "lottery"
    apply_starts_at: AwareDatetime
    apply_ends_at: AwareDatetime
    visibility: Visibility = "public"
    header_image_url: str | None = Field(default=None, max_length=500)


class EventOrganization(BaseModel):
    id: str
    name: str
    slug: str


class ApplicationState(BaseModel):
    applied: bool
    status: str | None


class EventResponse(BaseModel):
    id: str
    organization: EventOrganization
    title: str
    description: str
    platform: str
    world_name: str | None
    world_url: str | None
    starts_at: datetime
    ends_at: datetime
    capacity: int
    selection_method: str
    apply_starts_at: datetime
    apply_ends_at: datetime
    status: str
    visibility: str
    header_image_url: str | None
    application_state: ApplicationState | None = None
    """ログイン済みユーザーにのみ含める (§3)。"""


class EventListResponse(BaseModel):
    items: list[EventResponse]
    meta: PageMeta
