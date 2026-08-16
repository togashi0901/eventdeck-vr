from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """全モデルの基底 (2.0スタイル)。

    schema.sql の日時列はすべて timestamptz のため、datetime 注釈を
    timezone-aware にマップする (naive datetime を作らない規約と対)。
    """

    type_annotation_map = {datetime: DateTime(timezone=True)}


engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依存性: リクエストごとに AsyncSession を払い出す。"""
    async with SessionLocal() as session:
        yield session
