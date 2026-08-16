"""認証サービス (03_API仕様書 §2.1)。"""
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.core.security import (
    RESET_TOKEN_TTL_SECONDS,
    VERIFY_TOKEN_TTL_SECONDS,
    consume_token,
    hash_password,
    is_valid_password,
    issue_token,
    mask_email,
    verify_password,
)
from app.models import Organization, OrganizationMember, User, UserProfile
from app.notify.email import EmailSender
from app.schemas.auth import MeOrganization, MeResponse

logger = logging.getLogger(__name__)


def _validate_password_or_raise(password: str) -> None:
    if not is_valid_password(password):
        raise ApiError(
            400,
            "validation_error",
            "パスワードは8文字以上で、英字と数字を含めてください",
            details=[{"field": "password", "reason": "weak"}],
        )


async def register_user(db: AsyncSession, sender: EmailSender, email: str, password: str) -> User:
    _validate_password_or_raise(password)
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ApiError(409, "conflict", "このメールアドレスは登録済みです")

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.flush()

    token = await issue_token("email_verify", str(user.id), VERIFY_TOKEN_TTL_SECONDS)
    await sender.send(
        to=email,
        subject="【EventDeck VR】メールアドレスの確認",
        body=(
            "EventDeck VR へのご登録ありがとうございます。\n"
            "以下のリンクを開いてメールアドレスを確認してください（24時間有効）。\n\n"
            f"{settings.base_url}/verify-email?token={token}\n"
        ),
    )
    await db.commit()
    logger.info("user registered: %s", mask_email(email))
    return user


async def verify_email(db: AsyncSession, token: str) -> None:
    user_id = await consume_token("email_verify", token)
    if user_id is None:
        raise ApiError(400, "validation_error", "トークンが無効か期限切れです")
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(400, "validation_error", "トークンが無効です")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        await db.commit()


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or not verify_password(user.password_hash, password):
        raise ApiError(401, "invalid_credentials", "メールアドレスまたはパスワードが違います")
    if user.email_verified_at is None:
        raise ApiError(
            403,
            "email_not_verified",
            "メールアドレスが未確認です。確認メールのリンクを開いてください",
        )
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    return user


async def request_password_reset(db: AsyncSession, sender: EmailSender, email: str) -> None:
    """存在有無に関わらず 200 を返す前提 (列挙防止)。存在する場合のみメール送信。"""
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        logger.info("password reset requested for unknown email: %s", mask_email(email))
        return
    token = await issue_token("password_reset", str(user.id), RESET_TOKEN_TTL_SECONDS)
    await sender.send(
        to=email,
        subject="【EventDeck VR】パスワード再設定",
        body=(
            "パスワード再設定のリクエストを受け付けました。\n"
            "以下のリンクから新しいパスワードを設定してください（1時間有効）。\n"
            "心当たりがない場合はこのメールを無視してください。\n\n"
            f"{settings.base_url}/password-reset/confirm?token={token}\n"
        ),
    )


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    _validate_password_or_raise(new_password)
    user_id = await consume_token("password_reset", token)
    if user_id is None:
        raise ApiError(400, "validation_error", "トークンが無効か期限切れです")
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(400, "validation_error", "トークンが無効です")
    user.password_hash = hash_password(new_password)
    await db.commit()


async def build_me_response(db: AsyncSession, user: User) -> MeResponse:
    has_profile = (await db.get(UserProfile, user.id)) is not None
    rows = (
        await db.execute(
            select(Organization.id, Organization.name, OrganizationMember.role)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(Organization.name)
        )
    ).all()
    return MeResponse(
        id=str(user.id),
        email=user.email,
        has_profile=has_profile,
        organizations=[
            MeOrganization(id=str(org_id), name=name, role=role) for org_id, name, role in rows
        ],
    )
