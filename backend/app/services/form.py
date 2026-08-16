"""応募フォーム設問サービス (03_API仕様書 §2.5)。"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND, get_membership
from app.core.errors import ApiError
from app.models import Application, Event, FormItem, User, UserProfile
from app.schemas.form import FormItemIn, FormItemOut, FormResponse


def _to_out(item: FormItem) -> FormItemOut:
    return FormItemOut(
        id=str(item.id),
        label=item.label,
        help_text=item.help_text,
        item_type=item.item_type,
        options=item.options,
        is_required=item.is_required,
        autofill_key=item.autofill_key,
        sort_order=item.sort_order,
    )


async def ensure_event_visible(db: AsyncSession, event: Event | None, user: User | None) -> Event:
    """published は誰でも、それ以外は member のみ (非該当は404)。"""
    if event is None:
        raise NOT_FOUND
    if event.status != "published":
        if user is None or await get_membership(db, event.organization_id, user) is None:
            raise NOT_FOUND
    return event


async def load_items(db: AsyncSession, event_id: uuid.UUID) -> list[FormItem]:
    return list(
        await db.scalars(
            select(FormItem)
            .where(FormItem.event_id == event_id)
            .order_by(FormItem.sort_order, FormItem.created_at)
        )
    )


async def get_form(db: AsyncSession, event_id: uuid.UUID, user: User | None) -> FormResponse:
    event = await ensure_event_visible(db, await db.get(Event, event_id), user)
    items = await load_items(db, event.id)

    prefill: dict[str, str] | None = None
    if user is not None:
        profile = await db.get(UserProfile, user.id)
        if profile is not None:
            prefill = {}
            for item in items:
                if item.autofill_key is None:
                    continue
                value = getattr(profile, item.autofill_key, None)
                if value:
                    prefill[str(item.id)] = value
    return FormResponse(items=[_to_out(i) for i in items], prefill=prefill)


async def replace_form(
    db: AsyncSession, event: Event, items_in: list[FormItemIn]
) -> FormResponse:
    """設問の全置換 (§2.5)。

    応募が1件以上あるイベントでは、既存設問の削除・item_type変更・
    is_required の false→true 変更を禁止 (409 form_locked)。
    ラベル修正・help_text/options/並び順の変更・設問追加は可。
    """
    existing = {str(i.id): i for i in await load_items(db, event.id)}
    incoming_ids = [i.id for i in items_in if i.id is not None]

    for item_id in incoming_ids:
        if item_id not in existing:
            raise ApiError(400, "validation_error", f"設問 {item_id} はこのイベントにありません")
    if len(set(incoming_ids)) != len(incoming_ids):
        raise ApiError(400, "validation_error", "同じ設問idを複数回指定しています")

    has_applications = (
        await db.scalar(
            select(func.count()).select_from(Application).where(Application.event_id == event.id)
        )
    ) > 0

    if has_applications:
        deleted = set(existing) - set(incoming_ids)
        if deleted:
            raise ApiError(409, "form_locked", "応募があるため既存設問は削除できません")
        for data in items_in:
            if data.id is None:
                continue
            current = existing[data.id]
            if data.item_type != current.item_type:
                raise ApiError(409, "form_locked", "応募があるため設問の種類は変更できません")
            if data.is_required and not current.is_required:
                raise ApiError(409, "form_locked", "応募があるため必須への変更はできません")

    # 全置換: id ありは更新、なしは追加、リストに無い既存は削除 (応募なしの場合のみ到達)
    for missing_id in set(existing) - set(incoming_ids):
        await db.delete(existing[missing_id])
    for idx, data in enumerate(items_in):
        if data.id is not None:
            item = existing[data.id]
        else:
            item = FormItem(event_id=event.id)
            db.add(item)
        item.label = data.label
        item.help_text = data.help_text
        item.item_type = data.item_type
        item.options = data.options
        item.is_required = data.is_required
        item.autofill_key = data.autofill_key
        item.sort_order = idx
    await db.commit()

    return FormResponse(items=[_to_out(i) for i in await load_items(db, event.id)])
