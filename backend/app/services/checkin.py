"""入場管理サービス (03_API仕様書 §2.8)。"""
import uuid

from sqlalchemy import String, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND, get_membership
from app.core.errors import ApiError
from app.models import Application, Checkin, Event, User, UserProfile
from app.schemas.checkin import CheckinCreateRequest, CheckinItem, CheckinListResponse
from app.services.application import short_code as make_short_code


async def _resolve_application(
    db: AsyncSession, event: Event, req: CheckinCreateRequest
) -> Application:
    if req.application_id is not None:
        try:
            app_id = uuid.UUID(req.application_id)
        except ValueError as exc:
            raise ApiError(400, "validation_error", "application_id が不正です") from exc
        app = await db.get(Application, app_id)
    else:
        code = req.short_code.lower()
        app = await db.scalar(
            select(Application).where(
                Application.event_id == event.id,
                cast(Application.id, String).like(f"{code}%"),
            )
        )
    if app is None or app.event_id != event.id:
        raise NOT_FOUND
    return app


async def create_checkin(
    db: AsyncSession, event: Event, operator: User, req: CheckinCreateRequest
) -> CheckinItem:
    app = await _resolve_application(db, event, req)

    if app.status != "won":
        raise ApiError(409, "precondition_failed", "当選 (won) の応募のみ入場できます")
    existing = await db.scalar(select(Checkin).where(Checkin.application_id == app.id))
    if existing is not None:
        raise ApiError(409, "already_checked_in", "すでに入場済みです")

    checkin = Checkin(
        event_id=event.id,
        application_id=app.id,
        method=req.method,
        operator_id=operator.id,
    )
    db.add(checkin)
    try:
        await db.commit()
    except IntegrityError as exc:  # 同時照合の競合 (UNIQUE application_id)
        await db.rollback()
        raise ApiError(409, "already_checked_in", "すでに入場済みです") from exc
    await db.refresh(checkin)

    profile = await db.get(UserProfile, app.user_id)
    return CheckinItem(
        id=str(checkin.id),
        application_id=str(app.id),
        short_code=make_short_code(app.id),
        display_name=profile.display_name if profile else None,
        vrchat_username=profile.vrchat_username if profile else None,
        method=checkin.method,
        operator_email=operator.email,
        checked_in_at=checkin.checked_in_at,
    )


async def list_checkins(db: AsyncSession, event: Event) -> CheckinListResponse:
    rows = (
        await db.execute(
            select(Checkin, Application, UserProfile, User.email)
            .join(Application, Application.id == Checkin.application_id)
            .outerjoin(UserProfile, UserProfile.user_id == Application.user_id)
            .outerjoin(User, User.id == Checkin.operator_id)
            .where(Checkin.event_id == event.id)
            .order_by(Checkin.checked_in_at.desc())
        )
    ).all()
    won_count = await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.event_id == event.id, Application.status == "won")
    )
    checkin_count = len(rows)
    return CheckinListResponse(
        items=[
            CheckinItem(
                id=str(c.id),
                application_id=str(app.id),
                short_code=make_short_code(app.id),
                display_name=profile.display_name if profile else None,
                vrchat_username=profile.vrchat_username if profile else None,
                method=c.method,
                operator_email=operator_email,
                checked_in_at=c.checked_in_at,
            )
            for c, app, profile, operator_email in rows
        ],
        won_count=won_count,
        checkin_count=checkin_count,
        checkin_rate=round(checkin_count / won_count, 4) if won_count else 0.0,
    )


async def delete_checkin(db: AsyncSession, checkin_id: uuid.UUID, user: User) -> None:
    """誤操作の取り消し (§2.8)。対象イベントの member のみ。"""
    checkin = await db.get(Checkin, checkin_id)
    if checkin is None:
        raise NOT_FOUND
    event = await db.get(Event, checkin.event_id)
    if event is None or await get_membership(db, event.organization_id, user) is None:
        raise NOT_FOUND
    await db.delete(checkin)
    await db.commit()
