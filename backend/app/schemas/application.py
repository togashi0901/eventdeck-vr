from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AnswerIn(BaseModel):
    form_item_id: str
    value: str | None = None
    """text/textarea/select/radio/number の回答。"""
    values: list[str] | None = None
    """checkbox (複数選択) の回答。"""

    @model_validator(mode="after")
    def one_of(self) -> "AnswerIn":
        if self.value is not None and self.values is not None:
            raise ValueError("value と values は同時に指定できません")
        return self


class ApplicationCreateRequest(BaseModel):
    answers: list[AnswerIn] = Field(default_factory=list)


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class AnswerOut(BaseModel):
    form_item_id: str
    label: str
    item_type: str
    value: str | None
    values: list[str] | None


class ApplicationResponse(BaseModel):
    id: str
    event_id: str
    status: str
    promoted: bool
    applied_at: datetime
    canceled_at: datetime | None
    answers: list[AnswerOut] = Field(default_factory=list)


class ApplicantItem(BaseModel):
    """応募者一覧 (主催者向け §2.6)。"""

    id: str
    status: str
    promoted: bool
    applied_at: datetime
    display_name: str | None
    vrchat_username: str | None
    answers: list[AnswerOut]


class EventBrief(BaseModel):
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    status: str
    selection_method: str
    organization_name: str


class MyApplicationItem(BaseModel):
    """マイページの応募一覧 (§2.2)。"""

    id: str
    status: str
    promoted: bool
    applied_at: datetime
    event: EventBrief
    short_code: str
    """入場コード = application_id の先頭8桁 (§2.6)。"""


class EntryCodeResponse(BaseModel):
    application_id: str
    short_code: str
