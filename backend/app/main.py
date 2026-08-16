from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import (
    analytics,
    applications,
    auth,
    checkins,
    events,
    forms,
    health,
    lotteries,
    me,
    notifications,
    organizations,
)
from app.core.errors import ApiError, api_error_handler
from app.core.middleware import CsrfHeaderMiddleware

app = FastAPI(title="EventDeck VR API", version="0.1.0")

app.add_middleware(CsrfHeaderMiddleware)
app.add_exception_handler(ApiError, api_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic バリデーションエラーを §1.3 の JSON 形式に変換する。"""
    details = [
        {"field": ".".join(str(part) for part in err["loc"][1:]), "reason": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content={
            "error": {"code": "validation_error", "message": "入力が不正です", "details": details}
        },
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(forms.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(lotteries.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(checkins.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
