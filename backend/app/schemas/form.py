from typing import Literal

from pydantic import BaseModel, Field, model_validator

ItemType = Literal["text", "textarea", "select", "radio", "checkbox", "number"]
AutofillKey = Literal[
    "display_name",
    "vrchat_username",
    "platform",
    "device_note",
    "x_account",
    "discord_account",
]

CHOICE_TYPES = ("select", "radio", "checkbox")


class FormItemIn(BaseModel):
    id: str | None = None
    """既存設問の更新時はid必須。新規追加はid無し。"""
    label: str = Field(min_length=1, max_length=200)
    help_text: str | None = Field(default=None, max_length=500)
    item_type: ItemType
    options: list[str] | None = None
    is_required: bool = False
    autofill_key: AutofillKey | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "FormItemIn":
        """select/radio/checkbox のときだけ options 必須 (DB CHECKと同じ両方向制約)。"""
        needs_options = self.item_type in CHOICE_TYPES
        if needs_options and not self.options:
            raise ValueError("選択式の設問には options が必要です")
        if not needs_options and self.options is not None:
            raise ValueError("選択式でない設問に options は指定できません")
        if self.options is not None and any(not opt.strip() for opt in self.options):
            raise ValueError("options に空の選択肢は指定できません")
        return self


class FormPutRequest(BaseModel):
    items: list[FormItemIn]
    """全置換。sort_order はリストの並び順で決まる。"""


class FormItemOut(BaseModel):
    id: str
    label: str
    help_text: str | None
    item_type: str
    options: list[str] | None
    is_required: bool
    autofill_key: str | None
    sort_order: int


class FormResponse(BaseModel):
    items: list[FormItemOut]
    prefill: dict[str, str] | None = None
    """ログイン済み+プロフィール登録済みの場合のみ {form_item_id: 初期値} (§2.5)。"""
