"""イベントAPI (§2.4) のテスト (M2 完了条件)。"""
from datetime import UTC, datetime, timedelta

from tests.factories import create_event, create_org, event_payload, register_and_login

OWNER = "owner@example.com"
OTHER = "other@example.com"


def iso(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


async def test_event_crud(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    event = await create_event(client, org_id, title="CRUDイベント")
    assert event["status"] == "draft"
    event_id = event["id"]

    # member は draft を閲覧できる
    resp = await client.get(f"/api/v1/events/{event_id}")
    assert resp.status_code == 200

    # 更新
    resp = await client.put(
        f"/api/v1/events/{event_id}", json=event_payload(title="改題イベント", capacity=8)
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "改題イベント"
    assert resp.json()["capacity"] == 8

    # ダッシュボード一覧と status フィルタ
    events = (await client.get(f"/api/v1/orgs/{org_id}/events")).json()
    assert [e["id"] for e in events] == [event_id]
    assert (await client.get(f"/api/v1/orgs/{org_id}/events?status=draft")).json() != []
    assert (await client.get(f"/api/v1/orgs/{org_id}/events?status=published")).json() == []


async def test_event_create_invalid_times_422(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    # 応募締切が開催開始より後
    bad = event_payload(
        apply_ends_at=iso(timedelta(days=20)),  # starts_at (+14d) より後
    )
    resp = await client.post(f"/api/v1/orgs/{org_id}/events", json=bad)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unprocessable"

    # 終了が開始より前
    bad = event_payload(ends_at=iso(timedelta(days=13)))
    resp = await client.post(f"/api/v1/orgs/{org_id}/events", json=bad)
    assert resp.status_code == 422


async def test_draft_event_hidden_from_public(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id)

    # 未ログイン → 404 / 非member → 404 / 公開一覧に出ない
    anon = make_client()
    assert (await anon.get(f"/api/v1/events/{event['id']}")).status_code == 404

    other = make_client()
    await register_and_login(other, email_outbox, OTHER)
    assert (await other.get(f"/api/v1/events/{event['id']}")).status_code == 404

    listing = (await anon.get("/api/v1/events")).json()
    assert listing["items"] == []
    assert listing["meta"]["total"] == 0


async def test_publish_flow(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client, slug="pub-flow")
    event = await create_event(client, org_id)

    resp = await client.post(f"/api/v1/events/{event['id']}/publish")
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # 再公開は 409
    resp = await client.post(f"/api/v1/events/{event['id']}/publish")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "precondition_failed"

    # 未ログインでも一覧・詳細・団体公開ページで見える
    anon = make_client()
    listing = (await anon.get("/api/v1/events")).json()
    assert listing["meta"]["total"] == 1
    assert listing["items"][0]["id"] == event["id"]
    detail = (await anon.get(f"/api/v1/events/{event['id']}")).json()
    assert detail["status"] == "published"
    assert detail["application_state"] is None  # 未ログインには含めない
    org_page = (await anon.get("/api/v1/organizations/pub-flow")).json()
    assert [e["id"] for e in org_page["events"]] == [event["id"]]


async def test_publish_past_apply_deadline_422(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    # 時系列の相互関係は正しいが、全て過去のイベント
    event = await create_event(
        client,
        org_id,
        apply_starts_at=iso(timedelta(days=-10)),
        apply_ends_at=iso(timedelta(days=-5)),
        starts_at=iso(timedelta(days=-4)),
        ends_at=iso(timedelta(days=-3)),
    )
    resp = await client.post(f"/api/v1/events/{event['id']}/publish")
    assert resp.status_code == 422


async def test_capacity_cannot_decrease_after_publish(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id, capacity=5)
    await client.post(f"/api/v1/events/{event['id']}/publish")

    # 減少 → 422
    resp = await client.put(f"/api/v1/events/{event['id']}", json=event_payload(capacity=4))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unprocessable"

    # 増加は OK
    resp = await client.put(f"/api/v1/events/{event['id']}", json=event_payload(capacity=10))
    assert resp.status_code == 200
    assert resp.json()["capacity"] == 10


async def test_unlisted_event_not_listed_but_accessible(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id, visibility="unlisted")
    await client.post(f"/api/v1/events/{event['id']}/publish")

    anon = make_client()
    listing = (await anon.get("/api/v1/events")).json()
    assert listing["items"] == []  # 一覧には出ない
    resp = await anon.get(f"/api/v1/events/{event['id']}")
    assert resp.status_code == 200  # URLを知っていれば見える


async def test_cancel_event(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id)
    await client.post(f"/api/v1/events/{event['id']}/publish")

    resp = await client.post(f"/api/v1/events/{event['id']}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"

    # canceled は public からは見えない (member は見える)
    anon = make_client()
    assert (await anon.get(f"/api/v1/events/{event['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/events/{event['id']}")).status_code == 200

    # 再中止は 409
    assert (await client.post(f"/api/v1/events/{event['id']}/cancel")).status_code == 409


async def test_non_member_cannot_mutate_event(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id)

    other = make_client()
    await register_and_login(other, email_outbox, OTHER)
    assert (
        await other.put(f"/api/v1/events/{event['id']}", json=event_payload())
    ).status_code == 404
    assert (await other.post(f"/api/v1/events/{event['id']}/publish")).status_code == 404
    resp = await other.post(f"/api/v1/orgs/{org_id}/events", json=event_payload())
    assert resp.status_code == 404
    assert (await other.get(f"/api/v1/orgs/{org_id}/events")).status_code == 404


async def test_public_list_filters_and_paging(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    e1 = await create_event(client, org_id, title="VR音楽ライブ", platform="vrchat")
    e2 = await create_event(client, org_id, title="cluster交流会", platform="cluster")
    for e in (e1, e2):
        assert (await client.post(f"/api/v1/events/{e['id']}/publish")).status_code == 200

    anon = make_client()
    assert (await anon.get("/api/v1/events")).json()["meta"]["total"] == 2
    listing = (await anon.get("/api/v1/events?platform=cluster")).json()
    assert [e["id"] for e in listing["items"]] == [e2["id"]]
    listing = (await anon.get("/api/v1/events?q=音楽")).json()
    assert [e["id"] for e in listing["items"]] == [e1["id"]]
    listing = (await anon.get("/api/v1/events?per_page=1&page=2")).json()
    assert len(listing["items"]) == 1
    assert listing["meta"] == {"page": 2, "per_page": 1, "total": 2}


async def test_application_state_for_logged_in_user(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id)
    await client.post(f"/api/v1/events/{event['id']}/publish")

    other = make_client()
    await register_and_login(other, email_outbox, OTHER)
    detail = (await other.get(f"/api/v1/events/{event['id']}")).json()
    # 応募はM3実装。ログイン済みには未応募として含める
    assert detail["application_state"] == {"applied": False, "status": None}
