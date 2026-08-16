import uuid

from fastapi import APIRouter

from app.core.authz import require_event_member
from app.core.deps import CurrentUser, DbSession
from app.schemas.application import (
    ApplicantItem,
    ApplicationCreateRequest,
    ApplicationResponse,
    CancelRequest,
)
from app.services import application as app_service

router = APIRouter(tags=["applications"])


@router.post("/events/{event_id}/applications", status_code=201)
async def apply(
    event_id: uuid.UUID, body: ApplicationCreateRequest, user: CurrentUser, db: DbSession
) -> ApplicationResponse:
    return await app_service.apply(db, event_id, user, body.answers)


@router.get("/events/{event_id}/applications")
async def list_applicants(
    event_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    status: str | None = None,
    q: str | None = None,
) -> list[ApplicantItem]:
    event = await require_event_member(db, event_id, user)
    return await app_service.list_applicants(db, event, status, q)


@router.get("/applications/{application_id}")
async def get_application(
    application_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ApplicationResponse:
    return await app_service.get_application_detail(db, application_id, user)


@router.post("/applications/{application_id}/cancel")
async def cancel_application(
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    body: CancelRequest | None = None,
) -> ApplicationResponse:
    reason = body.reason if body else None
    return await app_service.cancel_application(db, application_id, user, reason)
