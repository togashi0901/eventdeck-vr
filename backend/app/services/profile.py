"""プロフィールサービス (03_API仕様書 §2.2)。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import User, UserProfile
from app.schemas.profile import ProfileResponse, ProfileUpsertRequest


def _to_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        display_name=profile.display_name,
        vrchat_username=profile.vrchat_username,
        platform=profile.platform,
        device_note=profile.device_note,
        x_account=profile.x_account,
        discord_account=profile.discord_account,
        bio=profile.bio,
    )


async def get_profile(db: AsyncSession, user: User) -> ProfileResponse:
    profile = await db.get(UserProfile, user.id)
    if profile is None:
        raise ApiError(404, "not_found", "プロフィールが未登録です")
    return _to_response(profile)


async def upsert_profile(
    db: AsyncSession, user: User, data: ProfileUpsertRequest
) -> ProfileResponse:
    profile = await db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id, **data.model_dump())
        db.add(profile)
    else:
        for key, value in data.model_dump().items():
            setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return _to_response(profile)
