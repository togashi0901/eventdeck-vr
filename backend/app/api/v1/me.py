import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.application import EntryCodeResponse, MyApplicationItem
from app.schemas.auth import MessageResponse
from app.schemas.notification import NotificationItem, PushSubscribeRequest
from app.schemas.profile import ProfileResponse, ProfileUpsertRequest
from app.services import application as app_service
from app.services import notification as notification_service
from app.services import profile as profile_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/profile")
async def get_profile(user: CurrentUser, db: DbSession) -> ProfileResponse:
    return await profile_service.get_profile(db, user)


@router.put("/profile")
async def put_profile(
    body: ProfileUpsertRequest, user: CurrentUser, db: DbSession
) -> ProfileResponse:
    return await profile_service.upsert_profile(db, user, body)


@router.get("/applications")
async def my_applications(user: CurrentUser, db: DbSession) -> list[MyApplicationItem]:
    return await app_service.list_my_applications(db, user)


@router.get("/applications/{application_id}/entry-code")
async def entry_code(
    application_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> EntryCodeResponse:
    return await app_service.get_entry_code(db, application_id, user)


@router.get("/notifications")
async def my_notifications(
    user: CurrentUser, db: DbSession, unread_only: bool = False
) -> list[NotificationItem]:
    return await notification_service.my_notifications(db, user, unread_only)


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> NotificationItem:
    return await notification_service.mark_read(db, notification_id, user)


@router.post("/push-subscriptions", status_code=201)
async def subscribe_push(
    body: PushSubscribeRequest, user: CurrentUser, db: DbSession
) -> MessageResponse:
    await notification_service.register_push(db, user, body.fcm_token, body.user_agent)
    return MessageResponse(message="購読しました")


@router.delete("/push-subscriptions/{fcm_token}")
async def unsubscribe_push(
    fcm_token: str, user: CurrentUser, db: DbSession
) -> MessageResponse:
    await notification_service.unregister_push(db, user, fcm_token)
    return MessageResponse(message="購読を解除しました")
