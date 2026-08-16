"""抽選サービス (02_抽選仕様書 / 03_API仕様書 §2.7)。

- アルゴリズムは lottery_v1.run_lottery() をそのまま使う (改変禁止: 不変条件4)
- 実行はイベント行の SELECT ... FOR UPDATE ロック下 (不変条件3)
- lotteries / lottery_results は追記専用: INSERT のみ (不変条件1)
"""
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND, get_membership
from app.core.errors import ApiError
from app.models import (
    Application,
    Checkin,
    Event,
    Lottery,
    LotteryResult,
    User,
    UserProfile,
)
from app.schemas.common import PageMeta
from app.schemas.lottery import (
    ExecuteResponse,
    LotteryHistoryItem,
    LotteryRequest,
    LotteryResultItem,
    LotteryResultsResponse,
    PreviewResponse,
    QuotaIn,
)
from app.services.application import transition_application
from app.services.lottery_v1 import QuotaConfig, run_lottery
from app.services.notification import queue_for_users

RESULT_NOTIFICATION = {
    "won": ("result_won", "当選"),
    "waitlisted": ("result_waitlisted", "補欠"),
    "lost": ("result_lost", "落選"),
}


async def _won_count(db: AsyncSession, event_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.event_id == event_id, Application.status == "won")
    )


async def _waitlisted_count(db: AsyncSession, event_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.event_id == event_id, Application.status == "waitlisted")
    )


async def _next_round(db: AsyncSession, event_id: uuid.UUID) -> int:
    max_round = await db.scalar(
        select(func.max(Lottery.round)).where(Lottery.event_id == event_id)
    )
    return (max_round or 0) + 1


async def _check_preconditions(db: AsyncSession, event: Event) -> int:
    """§3 の前提条件を検証し、残定員を返す。違反は 409 precondition_failed。"""
    if event.selection_method != "lottery":
        raise ApiError(409, "precondition_failed", "先着方式のイベントでは抽選を実行できません")
    if event.status not in ("published", "closed"):
        raise ApiError(409, "precondition_failed", "公開中または締切済のイベントのみ抽選できます")
    if datetime.now(UTC) <= event.apply_ends_at:
        raise ApiError(409, "precondition_failed", "応募締切前は抽選を実行できません")
    remaining = event.capacity - await _won_count(db, event.id)
    if remaining <= 0:
        raise ApiError(409, "precondition_failed", "残定員がありません")
    return remaining


async def _target_applications(
    db: AsyncSession, event: Event, round_: int
) -> list[Application]:
    """round 1 は pending 全応募、round 2以降は lost (敗者復活 §6)。"""
    if round_ == 1:
        target_status = "pending"
    else:
        if await _waitlisted_count(db, event.id) > 0:
            raise ApiError(
                409,
                "precondition_failed",
                "補欠が残っている間は追加抽選できません (繰り上げを使ってください)",
            )
        target_status = "lost"
    apps = (
        await db.scalars(
            select(Application).where(
                Application.event_id == event.id, Application.status == target_status
            )
        )
    ).all()
    if not apps:
        raise ApiError(409, "precondition_failed", "抽選対象の応募がありません")
    return list(apps)


