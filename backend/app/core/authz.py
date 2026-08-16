"""認可ヘルパ (03_API仕様書 §1.2)。

member/owner チェック。リソースの存在有無を漏らさないため、
権限なし・不存在はどちらも 404 not_found を返す (不変条件5)。
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import Event, Organization, OrganizationMember, User

NOT_FOUND = ApiError(404, "not_found", "リソースが見つかりません")


async def get_membership(
    db: AsyncSession, org_id: uuid.UUID, user: User
) -> OrganizationMember | None:
    return await db.get(OrganizationMember, (org_id, user.id))


async def require_org_member(
    db: AsyncSession, org_id: uuid.UUID, user: User
) -> Organization:
    org = await db.get(Organization, org_id)
    if org is None or await get_membership(db, org_id, user) is None:
        raise NOT_FOUND
    return org


async def require_org_owner(
    db: AsyncSession, org_id: uuid.UUID, user: User
) -> Organization:
    org = await db.get(Organization, org_id)
    membership = await get_membership(db, org_id, user)
    if org is None or membership is None or membership.role != "owner":
        raise NOT_FOUND
    return org


async def require_event_member(
    db: AsyncSession, event_id: uuid.UUID, user: User
) -> Event:
    """イベント → organization_id → 所属、の順に解決する (§1.2)。"""
    event = await db.get(Event, event_id)
    if event is None or await get_membership(db, event.organization_id, user) is None:
        raise NOT_FOUND
    return event
