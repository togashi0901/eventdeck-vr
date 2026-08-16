"""プッシュ送信の抽象化 (CLAUDE.md §4)。

FCM_CREDENTIALS_JSON が空なら StubPushSender (ログ出力+sent扱い)。
本結線 (FcmPushSender) は M6 で実装する。
"""
import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class PushSender(Protocol):
    async def send(self, fcm_token: str, title: str, body: str) -> None: ...


class StubPushSender:
    """dev用スタブ: 送信内容をログに出して成功扱いにする。"""

    async def send(self, fcm_token: str, title: str, body: str) -> None:
        logger.info("[stub push] token=%s... title=%s", fcm_token[:12], title)


_default_sender: PushSender = StubPushSender()


def get_push_sender() -> PushSender:
    if settings.fcm_credentials_json:
        # TODO(M6): FcmPushSender を実装して返す
        logger.warning("FCM credentials present but FcmPushSender is not implemented until M6")
    return _default_sender
