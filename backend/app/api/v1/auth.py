from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import enforce_rate_limit
from app.core.security import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    create_session,
    delete_session,
)
from app.notify.email import EmailSender, get_email_sender
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    VerifyEmailRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

Sender = Annotated[EmailSender, Depends(get_email_sender)]


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest, request: Request, db: DbSession, sender: Sender
) -> MessageResponse:
    await enforce_rate_limit(request, "register")
    await auth_service.register_user(db, sender, body.email, body.password)
    return MessageResponse(message="確認メールを送信しました")


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: DbSession) -> MessageResponse:
    await auth_service.verify_email(db, body.token)
    return MessageResponse(message="メールアドレスを確認しました")


@router.post("/login")
async def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession
) -> MessageResponse:
    await enforce_rate_limit(request, "login")
    user = await auth_service.authenticate(db, body.email, body.password)
    session_id = await create_session(str(user.id))
    _set_session_cookie(response, session_id)
    return MessageResponse(message="ログインしました")


@router.post("/logout")
async def logout(
    _user: CurrentUser,
    response: Response,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> MessageResponse:
    if session_id:
        await delete_session(session_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return MessageResponse(message="ログアウトしました")


@router.get("/me")
async def me(user: CurrentUser, db: DbSession) -> MeResponse:
    return await auth_service.build_me_response(db, user)


@router.post("/password-reset/request")
async def password_reset_request(
    body: PasswordResetRequest, db: DbSession, sender: Sender
) -> MessageResponse:
    await auth_service.request_password_reset(db, sender, body.email)
    return MessageResponse(message="登録されている場合、再設定メールを送信しました")


@router.post("/password-reset/confirm")
async def password_reset_confirm(body: PasswordResetConfirm, db: DbSession) -> MessageResponse:
    await auth_service.confirm_password_reset(db, body.token, body.new_password)
    return MessageResponse(message="パスワードを再設定しました")
