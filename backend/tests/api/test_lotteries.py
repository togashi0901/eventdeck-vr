"""抽選API (§2.7, 02_抽選仕様書) のテスト (M4 完了条件)。"""
from sqlalchemy import text

from app.services.lottery_v1 import QuotaConfig, run_lottery
from tests.factories import (
    create_event,
    create_org,
    publish_event,
    register_and_login,
    setup_profile,
)

OWNER = "owner@example.com"

GENERAL = {"name": "general", "label": "一般枠", "count": None, "filter": "all"}


async def _close_applications(db_session, event_id: str) -> None:
    """公開済みイベントの応募締切を過去に移動する (抽選前提条件を満たすため)。"""
    await db_session.execute(
        text(
            "UPDATE events SET apply_starts_at = now() - interval '2 day', "
            "apply_ends_at = now() - interval '1 hour' WHERE id = :id"
        ),
        {"id": event_id},
    )
    await db_session.commit()


async def _lottery_ready(
    client,
    email_outbox,
    make_client,
    db_session,
    *,
    applicants=8,
    capacity=5,
    close=True,
    **event_overrides,
):
    """capacity名のイベントに applicants 名が応募し締切済みの状態を作る。

    returns (event_id, {email: fan_client})
    """
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    event = await create_event(client, org_id, capacity=capacity, **event_overrides)
    await publish_event(client, event["id"])

    fans = {}
    for i in range(applicants):
        email = f"fan{i:02d}@example.com"
        fan = make_client()
        await register_and_login(fan, email_outbox, email)
        await setup_profile(fan, display_name=f"ファン{i:02d}")
        resp = await fan.post(f"/api/v1/events/{event['id']}/applications", json={"answers": []})
        assert resp.status_code == 201, resp.text
        fans[email] = fan
    if close:
        await _close_applications(db_session, event["id"])
    return event["id"], fans


def _body(waitlist_count=0, quotas=None):
    return {"quotas": quotas or [GENERAL], "waitlist_count": waitlist_count}


async def test_preview(client, email_outbox, make_client, db_session):
    event_id, _ = await _lottery_ready(client, email_outbox, make_client, db_session)

    resp = await client.post(f"/api/v1/events/{event_id}/lotteries/preview", json=_body(2))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "target_count": 8,
        "remaining_capacity": 5,
        "quota_matches": {"general": 8},
    }

    # 優先枠 (入場実績なし → 全員 first_timer)
    quotas = [
        {"name": "first_timer", "label": "初参加者優先枠", "count": 2, "filter": "first_timer"},
        GENERAL,
    ]
    resp = await client.post(
        f"/api/v1/events/{event_id}/lotteries/preview", json=_body(2, quotas)
    )
    assert resp.json()["quota_matches"] == {"first_timer": 8, "general": 8}

    # 枠合計 > 残定員 → 422
    over = [{"name": "a", "count": 6, "filter": "all"}]
    resp = await client.post(f"/api/v1/events/{event_id}/lotteries/preview", json=_body(0, over))
    assert resp.status_code == 422


async def test_preconditions_409(client, email_outbox, make_client, db_session):
    # 締切前 → 409
    event_id, _ = await _lottery_ready(
        client, email_outbox, make_client, db_session, applicants=1, close=False
    )
    resp = await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "precondition_failed"

    # first_come → 409 (memberとして自分の団体に作成)
    org2 = await create_org(client, slug="org-fc")
    fc = await create_event(client, org2, selection_method="first_come")
    await publish_event(client, fc["id"])
    await _close_applications(db_session, fc["id"])
    resp = await client.post(f"/api/v1/events/{fc['id']}/lotteries", json=_body())
    assert resp.status_code == 409

    # 応募0件 → 409
    org3 = await create_org(client, slug="org-empty")
    empty = await create_event(client, org3)
    await publish_event(client, empty["id"])
    await _close_applications(db_session, empty["id"])
    resp = await client.post(f"/api/v1/events/{empty['id']}/lotteries", json=_body())
    assert resp.status_code == 409

    # 非member → 404
    other = make_client()
    await register_and_login(other, email_outbox, "outsider@example.com")
    resp = await other.post(f"/api/v1/events/{event_id}/lotteries", json=_body())
    assert resp.status_code == 404


