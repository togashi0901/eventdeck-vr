"""通知サービス (02_抽選仕様書 §5, 03_API仕様書 §2.2 §2.9)。

APIプロセスは notifications 行の作成 (queued) まで。実配信はワーカーの責務。
"""
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND
from app.models import Application, Event, Notification, PushSubscription, User
from app.notify.email import EmailSender
from app.notify.push import PushSender
from app.schemas.notification import (
    BroadcastRequest,
    BroadcastResponse,
    NotificationHistoryResponse,
    NotificationItem,
    NotificationSummaryRow,
)

logger = logging.getLogger(__name__)

ALL_CHANNELS = ("in_app", "email", "push")


async def queue_for_users(
    db: AsyncSession,
    user_ids: list[uuid.UUID],
    *,
    event_id: uuid.UUID | None,
    type_: str,
    title: str,
    body: str,
    channels: tuple[str, ...] | list[str] = ALL_CHANNELS,
) -> int:
    """宛先×チャネルぶんの notifications 行を queued で一括作成する (commitは呼び出し側)。

    in_app / email は宛先全員、push は push_subscriptions を持つユーザーのみ (§5)。
    """
    if not user_ids:
        return 0
    push_users: set[uuid.UUID] = set()
    if "push" in channels:
        push_users = set(
            await db.scalars(
                select(PushSubscription.user_id).where(PushSubscription.user_id.in_(user_ids))
            )
        )
    count = 0
    for user_id in user_ids:
        for channel in channels:
            if channel == "push" and user_id not in push_users:
                continue
            db.add(
                Notification(
                    recipient_id=user_id,
                    event_id=event_id,
                    type=type_,
                    channel=channel,
                    title=title,
                    body=body,
                    status="queued",
                )
            )
            count += 1
    return count


# --- §2.9 主催者からの一斉配信 ---

async def broadcast(
    db: AsyncSession, event: Event, data: BroadcastRequest
) -> BroadcastResponse:
    conditions = [Application.event_id == event.id]
    if data.target == "won":
        conditions.append(Application.status == "won")
    else:  # all_applicants: キャンセル済みを除く全応募者
        conditions.append(Application.status != "canceled")
    user_ids = list(await db.scalars(select(Application.user_id).where(*conditions)))
    queued = await queue_for_users(
        db,
        user_ids,
        event_id=event.id,
        type_=data.type,
        title=data.title,
        body=data.body,
        channels=data.channels,
    )
    await db.commit()
    return BroadcastResponse(queued=queued)


async def history(db: AsyncSession, event: Event) -> NotificationHistoryResponse:
    """配信履歴 (type別・状態別の集計付き §2.9)。"""
    summary_rows = (
        await db.execute(
            select(
                Notification.type,
                Notification.channel,
                Notification.status,
                func.count(),
            )
            .where(Notification.event_id == event.id)
            .group_by(Notification.type, Notification.channel, Notification.status)
            .order_by(Notification.type, Notification.channel, Notification.status)
        )
    ).all()
    items = (
        await db.scalars(
            select(Notification)
            .where(Notification.event_id == event.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).all()
    return NotificationHistoryResponse(
        summary=[
            NotificationSummaryRow(type=t, channel=c, status=s, count=n)
            for t, c, s, n in summary_rows
        ],
        items=[_to_item(n) for n in items],
    )


# --- §2.2 アプリ内通知 ---

def _to_item(n: Notification) -> NotificationItem:
    return NotificationItem(
        id=str(n.id),
        event_id=str(n.event_id) if n.event_id else None,
        type=n.type,
        channel=n.channel,
        title=n.title,
        body=n.body,
        status=n.status,
        read_at=n.read_at,
        created_at=n.created_at,
    )


async def my_notifications(
    db: AsyncSession, user: User, unread_only: bool
) -> list[NotificationItem]:
    conditions = [Notification.recipient_id == user.id, Notification.channel == "in_app"]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    rows = (
        await db.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).all()
    return [_to_item(n) for n in rows]


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user: User) -> NotificationItem:
    n = await db.get(Notification, notification_id)
    if n is None or n.recipient_id != user.id or n.channel != "in_app":
        raise NOT_FOUND
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
        await db.commit()
    return _to_item(n)


# --- push購読 (§2.2) ---

async def register_push(
    db: AsyncSession, user: User, fcm_token: str, user_agent: str | None
) -> None:
    existing = await db.scalar(
        select(PushSubscription).where(PushSubscription.fcm_token == fcm_token)
    )
    if existing is not None:
        existing.user_id = user.id  # トークンが別ユーザーに移った場合も追従
        existing.last_used_at = datetime.now(UTC)
        if user_agent:
            existing.user_agent = user_agent
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                fcm_token=fcm_token,
                user_agent=user_agent,
                last_used_at=datetime.now(UTC),
            )
        )
    await db.commit()


async def unregister_push(db: AsyncSession, user: User, fcm_token: str) -> None:
    existing = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.fcm_token == fcm_token, PushSubscription.user_id == user.id
        )
    )
    if existing is None:
        raise NOT_FOUND
    await db.delete(existing)
    await db.commit()


# --- ワーカー処理 (queued行の配信。worker/main.py から呼ばれる) ---

async def process_queued(
    db: AsyncSession, email_sender: EmailSender, push_sender: PushSender, limit: int = 50
) -> int:
    """queued 行を SKIP LOCKED で取得して配信し sent/failed に更新する。処理件数を返す。"""
    rows = (
        await db.scalars(
            select(Notification)
            .where(Notification.status == "queued")
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for n in rows:
        try:
            if n.channel == "in_app":
                pass  # アプリ内通知はDB行が実体。sent にするだけ
            elif n.channel == "email":
                email = await db.scalar(select(User.email).where(User.id == n.recipient_id))
                if email is None:
                    raise RuntimeError("recipient not found")
                await email_sender.send(to=email, subject=n.title, body=n.body)
            elif n.channel == "push":
                tokens = (
                    await db.scalars(
                        select(PushSubscription.fcm_token).where(
                            PushSubscription.user_id == n.recipient_id
                        )
                    )
                ).all()
                for token in tokens:
                    await push_sender.send(token, n.title, n.body)
            n.status = "sent"
            n.sent_at = datetime.now(UTC)
        except Exception as exc:  # 1件の失敗で他を止めない
            logger.exception("notification %s failed", n.id)
            n.status = "failed"
            n.error_detail = str(exc)[:500]
    await db.commit()
    if rows:
        logger.info("processed %d notifications", len(rows))
    return len(rows)
