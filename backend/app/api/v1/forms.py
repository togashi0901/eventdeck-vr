import uuid

from fastapi import APIRouter

from app.core.authz import require_event_member
from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.schemas.form import FormPutRequest, FormResponse
from app.services import form as form_service

router = APIRouter(tags=["forms"])


@router.get("/events/{event_id}/form")
async def get_form(event_id: uuid.UUID, user: OptionalUser, db: DbSession) -> FormResponse:
    return await form_service.get_form(db, event_id, user)


@router.put("/events/{event_id}/form")
async def put_form(
    event_id: uuid.UUID, body: FormPutRequest, user: CurrentUser, db: DbSession
) -> FormResponse:
    event = await require_event_member(db, event_id, user)
    return await form_service.replace_form(db, event, body.items)
