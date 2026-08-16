"""分析サービス (03_API仕様書 §2.10)。

集計の定義:
- checkin_rate = checkins数 / won数 (01_DB設計書 §5)
- first_timer_rate = 応募ユーザー (キャンセル除く・ユニーク) のうち、同一団体の
  過去イベントで入場実績のないユーザーの割合 (02_抽選仕様書 §2 の first_timer 定義を流用)
- repeat_rate = 団体イベントに2回以上入場したユニークユーザー ÷ 1回以上入場したユニークユーザー
- daily_applications は JST の日付で集計する (表示側がJSTのため)
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, Checkin, Event, Organization
from app.schemas.analytics import (
    DailyApplications,
    EventAnalyticsResponse,
    OrgAnalyticsSummaryResponse,
    OrgEventAnalyticsRow,
)
from app.services.lottery import repeater_user_ids

JST = "Asia/Tokyo"


async def event_analytics(db: AsyncSession, event: Event) -> EventAnalyticsResponse:
    status_rows = (
        await db.execute(
            select(Application.status, func.count())
            .where(Application.event_id == event.id)
            .group_by(Application.status)
        )
    ).all()
    by_status = dict(status_rows)
    applications_total = sum(by_status.values())
    won_count = by_status.get("won", 0)

    checkin_count = await db.scalar(
        select(func.count()).select_from(Checkin).where(Checkin.event_id == event.id)
    )

    applicant_ids = list(
        await db.scalars(
            select(Application.user_id)
            .where(Application.event_id == event.id, Application.status != "canceled")
            .distinct()
        )
    )
    repeaters = await repeater_user_ids(db, event, applicant_ids)
    first_timers = len(applicant_ids) - len(repeaters)

    jst_date = func.date(func.timezone(JST, Application.applied_at))
    daily_rows = (
        await db.execute(
            select(jst_date.label("d"), func.count())
            .where(Application.event_id == event.id)
            .group_by("d")
            .order_by("d")
        )
    ).all()

    return EventAnalyticsResponse(
        applications_total=applications_total,
        by_status=by_status,
        checkin_rate=round(checkin_count / won_count, 4) if won_count else 0.0,
        first_timer_rate=(
            round(first_timers / len(applicant_ids), 4) if applicant_ids else 0.0
        ),
        daily_applications=[DailyApplications(date=d, count=c) for d, c in daily_rows],
    )


async def org_summary(db: AsyncSession, org: Organization) -> OrgAnalyticsSummaryResponse:
    events = (
        await db.scalars(
            select(Event).where(Event.organization_id == org.id).order_by(Event.starts_at)
        )
    ).all()
    event_ids = [e.id for e in events]

    app_rows: dict = {}
    checkin_counts: dict = {}
    if event_ids:
        app_rows = {
            (event_id, status): count
            for event_id, status, count in (
                await db.execute(
                    select(Application.event_id, Application.status, func.count())
                    .where(Application.event_id.in_(event_ids))
                    .group_by(Application.event_id, Application.status)
                )
            ).all()
        }
        checkin_counts = dict(
            (
                await db.execute(
                    select(Checkin.event_id, func.count())
                    .where(Checkin.event_id.in_(event_ids))
                    .group_by(Checkin.event_id)
                )
            ).all()
        )

    rows = []
    for e in events:
        total = sum(count for (eid, _), count in app_rows.items() if eid == e.id)
        won = app_rows.get((e.id, "won"), 0)
        checkins = checkin_counts.get(e.id, 0)
        rows.append(
            OrgEventAnalyticsRow(
                event_id=str(e.id),
                title=e.title,
                starts_at=e.starts_at,
                status=e.status,
                applications_total=total,
                won_count=won,
                checkin_count=checkins,
                checkin_rate=round(checkins / won, 4) if won else 0.0,
            )
        )

    # リピート率: 入場回数をユーザー単位で数える
    unique_attendees = 0
    repeat_attendees = 0
    if event_ids:
        per_user = (
            select(Application.user_id, func.count().label("visits"))
            .join(Checkin, Checkin.application_id == Application.id)
            .where(Checkin.event_id.in_(event_ids))
            .group_by(Application.user_id)
        ).subquery()
        unique_attendees = await db.scalar(select(func.count()).select_from(per_user)) or 0
        repeat_attendees = (
            await db.scalar(
                select(func.count()).select_from(per_user).where(per_user.c.visits >= 2)
            )
            or 0
        )

    return OrgAnalyticsSummaryResponse(
        events=rows,
        unique_attendees=unique_attendees,
        repeat_attendees=repeat_attendees,
        repeat_rate=(
            round(repeat_attendees / unique_attendees, 4) if unique_attendees else 0.0
        ),
    )
