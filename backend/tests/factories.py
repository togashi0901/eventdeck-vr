"""テストデータのファクトリ関数 (CLAUDE.md §5)。"""
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.notify.email import MemoryEmailSender

DEFAULT_PASSWORD = "Passw0rd!"

_TOKEN_RE = re.compile(r"token=([A-Za-z0-9_\-]+)")


def extract_token(outbox: MemoryEmailSender, index: int = -1) -> str:
    """送信済みメール本文から確認/リセットトークンを取り出す。"""
    match = _TOKEN_RE.search(outbox.sent[index].body)
    assert match, f"メール本文にトークンが無い: {outbox.sent[index].body!r}"
    return match.group(1)


async def register_user(
    client: httpx.AsyncClient,
    outbox: MemoryEmailSender,
    email: str,
    password: str = DEFAULT_PASSWORD,
    *,
    verify: bool = True,
) -> None:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    if verify:
        token = extract_token(outbox)
        resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert resp.status_code == 200, resp.text


async def login(
    client: httpx.AsyncClient, email: str, password: str = DEFAULT_PASSWORD
) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


async def register_and_login(
    client: httpx.AsyncClient,
    outbox: MemoryEmailSender,
    email: str,
    password: str = DEFAULT_PASSWORD,
) -> None:
    await register_user(client, outbox, email, password)
    resp = await login(client, email, password)
    assert resp.status_code == 200, resp.text


async def create_org(
    client: httpx.AsyncClient, slug: str = "test-org", name: str = "テスト団体"
) -> str:
    """ログイン中のユーザーで団体を作成し org_id を返す (作成者は owner)。"""
    resp = await client.post(
        "/api/v1/organizations", json={"name": name, "slug": slug}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def event_payload(**overrides) -> dict:
    """有効な時系列 (apply: -1日〜+7日 / 開催: +14日〜+14日2h) を持つイベント本文。"""
    now = datetime.now(UTC)

    def iso(delta: timedelta) -> str:
        return (now + delta).isoformat()

    payload = {
        "title": "テストイベント",
        "description": "テスト用",
        "platform": "vrchat",
        "world_name": "Test World",
        "starts_at": iso(timedelta(days=14)),
        "ends_at": iso(timedelta(days=14, hours=2)),
        "capacity": 5,
        "selection_method": "lottery",
        "apply_starts_at": iso(timedelta(days=-1)),
        "apply_ends_at": iso(timedelta(days=7)),
        "visibility": "public",
    }
    payload.update(overrides)
    return payload


async def create_event(client: httpx.AsyncClient, org_id: str, **overrides) -> dict:
    """ログイン中のユーザーでイベント (draft) を作成しレスポンス本文を返す。"""
    resp = await client.post(f"/api/v1/orgs/{org_id}/events", json=event_payload(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def setup_profile(
    client: httpx.AsyncClient,
    display_name: str = "参加者",
    vrchat_username: str | None = None,
) -> None:
    resp = await client.put(
        "/api/v1/me/profile",
        json={
            "display_name": display_name,
            "vrchat_username": vrchat_username,
            "platform": "pcvr",
        },
    )
    assert resp.status_code == 200, resp.text


async def publish_event(client: httpx.AsyncClient, event_id: str) -> None:
    resp = await client.post(f"/api/v1/events/{event_id}/publish")
    assert resp.status_code == 200, resp.text


def form_items_payload() -> list[dict]:
    """設問2種 (autofill付きtext + radio) + 任意checkbox。"""
    return [
        {
            "label": "VRChatユーザー名",
            "item_type": "text",
            "is_required": True,
            "autofill_key": "vrchat_username",
        },
        {
            "label": "参加予定プラットフォーム",
            "item_type": "radio",
            "is_required": True,
            "options": ["PCVR", "Quest単体", "デスクトップ"],
        },
        {
            "label": "興味のある企画",
            "item_type": "checkbox",
            "is_required": False,
            "options": ["ライブ", "交流会", "ワールド巡り"],
        },
    ]


async def put_form(
    client: httpx.AsyncClient, event_id: str, items: list[dict] | None = None
) -> list[dict]:
    resp = await client.put(
        f"/api/v1/events/{event_id}/form", json={"items": items or form_items_payload()}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]
