"""通知ワーカー (別コンテナで起動)。

notifications の queued 行をポーリングし、
- in_app: sent 確定 (DB行が実体)
- email: SMTP送信 (dev: MailHog)
- push: StubPushSender (M6でFCM本結線)
処理本体は app/services/notification.process_queued() (テストはそちらで担保)。
"""
import asyncio
import logging

from app.core.db import SessionLocal
from app.notify.email import get_email_sender
from app.notify.push import get_push_sender
from app.services.notification import process_queued

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 2.0
BATCH_SIZE = 50


async def run() -> None:
    logger.info("notification worker started")
    email_sender = get_email_sender()
    push_sender = get_push_sender()
    while True:
        try:
            async with SessionLocal() as db:
                processed = await process_queued(db, email_sender, push_sender, BATCH_SIZE)
            # 連続処理: キューが空になるまで間隔を空けない
            if processed < BATCH_SIZE:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception:
            logger.exception("worker loop error")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
