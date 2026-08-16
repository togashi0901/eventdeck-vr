"""メール送信の抽象化 (CLAUDE.md §4)。

dev: MailHog (SMTP) / 本番: SendGrid (同じSMTPインターフェース)。
テストは MemoryEmailSender で送信内容を検証する。実キー前提のコードは書かない。
"""
import asyncio
import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings
from app.core.security import mask_email

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpEmailSender:
    """SMTP実装。dev は MailHog、（将来）本番は SendGrid の SMTP を指す。"""

    async def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.mail_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        await asyncio.to_thread(self._send_sync, msg)
        logger.info("email sent to %s: %s", mask_email(to), subject)

    @staticmethod
    def _send_sync(msg: EmailMessage) -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(msg)


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


@dataclass
class MemoryEmailSender:
    """テスト用: 送信内容をリストに貯める。"""

    sent: list[SentEmail] = field(default_factory=list)

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append(SentEmail(to=to, subject=subject, body=body))


_default_sender: EmailSender = SmtpEmailSender()


def get_email_sender() -> EmailSender:
    """DI用。テストでは dependency_overrides で MemoryEmailSender に差し替える。"""
    return _default_sender
