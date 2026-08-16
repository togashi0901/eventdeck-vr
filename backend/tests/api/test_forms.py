"""応募フォームAPI (§2.5) のテスト (M3 完了条件)。"""
from tests.factories import (
    create_event,
    create_org,
    form_items_payload,
    publish_event,
    put_form,
    register_and_login,
    setup_profile,
)

OWNER = "owner@example.com"
FAN = "fan@example.com"


async def _setup_event(client, email_outbox) -> tuple[str, str]:
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id)
    return org_id, event["id"]


async def test_form_roundtrip_and_order(client, email_outbox):
    _, event_id = await _setup_event(client, email_outbox)
    items = await put_form(client, event_id)
    assert [i["sort_order"] for i in items] == [0, 1, 2]
    assert items[0]["autofill_key"] == "vrchat_username"
    assert items[1]["options"] == ["PCVR", "Quest単体", "デスクトップ"]

    # 並び替え+ラベル修正して再PUT (全置換)
    reordered = [
        {**items[1], "label": "プラットフォーム(改)"},
        items[0],
        items[2],
    ]
    updated = await put_form(client, event_id, reordered)
    assert updated[0]["label"] == "プラットフォーム(改)"
    assert updated[1]["id"] == items[0]["id"]


async def test_form_validation(client, email_outbox):
    _, event_id = await _setup_event(client, email_outbox)

    # 選択式なのに options なし → 400
    resp = await client.put(
        f"/api/v1/events/{event_id}/form",
        json={"items": [{"label": "x", "item_type": "select"}]},
    )
    assert resp.status_code == 400

    # 非選択式なのに options あり → 400
    resp = await client.put(
        f"/api/v1/events/{event_id}/form",
        json={"items": [{"label": "x", "item_type": "text", "options": ["a"]}]},
    )
    assert resp.status_code == 400

    # 他イベントの設問id → 400
    resp = await client.put(
        f"/api/v1/events/{event_id}/form",
        json={
            "items": [
                {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "label": "x",
                    "item_type": "text",
                }
            ]
        },
    )
    assert resp.status_code == 400


async def test_form_public_get_and_prefill(client, email_outbox, make_client):
    _, event_id = await _setup_event(client, email_outbox)
    items = await put_form(client, event_id)
    await publish_event(client, event_id)

    # 未ログイン: 設問は見えるが prefill なし
    anon = make_client()
    body = (await anon.get(f"/api/v1/events/{event_id}/form")).json()
    assert len(body["items"]) == 3
    assert body["prefill"] is None

    # プロフィール登録済みユーザー: autofill_key が解決される
    fan = make_client()
    await register_and_login(fan, email_outbox, FAN)
    await setup_profile(fan, display_name="ファン", vrchat_username="fan_vrc")
    body = (await fan.get(f"/api/v1/events/{event_id}/form")).json()
    assert body["prefill"] == {items[0]["id"]: "fan_vrc"}

    # プロフィール未登録ユーザー: prefill なし
    noprof = make_client()
    await register_and_login(noprof, email_outbox, "noprof@example.com")
    body = (await noprof.get(f"/api/v1/events/{event_id}/form")).json()
    assert body["prefill"] is None


async def test_form_locked_after_application(client, email_outbox, make_client):
    _, event_id = await _setup_event(client, email_outbox)
    items = await put_form(client, event_id)
    await publish_event(client, event_id)

    fan = make_client()
    await register_and_login(fan, email_outbox, FAN)
    await setup_profile(fan, vrchat_username="fan_vrc")
    resp = await fan.post(
        f"/api/v1/events/{event_id}/applications",
        json={
            "answers": [
                {"form_item_id": items[0]["id"], "value": "fan_vrc"},
                {"form_item_id": items[1]["id"], "value": "PCVR"},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    # 削除 → 409 form_locked
    resp = await client.put(
        f"/api/v1/events/{event_id}/form", json={"items": [items[0], items[1]]}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "form_locked"

    # item_type 変更 → 409
    changed = [dict(items[0], item_type="textarea"), items[1], items[2]]
    resp = await client.put(f"/api/v1/events/{event_id}/form", json={"items": changed})
    assert resp.status_code == 409

    # is_required false→true → 409
    changed = [items[0], items[1], dict(items[2], is_required=True)]
    resp = await client.put(f"/api/v1/events/{event_id}/form", json={"items": changed})
    assert resp.status_code == 409

    # ラベル修正 + 設問追加は可
    ok_items = [dict(items[0], label="VRChat名(修正)"), items[1], items[2]] + [
        {"label": "意気込み", "item_type": "textarea", "is_required": False}
    ]
    resp = await client.put(f"/api/v1/events/{event_id}/form", json={"items": ok_items})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 4


async def test_form_put_requires_member(client, email_outbox, make_client):
    _, event_id = await _setup_event(client, email_outbox)

    other = make_client()
    await register_and_login(other, email_outbox, FAN)
    resp = await other.put(
        f"/api/v1/events/{event_id}/form", json={"items": form_items_payload()}
    )
    assert resp.status_code == 404