async def test_execute_transaction_integrity(client, email_outbox, make_client, db_session):
    """§5: lotteries + lottery_results + applications + notifications の整合。"""
    event_id, fans = await _lottery_ready(client, email_outbox, make_client, db_session)

    resp = await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(2))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["round"] == 1
    assert (body["won"], body["waitlisted"], body["lost"]) == (5, 2, 1)

    # lotteries 行
    lot = (
        await db_session.execute(
            text("SELECT seed, winner_quota, waitlist_quota, config FROM lotteries WHERE id = :id"),
            {"id": body["lottery_id"]},
        )
    ).one()
    assert lot.winner_quota == 5 and lot.waitlist_quota == 2

    # lottery_results: 全対象8件、draw_rank は 1..8 の順列
    ranks = (
        await db_session.execute(
            text("SELECT draw_rank FROM lottery_results WHERE lottery_id = :id"),
            {"id": body["lottery_id"]},
        )
    ).scalars().all()
    assert sorted(ranks) == list(range(1, 9))

    # applications が results と一致 / pending が残らない (§6 round1)
    rows = (
        await db_session.execute(
            text(
                "SELECT a.status, lr.result FROM applications a "
                "JOIN lottery_results lr ON lr.application_id = a.id "
                "WHERE lr.lottery_id = :id"
            ),
            {"id": body["lottery_id"]},
        )
    ).all()
    assert all(status == result for status, result in rows)
    pending = (
        await db_session.execute(
            text("SELECT count(*) FROM applications WHERE event_id = :e AND status = 'pending'"),
            {"e": event_id},
        )
    ).scalar()
    assert pending == 0

    # notifications: in_app 8 + email 8 (push購読なし) = 16 queued
    counts = dict(
        (
            await db_session.execute(
                text(
                    "SELECT channel, count(*) FROM notifications "
                    "WHERE event_id = :e GROUP BY channel"
                ),
                {"e": event_id},
            )
        ).all()
    )
    assert counts == {"in_app": 8, "email": 8}

    # 参加者のマイページに結果が反映される
    statuses = set()
    for fan in fans.values():
        mine = (await fan.get("/api/v1/me/applications")).json()
        statuses.add(mine[0]["status"])
        notif = (await fan.get("/api/v1/me/notifications")).json()
        assert len(notif) == 1  # in_app 結果通知
    assert statuses == {"won", "waitlisted", "lost"}


async def test_reproduction_from_saved_seed(client, email_outbox, make_client, db_session):
    """§8: 保存済み seed + config + 対象集合から run_lottery を再実行し結果一致。"""
    event_id, _ = await _lottery_ready(client, email_outbox, make_client, db_session)
    body = (
        await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(2))
    ).json()

    lot = (
        await db_session.execute(
            text("SELECT seed, config FROM lotteries WHERE id = :id"),
            {"id": body["lottery_id"]},
        )
    ).one()
    saved = (
        await db_session.execute(
            text(
                "SELECT application_id, result, draw_rank, quota_name "
                "FROM lottery_results WHERE lottery_id = :id"
            ),
            {"id": body["lottery_id"]},
        )
    ).all()

    quotas = [
        QuotaConfig(name=q["name"], count=q["count"], filter=q["filter"])
        for q in lot.config["quotas"]
    ]
    reproduced = run_lottery(
        application_ids=[str(r.application_id) for r in saved],
        quotas=quotas,
        remaining_capacity=5,
        waitlist_count=lot.config["waitlist_count"],
        seed=lot.seed,
        is_match=lambda a, f: True,
    )
    reproduced_by_id = {r.application_id: r for r in reproduced}
    for row in saved:
        rep = reproduced_by_id[str(row.application_id)]
        assert (rep.result, rep.draw_rank, rep.quota_name) == (
            row.result,
            row.draw_rank,
            row.quota_name,
        )


async def _find_fans_by_status(fans, status):
    result = []
    for email, fan in fans.items():
        mine = (await fan.get("/api/v1/me/applications")).json()
        if mine[0]["status"] == status:
            result.append((email, fan, mine[0]))
    return result


async def test_cancel_won_triggers_promotion(client, email_outbox, make_client, db_session):
    """won→canceled で繰り上げ + promoted 通知 (§7)。"""
    event_id, fans = await _lottery_ready(client, email_outbox, make_client, db_session)
    body = (await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(2))).json()

    # 補欠のdraw_rank順を控える
    results = (
        await client.get(f"/api/v1/lotteries/{body['lottery_id']}/results?per_page=100")
    ).json()["items"]
    waitlist_order = [
        r["application_id"]
        for r in sorted(
            (r for r in results if r["result"] == "waitlisted"),
            key=lambda r: r["draw_rank"],
        )
    ]

    # 当選者1人がキャンセル → 補欠1位が自動で won (promoted)
    won = await _find_fans_by_status(fans, "won")
    _, won_fan, won_app = won[0]
    resp = await won_fan.post(f"/api/v1/applications/{won_app['id']}/cancel")
    assert resp.status_code == 200

    promoted = (
        await db_session.execute(
            text(
                "SELECT id, promoted FROM applications WHERE event_id = :e AND status = 'won' "
                "AND promoted = true"
            ),
            {"e": event_id},
        )
    ).all()
    assert len(promoted) == 1
    assert str(promoted[0].id) == waitlist_order[0]  # draw_rank 最上位が繰り上がる

    # promoted 通知が queued されている (in_app + email)
    notif = (
        await db_session.execute(
            text(
                "SELECT channel, count(*) FROM notifications "
                "WHERE event_id = :e AND type = 'promoted' GROUP BY channel"
            ),
            {"e": event_id},
        )
    ).all()
    assert dict(notif) == {"in_app": 1, "email": 1}

    # 2人目のキャンセル → 補欠2位が繰り上がる (順序検証)
    won = await _find_fans_by_status(fans, "won")
    target = [w for w in won if not w[2]["promoted"]][0]
    await target[1].post(f"/api/v1/applications/{target[2]['id']}/cancel")
    promoted_ids = (
        await db_session.execute(
            text(
                "SELECT id FROM applications WHERE event_id = :e AND promoted = true "
                "AND status = 'won'"
            ),
            {"e": event_id},
        )
    ).scalars().all()
    assert set(map(str, promoted_ids)) == set(waitlist_order)


