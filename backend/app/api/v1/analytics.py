import uuid

from fastapi import APIRouter

from app.core.authz import require_event_member, require_org_member
from app.core.deps import CurrentUser, DbSession
from app.schemas.analytics import EventAnalyticsResponse, OrgAnalyticsSummaryResponse
from app.services import analytics as analytics_service

router = APIRouter(tags=["analytics"])


@router.get("/events/{event_id}/analytics")
async def event_analytics(
    event_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> EventAnalyticsResponse:
    event = await require_event_member(db, event_id, user)
    return await analytics_service.event_analytics(db, event)


@router.get("/orgs/{org_id}/analytics/summary")
async def org_summary(
    org_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> OrgAnalyticsSummaryResponse:
    org = await require_org_member(db, org_id, user)
    return await analytics_service.org_summary(db, org)
