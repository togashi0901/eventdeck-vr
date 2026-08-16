"""通知API (§2.2, §2.9) とワーカー処理のテスト (M4)。"""
from sqlalchemy import text

from app.notify.email import MemoryEmailSender
from app.notify.push import StubPushSender
from app.services.notification import process_queued
from tests.factories import (
    create_event,
    create_org,
    publish_event,
    register_and_login,
    setup_profile,
)

OWNER = "owner@example.com"


async def _event_with_applicants(client, email_outbox, make_client, n=3, **overrides):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(
        client, org_id, selection_method="first_come", capacity=2, **overrides
    )
    await publish_event(client, event["id"])
    fans = {}
    for i in range(n):
        email = f"n{i:02d}@example.com"
        fan = make_client()
        await register_and_login(fan, email_outbox, email)
        await setup_profile(fan, display_name=f"参加者{i:02d}")
        resp = await fan.post(f"/api/v1/events/{event['id']}/applications", json={"answers": []})
        assert resp.status_code == 201
        fans[email] = fan
    return event["id"], fans  # first_come capacity2: won 2, pending 1


async def test_broadcast_targets_and_channels(client, email_outbox, make_client):
    event_id, _ = await _event_with_applicants(client, email_outbox, make_client)

    # won のみ × in_app のみ → 2件
    resp = await client.post(
        f"/api/v1/events/{event_id}/notifications",
        json={
            "type": "reminder",
            "target": "won",
            "title": "リマインダー",
            "body": "明日開催です",
            "channels": ["in_app"],
        },
    )
    assert resp.status_code == 201
    assert resp.json() == {"queued": 2}

    # 全応募者 × in_app + email → 3人 × 2ch = 6件
    resp = await client.post(
        f"/api/v1/events/{event_id}/notifications",
        json={
            "type": "announcement",
            "target": "all_applicants",
            "title": "お知らせ",
            "body": "会場が変わりました",
            "channels": ["in_app", "email"],
        },
    )
    assert resp.json() == {"queued": 6}

    # 履歴集計
    history = (await client.get(f"/api/v1/events/{event_id}/notifications")).json()
    summary = {(s["type"], s["channel"], s["status"]): s["count"] for s in history["summary"]}
    assert summary[("reminder", "in_app", "queued")] == 2
    assert summary[("announcement", "email", "queued")] == 3


async def test_broadcast_member_only(client, email_outbox, make_client):
    event_id, fans = await _event_with_applicants(client, email_outbox, make_client)
    fan = next(iter(fans.values()))
    resp = await fan.post(
        f"/api/v1/events/{event_id}/notifications",
        json={
            "type": "reminder",
            "target": "won",
            "title": "x",
            "body": "y",
            "channels": ["in_app"],
        },
    )
    assert resp.status_code == 404


async def test_my_notifications_and_mark_read(client, email_outbox, make_client):
    event_id, fans = await _event_with_applicants(client, email_outbox, make_client)
    await client.post(
        f"/api/v1/events/{event_id}/notifications",
        json={
            "type": "announcement",
            "target": "all_applicants",
            "title": "お知らせ",
            "body": "本文",
            "channels": ["in_app", "email"],
        },
    )
    fan = next(iter(fans.values()))
    items = (await fan.get("/api/v1/me/notifications")).json()
    assert len(items) == 1  # in_app のみが一覧に出る (emailは出ない)
    assert items[0]["title"] == "お知らせ"
    assert items[0]["read_at"] is None

    # 未読フィルタ → 既読化 → 未読0
    assert len((await fan.get("/api/v1/me/notifications?unread_only=true")).json()) == 1
    resp = await fan.post(f"/api/v1/me/notifications/{items[0]['id']}/read")
    assert resp.status_code == 200
    assert resp.json()["read_at"] is not None
    assert (await fan.get("/api/v1/me/notifications?unread_only=true")).json() == []

    # 他人の通知は既読化できない
    other = list(fans.values())[1]
    resp = await other.post(f"/api/v1/me/notifications/{items[0]['id']}/read")
    assert resp.status_code == 404


async def test_push_subscription_roundtrip(client, email_outbox, make_client, db_session):
    event_id, fans = await _event_with_applicants(client, email_outbox, make_client, n=2)
    fan = next(iter(fans.values()))

    resp = await fan.post(
        "/api/v1/me/push-subscriptions",
        json={"fcm_token": "tok-abc", "user_agent": "TestBrowser"},
    )
    assert resp.status_code == 201
    # 同一トークン再登録は upsert (エラーにならない)
    assert (
        await fan.post("/api/v1/me/push-subscriptions", json={"fcm_token": "tok-abc"})
    ).status_code == 201

    # 購読者には push 行も queued される
    resp = await client.post(
        f"/api/v1/events/{event_id}/notifications",
        json={
            "type": "reminder",
            "target": "all_applicants",
            "title": "t",
            "body": "b",
            "channels": ["push"],
        },
    )
    assert resp.json() == {"queued": 1}  # 購読者1人分のみ

    assert (
        await fan.delete("/api/v1/me/push-subscriptions/tok-abc")
    ).status_code == 200
    assert (
        await fan.delete("/api/v1/me/push-subscriptions/tok-abc")
    ).status_code == 404


async def test_event_cancel_queues_notifications(client, email_outbox, make_client, db_session):
    """イベント中止で全応募者へ event_canceled 通知が積まれる (§2.4)。"""
    event_id, _ = await _event_with_applicants(client, email_outbox, make_client)

    resp = await client.post(f"/api/v1/events/{event_id}/cancel")
    assert resp.status_code == 200

    counts = dict(
        (
            await db_session.execute(
                text(
                    "SELECT channel, count(*) FROM notifications "
                    "WHERE event_id = :e AND type = 'event_canceled' GROUP BY channel"
                ),
                {"e": event_id},
            )
        ).all()
    )
    assert counts == {"in_app": 3, "email": 3}


async def test_worker_process_queued(client, email_outbox, make_client, db_session):
    """ワーカー処理: queued → in_app/email/push を配信して sent にする。"""
    event_id, fans = await _event_with_applicants(client, email_outbox, make_client, n=2)
    fan = next(iter(fans.values()))
    await fan.post("/api/v1/me/push-subscriptions", json={"fcm_token": "tok-w"})

    await client.post(
        f"/api/v1/events/{event_id}/notifications",
        json={
            "type": "announcement",
            "target": "all_applicants",
            "title": "配信テスト",
            "body": "本文",
            "channels": ["in_app", "email", "push"],
        },
    )  # 2人×(in_app+email) + push1 = 5件

    worker_email = MemoryEmailSender()
    processed = await process_queued(db_session, worker_email, StubPushSender(), limit=50)
    assert processed == 5

    # email は2通、宛先は応募者
    assert len(worker_email.sent) == 2
    assert {m.subject for m in worker_email.sent} == {"配信テスト"}

    # 全行 sent / queued は残らない
    statuses = (
        await db_session.execute(
            text("SELECT status, count(*) FROM notifications WHERE event_id = :e GROUP BY status"),
            {"e": event_id},
        )
    ).all()
    assert dict(statuses) == {"sent": 5}
