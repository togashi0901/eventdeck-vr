import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.authz import require_event_member, require_org_member
from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.errors import ApiError
from app.schemas.event import EventListResponse, EventResponse, EventUpsertRequest
from app.services import event as event_service

router = APIRouter(tags=["events"])


@router.get("/events")
async def list_events(
    db: DbSession,
    platform: str | None = None,
    q: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EventListResponse:
    return await event_service.list_public_events(
        db, platform=platform, from_=from_, q=q, page=page, per_page=per_page
    )


@router.get("/events/{event_id}")
async def get_event(event_id: uuid.UUID, user: OptionalUser, db: DbSession) -> EventResponse:
    return await event_service.get_event_detail(db, event_id, user)


@router.post("/orgs/{org_id}/events", status_code=201)
async def create_event(
    org_id: uuid.UUID, body: EventUpsertRequest, user: CurrentUser, db: DbSession
) -> EventResponse:
    org = await require_org_member(db, org_id, user)
    return await event_service.create_event(db, org, user, body)


@router.get("/orgs/{org_id}/events")
async def list_org_events(
    org_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    status: str | None = None,
) -> list[EventResponse]:
    org = await require_org_member(db, org_id, user)
    if status is not None and status not in (
        "draft", "published", "closed", "finished", "canceled",
    ):
        raise ApiError(400, "validation_error", "status が不正です")
    return await event_service.list_org_events(db, org, status)


@router.put("/events/{event_id}")
async def update_event(
    event_id: uuid.UUID, body: EventUpsertRequest, user: CurrentUser, db: DbSession
) -> EventResponse:
    event = await require_event_member(db, event_id, user)
    return await event_service.update_event(db, event, body)


@router.post("/events/{event_id}/publish")
async def publish_event(event_id: uuid.UUID, user: CurrentUser, db: DbSession) -> EventResponse:
    event = await require_event_member(db, event_id, user)
    return await event_service.publish_event(db, event)


@router.post("/events/{event_id}/cancel")
async def cancel_event(event_id: uuid.UUID, user: CurrentUser, db: DbSession) -> EventResponse:
    event = await require_event_member(db, event_id, user)
    return await event_service.cancel_event(db, event)
