"""CSRF対策ミドルウェア (03_API仕様書 §1.1)。

状態変更系 (POST/PUT/DELETE/PATCH) は `X-Requested-With: XMLHttpRequest` を必須とする
(不変条件6)。SameSite=Lax と併用。Stripe webhook (M6) は導入時に除外リストへ追加する。
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
EXEMPT_PATHS: set[str] = set()  # 例: "/api/v1/webhooks/stripe" (M6)


class CsrfHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            request.method in MUTATING_METHODS
            and request.url.path.startswith("/api/")
            and request.url.path not in EXEMPT_PATHS
            and request.headers.get("x-requested-with") != "XMLHttpRequest"
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "csrf_required",
                        "message": "X-Requested-With ヘッダが必要です",
                    }
                },
            )
        return await call_next(request)
