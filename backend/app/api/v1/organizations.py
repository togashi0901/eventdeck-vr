import uuid

from fastapi import APIRouter

from app.core.authz import require_org_member, require_org_owner
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import MessageResponse
from app.schemas.organization import (
    MemberAddRequest,
    MemberResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    PublicOrganizationResponse,
)
from app.services import organization as org_service

router = APIRouter(tags=["organizations"])


@router.post("/organizations", status_code=201)
async def create_organization(
    body: OrganizationCreateRequest, user: CurrentUser, db: DbSession
) -> OrganizationResponse:
    return await org_service.create_organization(db, user, body)


@router.get("/organizations/{slug}")
async def public_organization(slug: str, db: DbSession) -> PublicOrganizationResponse:
    return await org_service.get_public_organization(db, slug)


@router.get("/orgs/{org_id}")
async def get_organization(
    org_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> OrganizationResponse:
    org = await require_org_member(db, org_id, user)
    return org_service.to_admin_response(org)


@router.put("/orgs/{org_id}")
async def update_organization(
    org_id: uuid.UUID, body: OrganizationUpdateRequest, user: CurrentUser, db: DbSession
) -> OrganizationResponse:
    org = await require_org_owner(db, org_id, user)
    return await org_service.update_organization(db, org, body)


@router.get("/orgs/{org_id}/members")
async def list_members(
    org_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[MemberResponse]:
    await require_org_member(db, org_id, user)
    return await org_service.list_members(db, org_id)


@router.post("/orgs/{org_id}/members", status_code=201)
async def add_member(
    org_id: uuid.UUID, body: MemberAddRequest, user: CurrentUser, db: DbSession
) -> MemberResponse:
    await require_org_owner(db, org_id, user)
    return await org_service.add_member(db, org_id, body)


@router.delete("/orgs/{org_id}/members/{user_id}")
async def remove_member(
    org_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> MessageResponse:
    await require_org_owner(db, org_id, user)
    await org_service.remove_member(db, org_id, user_id)
    return MessageResponse(message="除名しました")
