"""パスワードハッシュ・セッション・ワンタイムトークン (03_API仕様書 §1.1)。"""
import json
import re
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.redis import redis_client

_hasher = PasswordHasher()  # argon2id (デフォルト)

SESSION_TTL_SECONDS = 14 * 24 * 60 * 60  # 14日 (§1.1)
VERIFY_TOKEN_TTL_SECONDS = 24 * 60 * 60
RESET_TOKEN_TTL_SECONDS = 60 * 60

SESSION_COOKIE = "session_id"

# パスワードポリシー: 8文字以上かつ英字と数字を含む
# (仕様書に明記がないため採用した規則。PROGRESS.md の要確認欄に記録)
PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def is_valid_password(password: str) -> bool:
    return bool(PASSWORD_PATTERN.match(password))


def mask_email(email: str) -> str:
    """ログ出力用マスク (不変条件8: メールアドレス全体をログに出さない)。"""
    local, _, domain = email.partition("@")
    head = local[:2] if len(local) > 2 else local[:1]
    return f"{head}***@{domain}"


# --- セッション (Redis: session:{id} → {user_id, created_at}) ---

async def create_session(user_id: str) -> str:
    session_id = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": user_id, "created_at": datetime.now(UTC).isoformat()})
    await redis_client.set(f"session:{session_id}", payload, ex=SESSION_TTL_SECONDS)
    return session_id


async def get_session_user_id(session_id: str) -> str | None:
    raw = await redis_client.get(f"session:{session_id}")
    if raw is None:
        return None
    return json.loads(raw)["user_id"]


async def delete_session(session_id: str) -> None:
    await redis_client.delete(f"session:{session_id}")


# --- ワンタイムトークン (メール確認・パスワードリセット) ---

async def issue_token(kind: str, user_id: str, ttl: int) -> str:
    token = secrets.token_urlsafe(32)
    await redis_client.set(f"{kind}:{token}", user_id, ex=ttl)
    return token


async def consume_token(kind: str, token: str) -> str | None:
    """トークンを検証し、対応する user_id を返して無効化する (使い捨て)。"""
    key = f"{kind}:{token}"
    user_id = await redis_client.get(key)
    if user_id is not None:
        await redis_client.delete(key)
    return user_id