async def repeater_user_ids(
    db: AsyncSession, event: Event, user_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """同一団体の過去イベントで入場実績のあるユーザー (02仕様書 §2 のSQL)。"""
    if not user_ids:
        return set()
    past_event = select(Event.id).where(
        Event.organization_id == event.organization_id,
        Event.starts_at < event.starts_at,
    )
    rows = await db.scalars(
        select(Application.user_id)
        .join(Checkin, Checkin.application_id == Application.id)
        .where(
            Application.user_id.in_(user_ids),
            Checkin.event_id.in_(past_event),
        )
        .distinct()
    )
    return set(rows)


def _quota_configs(quotas: list[QuotaIn]) -> list[QuotaConfig]:
    names = [q.name for q in quotas]
    if len(set(names)) != len(names):
        raise ApiError(422, "unprocessable", "枠名が重複しています")
    return [QuotaConfig(name=q.name, count=q.count, filter=q.filter) for q in quotas]


async def _build_matcher(
    db: AsyncSession, event: Event, apps: list[Application]
):
    """(application_id, filter名) -> bool の判定関数を作る。"""
    repeaters = await repeater_user_ids(db, event, [a.user_id for a in apps])
    user_by_app = {str(a.id): a.user_id for a in apps}

    def is_match(app_id: str, filter_name: str) -> bool:
        if filter_name == "all":
            return True
        is_repeater = user_by_app[app_id] in repeaters
        return is_repeater if filter_name == "repeater" else not is_repeater

    return is_match


async def preview(db: AsyncSession, event: Event, req: LotteryRequest) -> PreviewResponse:
    """実行せずに集計を返す (§2.7)。設定不正は422。"""
    remaining = await _check_preconditions(db, event)
    round_ = await _next_round(db, event.id)
    apps = await _target_applications(db, event, round_)
    quotas = _quota_configs(req.quotas)

    fixed_total = sum(q.count for q in quotas if q.count is not None)
    none_counts = [q for q in quotas if q.count is None]
    if len(none_counts) > 1 or (none_counts and quotas[-1].count is not None):
        raise ApiError(422, "unprocessable", "残枠吸収の枠 (count=null) は最後に1つだけ置けます")
    if fixed_total > remaining:
        raise ApiError(422, "unprocessable", "枠の合計が残定員を超えています")

    is_match = await _build_matcher(db, event, apps)
    quota_matches = {
        q.name: sum(1 for a in apps if is_match(str(a.id), q.filter)) for q in quotas
    }
    return PreviewResponse(
        target_count=len(apps), remaining_capacity=remaining, quota_matches=quota_matches
    )


async def execute(
    db: AsyncSession, event_id: uuid.UUID, executor: User, req: LotteryRequest
) -> ExecuteResponse:
    """抽選実行 (02仕様書 §5 の1トランザクション)。"""
    # イベント単位の排他 (§3-5): FOR UPDATE でロックしてから全チェック・書き込み
    event = await db.scalar(select(Event).where(Event.id == event_id).with_for_update())
    if event is None:
        raise NOT_FOUND
    remaining = await _check_preconditions(db, event)
    round_ = await _next_round(db, event.id)
    apps = await _target_applications(db, event, round_)
    apps_by_id = {str(a.id): a for a in apps}
    is_match = await _build_matcher(db, event, apps)

    seed = secrets.randbits(63)
    try:
        results = run_lottery(
            application_ids=list(apps_by_id.keys()),
            quotas=_quota_configs(req.quotas),
            remaining_capacity=remaining,
            waitlist_count=req.waitlist_count,
            seed=seed,
            is_match=is_match,
        )
    except ValueError as exc:
        raise ApiError(422, "unprocessable", str(exc)) from exc

    won = [r for r in results if r.result == "won"]
    waitlisted = [r for r in results if r.result == "waitlisted"]
    lost = [r for r in results if r.result == "lost"]

    # 1. lotteries (追記専用)
    lottery = Lottery(
        event_id=event.id,
        round=round_,
        executed_by=executor.id,
        seed=seed,
        algorithm_version="v1",
        winner_quota=len(won),
        waitlist_quota=len(waitlisted),
        config={
            "quotas": [q.model_dump() for q in req.quotas],
            "waitlist_count": req.waitlist_count,
        },
    )
    db.add(lottery)
    await db.flush()

    # 2. lottery_results (追記専用・全対象ぶん)
    for r in results:
        db.add(
            LotteryResult(
                lottery_id=lottery.id,
                application_id=uuid.UUID(r.application_id),
                result=r.result,
                draw_rank=r.draw_rank,
                quota_name=r.quota_name,
            )
        )

    # 3. applications.status を results どおりに更新 (遷移関数経由: 不変条件2)
    for r in results:
        app = apps_by_id[r.application_id]
        if app.status == r.result:
            continue  # round≥2 の lost→lost は無遷移
        transition_application(app, r.result)

    # 4. 結果通知を queued で作成 (in_app+email 全員 / push は購読者のみ)
    for result_key, group in (("won", won), ("waitlisted", waitlisted), ("lost", lost)):
        if not group:
            continue
        type_, label = RESULT_NOTIFICATION[result_key]
        await queue_for_users(
            db,
            [apps_by_id[r.application_id].user_id for r in group],
            event_id=event.id,
            type_=type_,
            title=f"【{event.title}】抽選結果: {label}",
            body=(
                f"イベント「{event.title}」の抽選結果は「{label}」です。\n"
                "詳細はマイページをご確認ください。\n"
            ),
        )

    await db.commit()
    await db.refresh(lottery)
    return ExecuteResponse(
        lottery_id=str(lottery.id),
        round=lottery.round,
        won=len(won),
        waitlisted=len(waitlisted),
        lost=len(lost),
        executed_at=lottery.executed_at,
    )


async def list_history(db: AsyncSession, event: Event) -> list[LotteryHistoryItem]:
    rows = (
        await db.execute(
            select(Lottery, User.email)
            .join(User, User.id == Lottery.executed_by)
            .where(Lottery.event_id == event.id)
            .order_by(Lottery.round)
        )
    ).all()
    return [
        LotteryHistoryItem(
            id=str(lot.id),
            round=lot.round,
            executed_by_email=email,
            algorithm_version=lot.algorithm_version,
            winner_quota=lot.winner_quota,
            waitlist_quota=lot.waitlist_quota,
            config=lot.config,
            executed_at=lot.executed_at,
        )
        for lot, email in rows
    ]


async def get_results(
    db: AsyncSession, lottery_id: uuid.UUID, user: User, page: int, per_page: int
) -> LotteryResultsResponse:
    lottery = await db.get(Lottery, lottery_id)
    if lottery is None:
        raise NOT_FOUND
    event = await db.get(Event, lottery.event_id)
    if event is None or await get_membership(db, event.organization_id, user) is None:
        raise NOT_FOUND

    total = await db.scalar(
        select(func.count())
        .select_from(LotteryResult)
        .where(LotteryResult.lottery_id == lottery_id)
    )
    rows = (
        await db.execute(
            select(LotteryResult, Application, UserProfile.display_name)
            .join(Application, Application.id == LotteryResult.application_id)
            .outerjoin(UserProfile, UserProfile.user_id == Application.user_id)
            .where(LotteryResult.lottery_id == lottery_id)
            .order_by(LotteryResult.draw_rank)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    return LotteryResultsResponse(
        items=[
            LotteryResultItem(
                application_id=str(res.application_id),
                display_name=display_name,
                result=res.result,
                draw_rank=res.draw_rank,
                quota_name=res.quota_name,
                current_status=app.status,
            )
            for res, app, display_name in rows
        ],
        meta=PageMeta(page=page, per_page=per_page, total=total),
    )


# --- 繰り上げ (02仕様書 §7: 抽選ではない決定的ルール) ---

async def next_promotion_candidate(
    db: AsyncSession, event_id: uuid.UUID
) -> Application | None:
    """waitlisted のうち「round昇順 → draw_rank昇順」で最上位の応募。"""
    return await db.scalar(
        select(Application)
        .join(LotteryResult, LotteryResult.application_id == Application.id)
        .join(Lottery, Lottery.id == LotteryResult.lottery_id)
        .where(
            Application.event_id == event_id,
            Application.status == "waitlisted",
            LotteryResult.result == "waitlisted",
        )
        .order_by(Lottery.round, LotteryResult.draw_rank)
        .limit(1)
    )


async def promote(db: AsyncSession, event: Event, candidate: Application) -> None:
    """繰り上げ当選 + promoted 通知 (commitは呼び出し側)。"""
    transition_application(candidate, "won", promoted=True)
    await queue_for_users(
        db,
        [candidate.user_id],
        event_id=event.id,
        type_="promoted",
        title=f"【{event.title}】繰り上げ当選のお知らせ",
        body=(
            f"イベント「{event.title}」で補欠から繰り上げ当選しました。\n"
            "詳細はマイページをご確認ください。\n"
        ),
    )


async def auto_promote_on_cancel(db: AsyncSession, event_id: uuid.UUID) -> None:
    """won → canceled 時の自動繰り上げ (§7)。開始後・非公開状態では行わない。"""
    event = await db.get(Event, event_id)
    if event is None or event.status not in ("published", "closed"):
        return
    if datetime.now(UTC) >= event.starts_at:
        return
    candidate = await next_promotion_candidate(db, event_id)
    if candidate is not None:
        await promote(db, event, candidate)


async def manual_promote(
    db: AsyncSession, application_id: uuid.UUID, user: User
) -> None:
    """手動繰り上げ (§2.7)。対象は「次の繰り上げ候補」のみ。候補でない場合409。"""
    app = await db.get(Application, application_id)
    if app is None:
        raise NOT_FOUND
    event = await db.get(Event, app.event_id)
    if event is None or await get_membership(db, event.organization_id, user) is None:
        raise NOT_FOUND
    candidate = await next_promotion_candidate(db, app.event_id)
    if candidate is None or candidate.id != app.id:
        raise ApiError(409, "conflict", "この応募は次の繰り上げ候補ではありません")
    if event.capacity - await _won_count(db, event.id) <= 0:
        raise ApiError(409, "conflict", "残定員がないため繰り上げできません")
    await promote(db, event, candidate)
    await db.commit()
