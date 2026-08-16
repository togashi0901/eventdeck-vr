from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.event import EventResponse

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$"

Role = Literal["owner", "member"]


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(pattern=SLUG_PATTERN)
    description: str | None = None


class OrganizationUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    website_url: str | None = Field(default=None, max_length=500)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    website_url: str | None
    plan: str
    created_at: datetime


class PublicOrganizationResponse(BaseModel):
    """団体公開ページ (名前・説明・公開中イベント一覧)。"""

    name: str
    slug: str
    description: str | None
    website_url: str | None
    events: list[EventResponse]


class MemberResponse(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    role: Role
    joined_at: datetime


class MemberAddRequest(BaseModel):
    email: EmailStr
    role: Role = "member"
