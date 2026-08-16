"""スキーマ適用のスモークテスト (M0)。

db/schema.sql を適用したテスト用DBに 13 テーブルが揃っていることを確認する。
"""
from sqlalchemy import text

EXPECTED_TABLES = {
    "users",
    "user_profiles",
    "organizations",
    "organization_members",
    "events",
    "form_items",
    "applications",
    "application_answers",
    "lotteries",
    "lottery_results",
    "notifications",
    "push_subscriptions",
    "checkins",
}


async def test_schema_has_13_tables(db_session):
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
    )
    tables = {row[0] for row in result}
    assert EXPECTED_TABLES <= tables
    assert len(EXPECTED_TABLES) == 13
