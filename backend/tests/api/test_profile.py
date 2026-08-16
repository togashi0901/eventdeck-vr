"""プロフィール upsert のテスト (M1 完了条件)。"""
from tests.factories import register_and_login

EMAIL = "bob@example.com"

PROFILE = {
    "display_name": "トガシ",
    "vrchat_username": "togashi_vrc",
    "platform": "pcvr",
    "device_note": "Quest 3 + PC",
    "x_account": "togashi_x",
    "discord_account": "togashi#0001",
    "bio": "VRイベント好き",
}


async def test_profile_requires_login(client):
    assert (await client.get("/api/v1/me/profile")).status_code == 401
    assert (await client.put("/api/v1/me/profile", json=PROFILE)).status_code == 401


async def test_profile_upsert_flow(client, email_outbox):
    await register_and_login(client, email_outbox, EMAIL)

    # 未登録は 404
    resp = await client.get("/api/v1/me/profile")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

    # PUT で作成 → GET で一致 → me.has_profile が true
    resp = await client.put("/api/v1/me/profile", json=PROFILE)
    assert resp.status_code == 200
    resp = await client.get("/api/v1/me/profile")
    assert resp.status_code == 200
    assert resp.json() == PROFILE
    resp = await client.get("/api/v1/auth/me")
    assert resp.json()["has_profile"] is True

    # PUT で更新 (upsert)
    updated = {**PROFILE, "display_name": "トガシ2", "platform": "desktop"}
    resp = await client.put("/api/v1/me/profile", json=updated)
    assert resp.status_code == 200
    resp = await client.get("/api/v1/me/profile")
    assert resp.json()["display_name"] == "トガシ2"
    assert resp.json()["platform"] == "desktop"


async def test_profile_validation(client, email_outbox):
    await register_and_login(client, email_outbox, EMAIL)

    # platform が許可値以外 → 400
    resp = await client.put("/api/v1/me/profile", json={**PROFILE, "platform": "psvr"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"

    # display_name 空 → 400
    resp = await client.put("/api/v1/me/profile", json={**PROFILE, "display_name": ""})
    assert resp.status_code == 400
