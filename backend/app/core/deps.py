"""FastAPI 共通依存性 (current_user 等)。"""
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import SESSION_COOKIE, get_session_user_id
from app.models import User

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def current_user(
    db: DbSession,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    if not session_id:
        raise ApiError(401, "unauthenticated", "ログインしてください")
    user_id = await get_session_user_id(session_id)
    if user_id is None:
        raise ApiError(401, "unauthenticated", "セッションが失効しました")
    user = await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if user is None:
        raise ApiError(401, "unauthenticated", "セッションが失効しました")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def optional_current_user(
    db: DbSession,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User | None:
    """publicエンドポイント用: ログイン済みなら User、そうでなければ None。"""
    if not session_id:
        return None
    user_id = await get_session_user_id(session_id)
    if user_id is None:
        return None
    return await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))


OptionalUser = Annotated[User | None, Depends(optional_current_user)]
