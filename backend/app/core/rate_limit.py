"""IPベースのレート制限 (03_API仕様書 §1.4: login/register は 10回/分)。"""
from fastapi import Request

from app.core.errors import ApiError
from app.core.redis import redis_client

LIMIT_PER_MINUTE = 10
WINDOW_SECONDS = 60


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(request: Request, endpoint: str) -> None:
    key = f"rl:{endpoint}:{client_ip(request)}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, WINDOW_SECONDS)
    if count > LIMIT_PER_MINUTE:
        raise ApiError(
            429, "rate_limited", "試行回数が多すぎます。しばらく待ってから再試行してください"
        )
