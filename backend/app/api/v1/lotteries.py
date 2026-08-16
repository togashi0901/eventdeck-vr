import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.authz import require_event_member
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import MessageResponse
from app.schemas.lottery import (
    ExecuteResponse,
    LotteryHistoryItem,
    LotteryRequest,
    LotteryResultsResponse,
    PreviewResponse,
)
from app.services import lottery as lottery_service

router = APIRouter(tags=["lotteries"])


@router.post("/events/{event_id}/lotteries/preview")
async def preview(
    event_id: uuid.UUID, body: LotteryRequest, user: CurrentUser, db: DbSession
) -> PreviewResponse:
    event = await require_event_member(db, event_id, user)
    return await lottery_service.preview(db, event, body)


@router.post("/events/{event_id}/lotteries", status_code=201)
async def execute(
    event_id: uuid.UUID, body: LotteryRequest, user: CurrentUser, db: DbSession
) -> ExecuteResponse:
    await require_event_member(db, event_id, user)
    return await lottery_service.execute(db, event_id, user, body)


@router.get("/events/{event_id}/lotteries")
async def history(
    event_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[LotteryHistoryItem]:
    event = await require_event_member(db, event_id, user)
    return await lottery_service.list_history(db, event)


@router.get("/lotteries/{lottery_id}/results")
async def results(
    lottery_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LotteryResultsResponse:
    return await lottery_service.get_results(db, lottery_id, user, page, per_page)


@router.post("/applications/{application_id}/promote")
async def promote(
    application_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> MessageResponse:
    await lottery_service.manual_promote(db, application_id, user)
    return MessageResponse(message="繰り上げました")
