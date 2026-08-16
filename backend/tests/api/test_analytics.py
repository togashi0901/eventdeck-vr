"""分析API (§2.10) のテスト: 既知データを投入して期待値照合 (M6 完了条件)。"""
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import text

from tests.factories import (
    create_event,
    create_org,
    publish_event,
    register_and_login,
    setup_profile,
)

OWNER = "owner@example.com"
JST = timezone(timedelta(hours=9))


async def _participant(make_client, email_outbox, email):
    c = make_client()
    await register_and_login(c, email_outbox, email)
    await setup_profile(c, display_name=email.split("@")[0])
    return c


async def _apply(fan, event_id):
    resp = await fan.post(f"/api/v1/events/{event_id}/applications", json={"answers": []})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _known_dataset(client, email_outbox, make_client, db_session):
    """既知データ:
    過去イベントA: f1, f2 が won + 入場済み (団体の入場実績)
    現行イベントB: f1(リピーター), f3 が won / f4 pending / f5 canceled、f1のみ入場
    """
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    # 過去イベントA (先着・定員5)
    event_a = await create_event(
        client, org_id, title="過去イベント", selection_method="first_come", capacity=5
    )
    await publish_event(client, event_a["id"])
    f1 = await _participant(make_client, email_outbox, "f1@example.com")
    f2 = await _participant(make_client, email_outbox, "f2@example.com")
    app_a1 = await _apply(f1, event_a["id"])
    app_a2 = await _apply(f2, event_a["id"])
    for app in (app_a1, app_a2):
        assert app["status"] == "won"
        resp = await client.post(
            f"/api/v1/events/{event_a['id']}/checkins", json={"application_id": app["id"]}
        )
        assert resp.status_code == 201
    # A を過去に移動 (first_timer 評価の「過去イベント」にする)
    await db_session.execute(
        text(
            "UPDATE events SET starts_at = now() - interval '10 day', "
            "ends_at = now() - interval '10 day' + interval '2 hour', "
            "apply_starts_at = now() - interval '20 day', "
            "apply_ends_at = now() - interval '11 day', status = 'finished' "
            "WHERE id = :id"
        ),
        {"id": event_a["id"]},
    )
    await db_session.commit()

    # 現行イベントB (先着・定員2)
    event_b = await create_event(
        client, org_id, title="現行イベント", selection_method="first_come", capacity=2
    )
    await publish_event(client, event_b["id"])
    f3 = await _participant(make_client, email_outbox, "f3@example.com")
    f4 = await _participant(make_client, email_outbox, "f4@example.com")
    f5 = await _participant(make_client, email_outbox, "f5@example.com")
    app_b1 = await _apply(f1, event_b["id"])  # won (リピーター)
    await _apply(f3, event_b["id"])  # won
    await _apply(f4, event_b["id"])  # pending (定員超)
    app_b5 = await _apply(f5, event_b["id"])  # → canceled
    await f5.post(f"/api/v1/applications/{app_b5['id']}/cancel")
    resp = await client.post(
        f"/api/v1/events/{event_b['id']}/checkins", json={"application_id": app_b1["id"]}
    )
    assert resp.status_code == 201

    return org_id, event_a["id"], event_b["id"]


async def test_event_analytics_expected_values(client, email_outbox, make_client, db_session):
    _, _, event_b = await _known_dataset(client, email_outbox, make_client, db_session)

    body = (await client.get(f"/api/v1/events/{event_b}/analytics")).json()
    assert body["applications_total"] == 4
    assert body["by_status"] == {"won": 2, "pending": 1, "canceled": 1}
    assert body["checkin_rate"] == 0.5  # won2 中 1人入場
    assert body["first_timer_rate"] == 0.6667  # {f1,f3,f4} 中 f3,f4 が初参加
    today_jst = datetime.now(UTC).astimezone(JST).date().isoformat()
    assert body["daily_applications"] == [{"date": today_jst, "count": 4}]


async def test_org_summary_expected_values(client, email_outbox, make_client, db_session):
    org_id, event_a, event_b = await _known_dataset(
        client, email_outbox, make_client, db_session
    )

    body = (await client.get(f"/api/v1/orgs/{org_id}/analytics/summary")).json()
    rows = {r["event_id"]: r for r in body["events"]}
    assert rows[event_a]["applications_total"] == 2
    assert rows[event_a]["checkin_count"] == 2
    assert rows[event_a]["checkin_rate"] == 1.0
    assert rows[event_b]["applications_total"] == 4
    assert rows[event_b]["won_count"] == 2
    assert rows[event_b]["checkin_rate"] == 0.5

    # リピート率: 入場ユニーク {f1(2回), f2(1回)} → 1/2
    assert body["unique_attendees"] == 2
    assert body["repeat_attendees"] == 1
    assert body["repeat_rate"] == 0.5


async def test_analytics_member_only(client, email_outbox, make_client, db_session):
    org_id, _, event_b = await _known_dataset(client, email_outbox, make_client, db_session)

    outsider = make_client()
    await register_and_login(outsider, email_outbox, "outsider@example.com")
    assert (await outsider.get(f"/api/v1/events/{event_b}/analytics")).status_code == 404
    assert (
        await outsider.get(f"/api/v1/orgs/{org_id}/analytics/summary")
    ).status_code == 404
