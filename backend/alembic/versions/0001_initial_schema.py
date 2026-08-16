"""initial schema (db/schema.sql と一致)

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-09

初期リビジョンは db/schema.sql を丸ごと適用する。
これにより「alembic upgrade head 後のテーブル定義が schema.sql と一致する」
(04計画 M0 完了条件) が構成上保証される。
以降のスキーマ変更は 01_DB設計書 更新 → 新規マイグレーション の順で行う (不変条件7)。
"""
import os
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema_sql() -> str:
    here = Path(__file__).resolve()
    candidates = [
        Path(os.environ["SCHEMA_SQL_PATH"]) if os.environ.get("SCHEMA_SQL_PATH") else None,
        here.parents[3] / "db" / "schema.sql",  # コンテナ(/db)・ローカル(repo/db) 双方に解決
        Path("/db/schema.sql"),
    ]
    for path in candidates:
        if path and path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError("db/schema.sql が見つかりません (SCHEMA_SQL_PATH で指定可)")


# schema.sql の順序と逆順で破棄する
_TABLES = [
    "checkins",
    "push_subscriptions",
    "notifications",
    "lottery_results",
    "lotteries",
    "application_answers",
    "applications",
    "form_items",
    "events",
    "organization_members",
    "organizations",
    "user_profiles",
    "users",
]


def upgrade() -> None:
    # psycopg は SQL 中の '%' をプレースホルダとして走査する。schema.sql の
    # DO ブロック内 format('... %I ...') が誤検知されるため '%%' にエスケープする
    # (psycopg がサーバ送信前に '%' へ戻すので DDL の意味は変わらない)。
    sql = _schema_sql().replace("%", "%%")
    op.get_bind().exec_driver_sql(sql)


def downgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table} CASCADE")
    conn.exec_driver_sql("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