async def test_manual_promote(client, email_outbox, make_client, db_session):
    event_id, fans = await _lottery_ready(client, email_outbox, make_client, db_session)
    body = (await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(2))).json()
    results = (
        await client.get(f"/api/v1/lotteries/{body['lottery_id']}/results?per_page=100")
    ).json()["items"]
    waitlist_order = [
        r["application_id"]
        for r in sorted(
            (r for r in results if r["result"] == "waitlisted"),
            key=lambda r: r["draw_rank"],
        )
    ]

    # 残定員0のうちは繰り上げ不可 → 409
    resp = await client.post(f"/api/v1/applications/{waitlist_order[0]}/promote")
    assert resp.status_code == 409

    # 定員+1 して残定員を作る (published後の増加は可)
    ev = (await client.get(f"/api/v1/events/{event_id}")).json()
    update = {
        k: ev[k]
        for k in (
            "title", "description", "platform", "world_name", "world_url",
            "starts_at", "ends_at", "selection_method",
            "apply_starts_at", "apply_ends_at", "visibility", "header_image_url",
        )
    }
    resp = await client.put(f"/api/v1/events/{event_id}", json={**update, "capacity": 6})
    assert resp.status_code == 200

    # 候補2位の指名繰り上げ → 409 / 候補1位 → 200
    resp = await client.post(f"/api/v1/applications/{waitlist_order[1]}/promote")
    assert resp.status_code == 409
    resp = await client.post(f"/api/v1/applications/{waitlist_order[0]}/promote")
    assert resp.status_code == 200

    row = (
        await db_session.execute(
            text("SELECT status, promoted FROM applications WHERE id = :id"),
            {"id": waitlist_order[0]},
        )
    ).one()
    assert (row.status, row.promoted) == ("won", True)


async def test_round2_revival(client, email_outbox, make_client, db_session):
    """§6: 補欠なし・残定員ありのとき lost を対象に round 2 を実行できる。"""
    event_id, fans = await _lottery_ready(client, email_outbox, make_client, db_session)
    await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(0))  # 補欠なし

    # 当選者1人キャンセル (補欠がいないので繰り上げは起きない) → 残定員1
    won = await _find_fans_by_status(fans, "won")
    _, won_fan, won_app = won[0]
    await won_fan.post(f"/api/v1/applications/{won_app['id']}/cancel")

    resp = await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(0))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["round"] == 2
    assert body["won"] == 1  # 残定員1を lost 3人から選出
    assert body["lost"] == 2

    # 履歴に2ラウンド
    history = (await client.get(f"/api/v1/events/{event_id}/lotteries")).json()
    assert [h["round"] for h in history] == [1, 2]

    # round2 当選者は promoted=false (§6: 繰り上げではなく再抽選当選)
    revived = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM applications WHERE event_id = :e AND status='won' "
                "AND promoted = true"
            ),
            {"e": event_id},
        )
    ).scalar()
    assert revived == 0


async def test_results_member_only(client, email_outbox, make_client, db_session):
    event_id, fans = await _lottery_ready(
        client, email_outbox, make_client, db_session, applicants=3, capacity=2
    )
    body = (await client.post(f"/api/v1/events/{event_id}/lotteries", json=_body(1))).json()

    fan = next(iter(fans.values()))
    resp = await fan.get(f"/api/v1/lotteries/{body['lottery_id']}/results")
    assert resp.status_code == 404  # 参加者からは見えない

    resp = await client.get(f"/api/v1/lotteries/{body['lottery_id']}/results?per_page=2&page=2")
    assert resp.status_code == 200
    assert resp.json()["meta"] == {"page": 2, "per_page": 2, "total": 3}
