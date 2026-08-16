"""団体API (§2.3) のテスト (M2 完了条件)。"""
from tests.factories import create_org, register_and_login

OWNER = "owner@example.com"
OTHER = "other@example.com"


async def test_create_org_creator_becomes_owner(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client, slug="my-team", name="マイチーム")

    # me に owner として現れる
    me = (await client.get("/api/v1/auth/me")).json()
    assert me["organizations"] == [{"id": org_id, "name": "マイチーム", "role": "owner"}]

    # 管理用詳細・メンバー一覧
    resp = await client.get(f"/api/v1/orgs/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-team"
    members = (await client.get(f"/api/v1/orgs/{org_id}/members")).json()
    assert len(members) == 1
    assert members[0]["email"] == OWNER
    assert members[0]["role"] == "owner"


async def test_create_org_requires_login(client):
    resp = await client.post("/api/v1/organizations", json={"name": "x", "slug": "abc"})
    assert resp.status_code == 401


async def test_create_org_slug_validation_and_duplicate(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    for bad in ["AB", "-bad", "bad-", "日本語", "a"]:
        resp = await client.post("/api/v1/organizations", json={"name": "x", "slug": bad})
        assert resp.status_code == 400, bad
    await create_org(client, slug="dup-slug")
    resp = await client.post("/api/v1/organizations", json={"name": "x", "slug": "dup-slug"})
    assert resp.status_code == 409


async def test_non_member_gets_404(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    other = make_client()
    await register_and_login(other, email_outbox, OTHER)
    assert (await other.get(f"/api/v1/orgs/{org_id}")).status_code == 404
    assert (await other.get(f"/api/v1/orgs/{org_id}/members")).status_code == 404
    resp = await other.put(f"/api/v1/orgs/{org_id}", json={"name": "hack"})
    assert resp.status_code == 404


async def test_member_add_and_remove(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    other = make_client()
    await register_and_login(other, email_outbox, OTHER)

    # owner が member を追加
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"email": OTHER, "role": "member"}
    )
    assert resp.status_code == 201
    other_me = (await other.get("/api/v1/auth/me")).json()
    assert other_me["organizations"][0]["id"] == org_id
    assert other_me["organizations"][0]["role"] == "member"

    # member はメンバー追加不可 (owner権限なし → 404)
    resp = await other.post(
        f"/api/v1/orgs/{org_id}/members", json={"email": "x@example.com", "role": "member"}
    )
    assert resp.status_code == 404

    # member は org 更新不可 / 閲覧は可
    assert (await other.put(f"/api/v1/orgs/{org_id}", json={"name": "x"})).status_code == 404
    assert (await other.get(f"/api/v1/orgs/{org_id}")).status_code == 200

    # 除名 → me から消える
    user_id = other_me["id"]
    resp = await client.delete(f"/api/v1/orgs/{org_id}/members/{user_id}")
    assert resp.status_code == 200
    other_me = (await other.get("/api/v1/auth/me")).json()
    assert other_me["organizations"] == []


async def test_add_member_errors(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    # 未登録メール → 404
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"email": "ghost@example.com", "role": "member"}
    )
    assert resp.status_code == 404

    # すでにメンバー (自分) → 409
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"email": OWNER, "role": "member"}
    )
    assert resp.status_code == 409


async def test_last_owner_cannot_be_removed(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)
    me = (await client.get("/api/v1/auth/me")).json()

    resp = await client.delete(f"/api/v1/orgs/{org_id}/members/{me['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_two_owners_one_can_leave(client, email_outbox, make_client):
    await register_and_login(client, email_outbox, OWNER)
    org_id = await create_org(client)

    other = make_client()
    await register_and_login(other, email_outbox, OTHER)
    await client.post(f"/api/v1/orgs/{org_id}/members", json={"email": OTHER, "role": "owner"})

    me = (await client.get("/api/v1/auth/me")).json()
    resp = await client.delete(f"/api/v1/orgs/{org_id}/members/{me['id']}")
    assert resp.status_code == 200  # owner が2人なら片方は抜けられる


async def test_public_org_page(client, email_outbox):
    await register_and_login(client, email_outbox, OWNER)
    await create_org(client, slug="pub-team", name="公開チーム")

    resp = await client.get("/api/v1/organizations/pub-team")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "公開チーム"
    assert body["events"] == []

    assert (await client.get("/api/v1/organizations/no-such-team")).status_code == 404
