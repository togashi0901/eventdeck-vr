"""入場管理API (§2.8) のテスト (M5 完了条件)。"""
from tests.factories import (
    create_event,
    create_org,
    publish_event,
    register_and_login,
    setup_profile,
)

OWNER = "owner@example.com"


async def _event_with_results(client, email_outbox, make_client):
    """first_come 定員2 に3人応募: won 2 / pending 1 の状態を作る。"""
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id, selection_method="first_come", capacity=2)
    await publish_event(client, event["id"])
    apps = {}
    for i in range(3):
        email = f"c{i:02d}@example.com"
        fan = make_client()
        await register_and_login(fan, email_outbox, email)
        await setup_profile(fan, display_name=f"来場者{i:02d}")
        resp = await fan.post(f"/api/v1/events/{event['id']}/applications", json={"answers": []})
        assert resp.status_code == 201
        apps[email] = (fan, resp.json())
    return event["id"], apps  # c00, c01 → won / c02 → pending


async def test_checkin_by_id_and_short_code(client, email_outbox, make_client):
    event_id, apps = await _event_with_results(client, email_outbox, make_client)
    _, won1 = apps["c00@example.com"]
    _, won2 = apps["c01@example.com"]

    # application_id で入場 (qr相当)
    resp = await client.post(
        f"/api/v1/events/{event_id}/checkins",
        json={"application_id": won1["id"], "method": "qr"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["short_code"] == won1["id"][:8]

    # short_code で入場 (code)
    resp = await client.post(
        f"/api/v1/events/{event_id}/checkins",
        json={"short_code": won2["id"][:8], "method": "code"},
    )
    assert resp.status_code == 201
    assert resp.json()["application_id"] == won2["id"]

    # 一覧と入場率: won2 / checkin2 → 1.0
    body = (await client.get(f"/api/v1/events/{event_id}/checkins")).json()
    assert body["won_count"] == 2
    assert body["checkin_count"] == 2
    assert body["checkin_rate"] == 1.0
    assert {i["display_name"] for i in body["items"]} == {"来場者00", "来場者01"}


async def test_non_won_rejected(client, email_outbox, make_client):
    event_id, apps = await _event_with_results(client, email_outbox, make_client)
    _, pending = apps["c02@example.com"]

    resp = await client.post(
        f"/api/v1/events/{event_id}/checkins", json={"application_id": pending["id"]}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "precondition_failed"


async def test_duplicate_checkin_409(client, email_outbox, make_client):
    event_id, apps = await _event_with_results(client, email_outbox, make_client)
    _, won1 = apps["c00@example.com"]

    assert (
        await client.post(
            f"/api/v1/events/{event_id}/checkins", json={"application_id": won1["id"]}
        )
    ).status_code == 201
    resp = await client.post(
        f"/api/v1/events/{event_id}/checkins", json={"short_code": won1["id"][:8]}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_checked_in"


async def test_checkin_validation_and_authz(client, email_outbox, make_client):
    event_id, apps = await _event_with_results(client, email_outbox, make_client)
    fan, won1 = apps["c00@example.com"]

    # 不明な short_code → 404
    resp = await client.post(
        f"/api/v1/events/{event_id}/checkins", json={"short_code": "00000000"}
    )
    assert resp.status_code == 404

    # id と short_code の両方指定 / どちらも無し → 400
    resp = await client.post(
        f"/api/v1/events/{event_id}/checkins",
        json={"application_id": won1["id"], "short_code": won1["id"][:8]},
    )
    assert resp.status_code == 400
    resp = await client.post(f"/api/v1/events/{event_id}/checkins", json={})
    assert resp.status_code == 400

    # 参加者 (非member) は入場管理を操作できない → 404
    assert (
        await fan.post(
            f"/api/v1/events/{event_id}/checkins", json={"application_id": won1["id"]}
        )
    ).status_code == 404
    assert (await fan.get(f"/api/v1/events/{event_id}/checkins")).status_code == 404


async def test_checkin_wrong_event_404(client, email_outbox, make_client):
    event_id, apps = await _event_with_results(client, email_outbox, make_client)
    _, won1 = apps["c00@example.com"]

    # 同じ団体の別イベントに対して照合 → 404 (このイベントの応募ではない)
    org2_event = await create_event(
        client,
        (await client.get("/api/v1/auth/me")).json()["organizations"][0]["id"],
        title="別イベント",
    )
    resp = await client.post(
        f"/api/v1/events/{org2_event['id']}/checkins", json={"application_id": won1["id"]}
    )
    assert resp.status_code == 404


async def test_delete_checkin_and_rate(client, email_outbox, make_client):
    event_id, apps = await _event_with_results(client, email_outbox, make_client)
    fan, won1 = apps["c00@example.com"]

    checkin = (
        await client.post(
            f"/api/v1/events/{event_id}/checkins", json={"application_id": won1["id"]}
        )
    ).json()
    body = (await client.get(f"/api/v1/events/{event_id}/checkins")).json()
    assert body["checkin_count"] == 1
    assert body["checkin_rate"] == 0.5  # won2 中 1人入場

    # 非member の取り消し → 404
    assert (await fan.delete(f"/api/v1/checkins/{checkin['id']}")).status_code == 404

    # 取り消し → 集計が戻り、再入場できる
    assert (await client.delete(f"/api/v1/checkins/{checkin['id']}")).status_code == 200
    body = (await client.get(f"/api/v1/events/{event_id}/checkins")).json()
    assert body["checkin_count"] == 0
    assert body["checkin_rate"] == 0.0
    assert (
        await client.post(
            f"/api/v1/events/{event_id}/checkins", json={"short_code": won1["id"][:8]}
        )
    ).status_code == 201
