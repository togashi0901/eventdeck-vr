"""pytest 共通フィクスチャ。

テスト用DB (eventdeck_test) をセッションごとに作成・破棄する (04計画 M0)。
- スキーマ適用は同期 psycopg で db/schema.sql を丸ごと流す (複数ステートメント対応)。
- 実際のクエリ用には async セッション (asyncpg) を払い出す。
DB へ接続できない環境ではDB依存テストを skip し、純粋ロジックのテストは通す。
"""
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_session
from app.core.redis import redis_client
from app.main import app
from app.notify.email import MemoryEmailSender, get_email_sender

TEST_DB = "eventdeck_test"

# テスト中に使い捨てる Redis キーの接頭辞 (テスト間の独立性を保つ)
VOLATILE_REDIS_PREFIXES = ("rl:", "session:", "email_verify:", "password_reset:")


def _repo_root() -> Path:
    # backend/tests/conftest.py -> parents[2] がリポジトリ相当 (コンテナでは /)
    return Path(__file__).resolve().parents[2]


def _schema_sql() -> str:
    for path in (_repo_root() / "db" / "schema.sql", Path("/db/schema.sql")):
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError("db/schema.sql が見つかりません")


def _sync_url(dbname: str) -> str:
    base = settings.database_url.replace("+asyncpg", "+psycopg").rpartition("/")[0]
    return f"{base}/{dbname}"


def _async_url(dbname: str) -> str:
    return f"{settings.database_url.rpartition('/')[0]}/{dbname}"


@pytest.fixture(scope="session")
def test_db() -> None:
    """テスト用DBを作成しスキーマを適用する。終了時に破棄する。"""
    admin = create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {TEST_DB}")
            conn.exec_driver_sql(f"CREATE DATABASE {TEST_DB}")
    except OperationalError:
        admin.dispose()
        pytest.skip("PostgreSQL に接続できないため DB 依存テストをスキップ")
    admin.dispose()

    schema_engine = create_engine(_sync_url(TEST_DB))
    with schema_engine.begin() as conn:
        # psycopg の '%' プレースホルダ走査を避ける (0001_initial_schema と同じ理由)
        conn.exec_driver_sql(_schema_sql().replace("%", "%%"))
    schema_engine.dispose()

    yield

    admin = create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {TEST_DB}")
    admin.dispose()


@pytest_asyncio.fixture
async def db_session(test_db) -> AsyncSession:
    """テスト用DBへの async セッション。"""
    engine = create_async_engine(_async_url(TEST_DB))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def email_outbox() -> MemoryEmailSender:
    """テスト用メール送信 (送信内容をリストに貯める)。"""
    return MemoryEmailSender()


@pytest_asyncio.fixture
async def client(test_db, email_outbox):
    """テストDB・メモリメール送信に差し替えたAPIクライアント。

    - X-Requested-With を既定付与 (CSRF 対策ヘッダ。無しの検証は素の httpx で行う)
    - テーブルと揮発性 Redis キーを毎テスト初期化する
    """
    engine = create_async_engine(_async_url(TEST_DB))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, organizations CASCADE"))
    for prefix in VOLATILE_REDIS_PREFIXES:
        async for key in redis_client.scan_iter(f"{prefix}*"):
            await redis_client.delete(key)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_email_sender] = lambda: email_outbox
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def make_client(client):
    """追加ユーザー用クライアントのファクトリ (client と同じ差し替え済みappを共有)。"""
    clients: list[httpx.AsyncClient] = []

    def _make() -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        c = httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        clients.append(c)
        return c

    yield _make
    for c in clients:
        await c.aclose()
