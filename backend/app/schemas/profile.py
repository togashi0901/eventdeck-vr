from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["pcvr", "desktop", "quest_standalone", "mobile", "unknown"]


class ProfileUpsertRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=50)
    vrchat_username: str | None = Field(default=None, max_length=64)
    platform: Platform = "unknown"
    device_note: str | None = Field(default=None, max_length=200)
    x_account: str | None = Field(default=None, max_length=50)
    discord_account: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=500)


class ProfileResponse(BaseModel):
    display_name: str
    vrchat_username: str | None
    platform: str
    device_note: str | None
    x_account: str | None
    discord_account: str | None
    bio: str | None
