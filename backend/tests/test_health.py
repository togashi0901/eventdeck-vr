"""healthz エンドポイントのテスト (M0)。

DB・Redis が疎通していれば {"status":"ok","db":true,"redis":true} を返す。
"""
import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_healthz_shape():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "db", "redis"}
    assert isinstance(body["db"], bool)
    assert isinstance(body["redis"], bool)
