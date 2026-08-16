"""認証フローのテスト (M1 完了条件)。"""
import httpx

from app.core.redis import redis_client
from app.core.security import SESSION_COOKIE
from app.main import app
from tests.factories import extract_token, login, register_and_login, register_user

EMAIL = "alice@example.com"


async def test_full_auth_flow(client, email_outbox):
    """登録→未確認ログイン拒否→メール確認→ログイン→me→ログアウトの一連。"""
    # 登録 (201) + 確認メールが1通
    resp = await client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": "Passw0rd!"}
    )
    assert resp.status_code == 201
    assert len(email_outbox.sent) == 1
    assert email_outbox.sent[0].to == EMAIL

    # 未確認のログインは 403 email_not_verified
    resp = await login(client, EMAIL)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "email_not_verified"

    # メール確認 → ログイン成功 + セッションCookie発行
    token = extract_token(email_outbox)
    resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert resp.status_code == 200
    resp = await login(client, EMAIL)
    assert resp.status_code == 200
    session_id = client.cookies.get(SESSION_COOKIE)
    assert session_id

    # セッションが Redis に存在する (M1 完了条件)
    assert await redis_client.get(f"session:{session_id}") is not None

    # me
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["has_profile"] is False
    assert body["organizations"] == []

    # ログアウト → セッションが Redis から消える → me は 401
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert await redis_client.get(f"session:{session_id}") is None
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


async def test_register_duplicate_email(client, email_outbox):
    await register_user(client, email_outbox, EMAIL)
    resp = await client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": "Passw0rd!"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_password_policy(client):
    """8文字以上・英字+数字を含まないパスワードは 400。"""
    for bad in ["short1", "onlyletters", "12345678", "Ab1"]:
        resp = await client.post(
            "/api/v1/auth/register", json={"email": EMAIL, "password": bad}
        )
        assert resp.status_code == 400, bad
        assert resp.json()["error"]["code"] == "validation_error"


async def test_login_wrong_password(client, email_outbox):
    await register_user(client, email_outbox, EMAIL)
    resp = await login(client, EMAIL, "WrongPass1")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_verify_email_invalid_token(client):
    resp = await client.post("/api/v1/auth/verify-email", json={"token": "bogus"})
    assert resp.status_code == 400


async def test_login_rate_limit(client, email_outbox):
    """login は IP あたり 10回/分。11回目は 429 (§1.4)。"""
    await register_user(client, email_outbox, EMAIL)
    for _ in range(10):
        resp = await login(client, EMAIL, "WrongPass1")
        assert resp.status_code == 401
    resp = await login(client, EMAIL, "WrongPass1")
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


async def test_password_reset_flow(client, email_outbox):
    await register_and_login(client, email_outbox, EMAIL)
    await client.post("/api/v1/auth/logout")

    # リクエスト → メール受信 → 新パスワードで確定
    resp = await client.post("/api/v1/auth/password-reset/request", json={"email": EMAIL})
    assert resp.status_code == 200
    token = extract_token(email_outbox)
    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewPassw0rd!"},
    )
    assert resp.status_code == 200

    # 旧パスワードは 401、新パスワードでログイン可
    assert (await login(client, EMAIL, "Passw0rd!")).status_code == 401
    assert (await login(client, EMAIL, "NewPassw0rd!")).status_code == 200

    # トークンは使い捨て
    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "AnotherPass1"},
    )
    assert resp.status_code == 400


async def test_password_reset_unknown_email_no_leak(client, email_outbox):
    """存在しないメールでも 200 を返し、メールは送らない (列挙防止)。"""
    resp = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert resp.status_code == 200
    assert email_outbox.sent == []


async def test_csrf_header_required(client, test_db):
    """X-Requested-With なしの状態変更系リクエストは 400 (不変条件6)。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as raw:
        resp = await raw.post(
            "/api/v1/auth/register", json={"email": EMAIL, "password": "Passw0rd!"}
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "csrf_required"
