from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """アプリ内で送出する統一例外。ハンドラで 03_API仕様書 §1.3 の JSON に変換する。"""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: list[dict] | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    error: dict = {"code": exc.code, "message": exc.message}
    if exc.details is not None:
        error["details"] = exc.details
    return JSONResponse(status_code=exc.status, content={"error": error})
