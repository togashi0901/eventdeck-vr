"""応募API (§2.6) のテスト (M3 完了条件)。"""
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.factories import (
    create_event,
    create_org,
    publish_event,
    put_form,
    register_and_login,
    setup_profile,
)

OWNER = "owner@example.com"
FAN = "fan@example.com"


async def _published_event_with_form(client, email_outbox, **event_overrides):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id, **event_overrides)
    items = await put_form(client, event["id"])
    await publish_event(client, event["id"])
    return event["id"], items


async def _participant(make_client, email_outbox, email, vrchat=None, display_name="参加者"):
    c = make_client()
    await register_and_login(c, email_outbox, email)
    await setup_profile(c, display_name=display_name, vrchat_username=vrchat)
    return c


def _answers(items, vrchat="fan_vrc", platform="PCVR", interests=None):
    answers = [
        {"form_item_id": items[0]["id"], "value": vrchat},
        {"form_item_id": items[1]["id"], "value": platform},
    ]
    if interests:
        answers.append({"form_item_id": items[2]["id"], "values": interests})
    return {"answers": answers}


async def test_apply_flow(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(client, email_outbox)
    fan = await _participant(
        make_client, email_outbox, FAN, vrchat="fan_vrc", display_name="ファンA"
    )

    resp = await fan.post(
        f"/api/v1/events/{event_id}/applications",
        json=_answers(items, interests=["ライブ", "交流会"]),
    )
    assert resp.status_code == 201, resp.text
    app = resp.json()
    assert app["status"] == "pending"  # 抽選イベントは結果待ち

    # マイページに「応募中」+ short_code
    mine = (await fan.get("/api/v1/me/applications")).json()
    assert len(mine) == 1
    assert mine[0]["status"] == "pending"
    assert mine[0]["event"]["title"] == "テストイベント"
    assert mine[0]["short_code"] == app["id"][:8]

    # イベント詳細の application_state
    detail = (await fan.get(f"/api/v1/events/{event_id}")).json()
    assert detail["application_state"] == {"applied": True, "status": "pending"}

    # 主催者の応募者一覧に回答ごと表示
    applicants = (await client.get(f"/api/v1/events/{event_id}/applications")).json()
    assert len(applicants) == 1
    a = applicants[0]
    assert a["display_name"] == "ファンA"
    assert {ans["label"]: ans.get("value") or ans.get("values") for ans in a["answers"]} == {
        "VRChatユーザー名": "fan_vrc",
        "参加予定プラットフォーム": "PCVR",
        "興味のある企画": ["ライブ", "交流会"],
    }

    # 応募詳細は本人・memberとも見える。第三者は404
    app_id = app["id"]
    assert (await fan.get(f"/api/v1/applications/{app_id}")).status_code == 200
    assert (await client.get(f"/api/v1/applications/{app_id}")).status_code == 200
    stranger = await _participant(make_client, email_outbox, "stranger@example.com")
    assert (await stranger.get(f"/api/v1/applications/{app_id}")).status_code == 404


async def test_apply_validations(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(client, email_outbox)
    fan = await _participant(make_client, email_outbox, FAN)

    # 必須未回答 → 400
    resp = await fan.post(f"/api/v1/events/{event_id}/applications", json={"answers": []})
    assert resp.status_code == 400
    reasons = {d["reason"] for d in resp.json()["error"]["details"]}
    assert "required" in reasons

    # options に無い値 → 400
    resp = await fan.post(
        f"/api/v1/events/{event_id}/applications", json=_answers(items, platform="PSVR")
    )
    assert resp.status_code == 400

    # checkbox に無い値 → 400
    resp = await fan.post(
        f"/api/v1/events/{event_id}/applications",
        json=_answers(items, interests=["存在しない企画"]),
    )
    assert resp.status_code == 400

    # 存在しない設問 → 400
    resp = await fan.post(
        f"/api/v1/events/{event_id}/applications",
        json={
            "answers": [
                {"form_item_id": "00000000-0000-0000-0000-000000000000", "value": "x"}
            ]
        },
    )
    assert resp.status_code == 400


async def test_apply_requires_profile(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(client, email_outbox)
    noprof = make_client()
    await register_and_login(noprof, email_outbox, "noprof@example.com")

    resp = await noprof.post(
        f"/api/v1/events/{event_id}/applications", json=_answers(items)
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "profile_required"


async def test_duplicate_application_409(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(client, email_outbox)
    fan = await _participant(make_client, email_outbox, FAN)

    assert (
        await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    ).status_code == 201
    resp = await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_applied"


async def test_apply_window(client, email_outbox, make_client, db_session):
    # 受付開始前 → 409
    event_id, items = await _published_event_with_form(
        client,
        email_outbox,
        apply_starts_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
        apply_ends_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
    )
    fan = await _participant(make_client, email_outbox, FAN)
    resp = await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    assert resp.status_code == 409

    # 締切後 → 409 (公開後に締切をDB上で過去に移動して再現)
    await db_session.execute(
        text("UPDATE events SET apply_starts_at = now() - interval '2 day', "
             "apply_ends_at = now() - interval '1 day' WHERE id = :id"),
        {"id": event_id},
    )
    await db_session.commit()
    resp = await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    assert resp.status_code == 409


async def test_apply_to_draft_404(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id)
    items = await put_form(client, event["id"])

    fan = await _participant(make_client, email_outbox, FAN)
    resp = await fan.post(
        f"/api/v1/events/{event['id']}/applications", json=_answers(items)
    )
    assert resp.status_code == 404


async def test_first_come_wins_within_capacity(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(
        client, email_outbox, selection_method="first_come", capacity=2
    )
    statuses = []
    for i in range(3):
        fan = await _participant(make_client, email_outbox, f"fc{i}@example.com")
        resp = await fan.post(
            f"/api/v1/events/{event_id}/applications", json=_answers(items)
        )
        assert resp.status_code == 201
        statuses.append(resp.json()["status"])
    assert statuses == ["won", "won", "pending"]  # 定員2: 3人目は定員外


async def test_first_come_concurrent_race(client, email_outbox, make_client):
    """同時応募でも当選は定員ちょうど (イベント行ロックの検証)。"""
    event_id, items = await _published_event_with_form(
        client, email_outbox, selection_method="first_come", capacity=1
    )
    fans = []
    for i in range(3):
        fans.append(await _participant(make_client, email_outbox, f"race{i}@example.com"))

    responses = await asyncio.gather(
        *[
            fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
            for fan in fans
        ]
    )
    statuses = sorted(r.json()["status"] for r in responses)
    assert all(r.status_code == 201 for r in responses)
    assert statuses == ["pending", "pending", "won"]  # won はちょうど1人


async def test_cancel_application(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(client, email_outbox)
    fan = await _participant(make_client, email_outbox, FAN)
    app = (
        await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    ).json()

    # 本人以外のキャンセル → 404 (主催者でも不可)
    assert (await client.post(f"/api/v1/applications/{app['id']}/cancel")).status_code == 404

    resp = await fan.post(
        f"/api/v1/applications/{app['id']}/cancel", json={"reason": "都合が悪くなった"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"
    assert resp.json()["canceled_at"] is not None

    # 二重キャンセル → 409 (canceled → canceled は遷移不可)
    assert (await fan.post(f"/api/v1/applications/{app['id']}/cancel")).status_code == 409


async def test_cancel_won_first_come(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(
        client, email_outbox, selection_method="first_come", capacity=5
    )
    fan = await _participant(make_client, email_outbox, FAN)
    app = (
        await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    ).json()
    assert app["status"] == "won"
    resp = await fan.post(f"/api/v1/applications/{app['id']}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"


async def test_applicant_list_filters(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(
        client, email_outbox, selection_method="first_come", capacity=1
    )
    a = await _participant(
        make_client, email_outbox, "fanA@example.com", display_name="アリス", vrchat="alice_vrc"
    )
    b = await _participant(
        make_client, email_outbox, "fanB@example.com", display_name="ボブ", vrchat="bob_vrc"
    )
    await a.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    await b.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))

    all_apps = (await client.get(f"/api/v1/events/{event_id}/applications")).json()
    assert len(all_apps) == 2

    won = (await client.get(f"/api/v1/events/{event_id}/applications?status=won")).json()
    assert [x["display_name"] for x in won] == ["アリス"]  # 先着1名

    hit = (await client.get(f"/api/v1/events/{event_id}/applications?q=ボブ")).json()
    assert [x["display_name"] for x in hit] == ["ボブ"]
    hit = (await client.get(f"/api/v1/events/{event_id}/applications?q=alice")).json()
    assert [x["display_name"] for x in hit] == ["アリス"]

    # 非member → 404
    assert (await a.get(f"/api/v1/events/{event_id}/applications")).status_code == 404


async def test_entry_code(client, email_outbox, make_client):
    event_id, items = await _published_event_with_form(client, email_outbox)
    fan = await _participant(make_client, email_outbox, FAN)
    app = (
        await fan.post(f"/api/v1/events/{event_id}/applications", json=_answers(items))
    ).json()

    resp = await fan.get(f"/api/v1/me/applications/{app['id']}/entry-code")
    assert resp.status_code == 200
    assert resp.json() == {"application_id": app["id"], "short_code": app["id"][:8]}

    # 他人 (主催者含む) は404
    assert (
        await client.get(f"/api/v1/me/applications/{app['id']}/entry-code")
    ).status_code == 404
