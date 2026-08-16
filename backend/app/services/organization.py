"""団体サービス (03_API仕様書 §2.3)。"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND
from app.core.errors import ApiError
from app.models import Event, Organization, OrganizationMember, User, UserProfile
from app.schemas.organization import (
    MemberAddRequest,
    MemberResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    PublicOrganizationResponse,
)
from app.services.event import to_event_response


def _to_response(org: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        website_url=org.website_url,
        plan=org.plan,
        created_at=org.created_at,
    )


async def create_organization(
    db: AsyncSession, user: User, data: OrganizationCreateRequest
) -> OrganizationResponse:
    """作成者が owner になる (§2.3)。"""
    existing = await db.scalar(select(Organization).where(Organization.slug == data.slug))
    if existing is not None:
        raise ApiError(409, "conflict", "このスラッグは使用済みです")
    org = Organization(name=data.name, slug=data.slug, description=data.description)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(org)
    return _to_response(org)


async def get_public_organization(db: AsyncSession, slug: str) -> PublicOrganizationResponse:
    org = await db.scalar(select(Organization).where(Organization.slug == slug))
    if org is None:
        raise NOT_FOUND
    events = (
        await db.scalars(
            select(Event)
            .where(
                Event.organization_id == org.id,
                Event.status == "published",
                Event.visibility == "public",
            )
            .order_by(Event.starts_at)
        )
    ).all()
    return PublicOrganizationResponse(
        name=org.name,
        slug=org.slug,
        description=org.description,
        website_url=org.website_url,
        events=[to_event_response(e, org) for e in events],
    )


def to_admin_response(org: Organization) -> OrganizationResponse:
    return _to_response(org)


async def update_organization(
    db: AsyncSession, org: Organization, data: OrganizationUpdateRequest
) -> OrganizationResponse:
    org.name = data.name
    org.description = data.description
    org.website_url = data.website_url
    await db.commit()
    await db.refresh(org)
    return _to_response(org)


async def list_members(db: AsyncSession, org_id: uuid.UUID) -> list[MemberResponse]:
    rows = (
        await db.execute(
            select(
                OrganizationMember.user_id,
                User.email,
                UserProfile.display_name,
                OrganizationMember.role,
                OrganizationMember.joined_at,
            )
            .join(User, User.id == OrganizationMember.user_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(OrganizationMember.organization_id == org_id)
            .order_by(OrganizationMember.joined_at)
        )
    ).all()
    return [
        MemberResponse(
            user_id=str(user_id),
            email=email,
            display_name=display_name,
            role=role,
            joined_at=joined_at,
        )
        for user_id, email, display_name, role, joined_at in rows
    ]


async def add_member(
    db: AsyncSession, org_id: uuid.UUID, data: MemberAddRequest
) -> MemberResponse:
    """登録済みユーザーをメールアドレスで追加 (MVP。招待フローは将来)。"""
    user = await db.scalar(
        select(User).where(User.email == data.email, User.deleted_at.is_(None))
    )
    if user is None:
        raise ApiError(404, "not_found", "このメールアドレスのユーザーが見つかりません")
    if await db.get(OrganizationMember, (org_id, user.id)) is not None:
        raise ApiError(409, "conflict", "すでにメンバーです")
    db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=data.role))
    await db.commit()
    profile = await db.get(UserProfile, user.id)
    membership = await db.get(OrganizationMember, (org_id, user.id))
    return MemberResponse(
        user_id=str(user.id),
        email=user.email,
        display_name=profile.display_name if profile else None,
        role=membership.role,
        joined_at=membership.joined_at,
    )


async def remove_member(db: AsyncSession, org_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
    """除名。最後の owner は削除不可 (409)。"""
    membership = await db.get(OrganizationMember, (org_id, target_user_id))
    if membership is None:
        raise NOT_FOUND
    if membership.role == "owner":
        owner_count = await db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == "owner",
            )
        )
        if owner_count <= 1:
            raise ApiError(409, "conflict", "最後のオーナーは除名できません")
    await db.delete(membership)
    await db.commit()
