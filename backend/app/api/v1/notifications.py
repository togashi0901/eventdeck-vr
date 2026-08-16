import uuid

from fastapi import APIRouter

from app.core.authz import require_event_member
from app.core.deps import CurrentUser, DbSession
from app.schemas.notification import (
    BroadcastRequest,
    BroadcastResponse,
    NotificationHistoryResponse,
)
from app.services import notification as notification_service

router = APIRouter(tags=["notifications"])


@router.post("/events/{event_id}/notifications", status_code=201)
async def broadcast(
    event_id: uuid.UUID, body: BroadcastRequest, user: CurrentUser, db: DbSession
) -> BroadcastResponse:
    event = await require_event_member(db, event_id, user)
    return await notification_service.broadcast(db, event, body)


@router.get("/events/{event_id}/notifications")
async def history(
    event_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> NotificationHistoryResponse:
    event = await require_event_member(db, event_id, user)
    return await notification_service.history(db, event)
