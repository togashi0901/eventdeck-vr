"""イベントサービス (03_API仕様書 §2.4)。"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND, get_membership
from app.core.errors import ApiError
from app.models import Application, Event, Organization, User
from app.schemas.common import PageMeta
from app.schemas.event import (
    ApplicationState,
    EventListResponse,
    EventOrganization,
    EventResponse,
    EventUpsertRequest,
)


def to_event_response(
    event: Event, org: Organization, application_state: ApplicationState | None = None
) -> EventResponse:
    return EventResponse(
        id=str(event.id),
        organization=EventOrganization(id=str(org.id), name=org.name, slug=org.slug),
        title=event.title,
        description=event.description,
        platform=event.platform,
        world_name=event.world_name,
        world_url=event.world_url,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        capacity=event.capacity,
        selection_method=event.selection_method,
        apply_starts_at=event.apply_starts_at,
        apply_ends_at=event.apply_ends_at,
        status=event.status,
        visibility=event.visibility,
        header_image_url=event.header_image_url,
        application_state=application_state,
    )


def _validate_times(data: EventUpsertRequest) -> None:
    """時系列の整合性 (01_DB設計書: apply_starts < apply_ends <= starts < ends)。"""
    problems: list[dict] = []
    if data.ends_at <= data.starts_at:
        problems.append({"field": "ends_at", "reason": "must_be_after_starts_at"})
    if data.apply_ends_at <= data.apply_starts_at:
        problems.append({"field": "apply_ends_at", "reason": "must_be_after_apply_starts_at"})
    if data.apply_ends_at > data.starts_at:
        problems.append({"field": "apply_ends_at", "reason": "must_not_be_after_starts_at"})
    if problems:
        raise ApiError(422, "unprocessable", "日時の前後関係が不正です", details=problems)


def _apply_fields(event: Event, data: EventUpsertRequest) -> None:
    for key, value in data.model_dump().items():
        setattr(event, key, value)


async def _application_state(
    db: AsyncSession, event_id: uuid.UUID, user: User | None
) -> ApplicationState | None:
    """ログイン済みユーザーの応募状況 (§3)。"""
    if user is None:
        return None
    app = await db.scalar(
        select(Application).where(
            Application.event_id == event_id, Application.user_id == user.id
        )
    )
    if app is None:
        return ApplicationState(applied=False, status=None)
    return ApplicationState(applied=True, status=app.status)


async def create_event(
    db: AsyncSession, org: Organization, user: User, data: EventUpsertRequest
) -> EventResponse:
    _validate_times(data)
    event = Event(organization_id=org.id, created_by=user.id, status="draft")
    _apply_fields(event, data)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return to_event_response(event, org)


async def update_event(
    db: AsyncSession, event: Event, data: EventUpsertRequest
) -> EventResponse:
    if event.status not in ("draft", "published"):
        raise ApiError(409, "conflict", f"{event.status} のイベントは編集できません")
    _validate_times(data)
    if event.status == "published" and data.capacity < event.capacity:
        raise ApiError(
            422,
            "unprocessable",
            "公開後は定員を減らせません",
            details=[{"field": "capacity", "reason": "cannot_decrease_after_publish"}],
        )
    _apply_fields(event, data)
    await db.commit()
    await db.refresh(event)
    org = await db.get(Organization, event.organization_id)
    return to_event_response(event, org)


async def publish_event(db: AsyncSession, event: Event) -> EventResponse:
    """draft → published。時系列が不正な場合 422 (§2.4)。

    保存済みの行はDB CHECKを常に満たすため、publish時は「現在時刻に対して
    まだ成立するか」(応募締切・終了が過去でないか) を検証する。
    """
    if event.status != "draft":
        raise ApiError(409, "precondition_failed", "下書きのイベントのみ公開できます")
    now = datetime.now(UTC)
    problems: list[dict] = []
    if event.apply_ends_at <= now:
        problems.append({"field": "apply_ends_at", "reason": "already_passed"})
    if event.ends_at <= now:
        problems.append({"field": "ends_at", "reason": "already_passed"})
    if problems:
        raise ApiError(
            422,
            "unprocessable",
            "応募締切または開催終了が過去のため公開できません",
            details=problems,
        )
    event.status = "published"
    await db.commit()
    await db.refresh(event)
    org = await db.get(Organization, event.organization_id)
    return to_event_response(event, org)


async def cancel_event(db: AsyncSession, event: Event) -> EventResponse:
    if event.status not in ("draft", "published"):
        raise ApiError(409, "precondition_failed", "このイベントは中止できません")
    event.status = "canceled"
    # 全応募者 (キャンセル済み除く) へ event_canceled 通知を積む (§2.4)
    from app.services.notification import queue_for_users  # 循環import回避

    applicant_ids = list(
        await db.scalars(
            select(Application.user_id).where(
                Application.event_id == event.id, Application.status != "canceled"
            )
        )
    )
    await queue_for_users(
        db,
        applicant_ids,
        event_id=event.id,
        type_="event_canceled",
        title=f"【{event.title}】開催中止のお知らせ",
        body=f"イベント「{event.title}」は開催中止となりました。\n",
    )
    await db.commit()
    await db.refresh(event)
    org = await db.get(Organization, event.organization_id)
    return to_event_response(event, org)


async def get_event_detail(
    db: AsyncSession, event_id: uuid.UUID, user: User | None
) -> EventResponse:
    """published は誰でも可。draft 等は member のみ (非該当は404)。"""
    event = await db.get(Event, event_id)
    if event is None:
        raise NOT_FOUND
    if event.status != "published":
        if user is None or await get_membership(db, event.organization_id, user) is None:
            raise NOT_FOUND
    org = await db.get(Organization, event.organization_id)
    state = await _application_state(db, event.id, user)
    return to_event_response(event, org, state)


async def list_public_events(
    db: AsyncSession,
    *,
    platform: str | None,
    from_: datetime | None,
    q: str | None,
    page: int,
    per_page: int,
) -> EventListResponse:
    """公開イベント一覧: status='published' かつ visibility='public' のみ (§2.4)。"""
    conditions = [Event.status == "published", Event.visibility == "public"]
    if platform:
        conditions.append(Event.platform == platform)
    if from_:
        conditions.append(Event.starts_at >= from_)
    if q:
        conditions.append(Event.title.ilike(f"%{q}%"))

    total = await db.scalar(select(func.count()).select_from(Event).where(*conditions)) or 0
    rows = (
        await db.execute(
            select(Event, Organization)
            .join(Organization, Organization.id == Event.organization_id)
            .where(*conditions)
            .order_by(Event.starts_at)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    return EventListResponse(
        items=[to_event_response(e, o) for e, o in rows],
        meta=PageMeta(page=page, per_page=per_page, total=total),
    )


async def list_org_events(
    db: AsyncSession, org: Organization, status: str | None
) -> list[EventResponse]:
    """ダッシュボード用一覧 (§2.4)。"""
    conditions = [Event.organization_id == org.id]
    if status:
        conditions.append(Event.status == status)
    events = (
        await db.scalars(select(Event).where(*conditions).order_by(Event.starts_at.desc()))
    ).all()
    return [to_event_response(e, org) for e in events]
