import uuid

from fastapi import APIRouter

from app.core.authz import require_event_member
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import MessageResponse
from app.schemas.checkin import CheckinCreateRequest, CheckinItem, CheckinListResponse
from app.services import checkin as checkin_service

router = APIRouter(tags=["checkins"])


@router.post("/events/{event_id}/checkins", status_code=201)
async def create_checkin(
    event_id: uuid.UUID, body: CheckinCreateRequest, user: CurrentUser, db: DbSession
) -> CheckinItem:
    event = await require_event_member(db, event_id, user)
    return await checkin_service.create_checkin(db, event, user, body)


@router.get("/events/{event_id}/checkins")
async def list_checkins(
    event_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> CheckinListResponse:
    event = await require_event_member(db, event_id, user)
    return await checkin_service.list_checkins(db, event)


@router.delete("/checkins/{checkin_id}")
async def delete_checkin(
    checkin_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> MessageResponse:
    await checkin_service.delete_checkin(db, checkin_id, user)
    return MessageResponse(message="入場を取り消しました")
