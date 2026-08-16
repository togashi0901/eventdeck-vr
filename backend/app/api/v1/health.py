from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import engine
from app.core.redis import redis_client

router = APIRouter(tags=["health"])


async def _check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False


@router.get("/healthz")
async def healthz() -> dict:
    """監視用ヘルスチェック。DB・Redis 疎通込み (04計画 M0 完了条件)。"""
    return {
        "status": "ok",
        "db": await _check_db(),
        "redis": await _check_redis(),
    }
