"""応募サービス (03_API仕様書 §2.6)。

- 状態遷移は transition_application() に集約 (不変条件2)
- 先着確定はイベント行の SELECT ... FOR UPDATE ロック下で行う (不変条件3)
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import NOT_FOUND, get_membership
from app.core.errors import ApiError
from app.models import (
    Application,
    ApplicationAnswer,
    Event,
    FormItem,
    Organization,
    User,
    UserProfile,
)
from app.schemas.application import (
    AnswerIn,
    AnswerOut,
    ApplicantItem,
    ApplicationResponse,
    EntryCodeResponse,
    EventBrief,
    MyApplicationItem,
)
from app.services.form import load_items

# 01_DB設計書 §4 の遷移図にある経路のみ (不変条件2)。
# lost→won / lost→waitlisted は遷移図には無いが、01設計書が「救済は追加抽選で対応」と
# 定める敗者復活抽選 (02_抽選仕様書 §6, round≥2) の実行経路としてのみ使われる。
ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    ("pending", "won"),
    ("pending", "lost"),
    ("pending", "waitlisted"),
    ("pending", "canceled"),
    ("won", "canceled"),
    ("waitlisted", "won"),
    ("waitlisted", "canceled"),
    ("waitlisted", "lost"),
    ("lost", "won"),
    ("lost", "waitlisted"),
}


def transition_application(
    app: Application,
    new_status: str,
    *,
    promoted: bool = False,
    cancel_reason: str | None = None,
) -> None:
    """applications.status の遷移はすべてこの関数を通す (不変条件2)。

    commit は呼び出し側の責務 (抽選トランザクション等に組み込むため)。
    """
    if (app.status, new_status) not in ALLOWED_TRANSITIONS:
        raise ApiError(409, "conflict", f"{app.status} から {new_status} へは遷移できません")
    if new_status == "canceled":
        app.canceled_at = datetime.now(UTC)
        app.cancel_reason = cancel_reason
    if new_status == "won" and promoted:
        app.promoted = True
    app.status = new_status


def short_code(application_id: uuid.UUID) -> str:
    """入場コード: application_id の先頭8桁 (§2.6)。"""
    return str(application_id)[:8]


def _validate_answers(
    items: list[FormItem], answers: list[AnswerIn]
) -> list[tuple[FormItem, str | None, list[str] | None]]:
    """回答を検証し (設問, answer_text, answer_json) のリストを返す。"""
    items_by_id = {str(i.id): i for i in items}
    seen: set[str] = set()
    problems: list[dict] = []
    validated: list[tuple[FormItem, str | None, list[str] | None]] = []

    for ans in answers:
        item = items_by_id.get(ans.form_item_id)
        if item is None:
            raise ApiError(400, "validation_error", f"設問 {ans.form_item_id} は存在しません")
        if ans.form_item_id in seen:
            raise ApiError(400, "validation_error", "同じ設問への回答が重複しています")
        seen.add(ans.form_item_id)

        if item.item_type == "checkbox":
            values = ans.values or []
            if ans.value is not None:
                problems.append({"field": str(item.id), "reason": "use_values_for_checkbox"})
                continue
            invalid = [v for v in values if v not in (item.options or [])]
            if invalid:
                problems.append({"field": str(item.id), "reason": "value_not_in_options"})
                continue
            if values:
                validated.append((item, None, values))
        else:
            value = (ans.value or "").strip()
            if ans.values is not None:
                problems.append({"field": str(item.id), "reason": "use_value_for_this_type"})
                continue
            if not value:
                continue  # 空回答は未回答扱い (必須チェックは後段)
            if item.item_type in ("select", "radio") and value not in (item.options or []):
                problems.append({"field": str(item.id), "reason": "value_not_in_options"})
                continue
            if item.item_type == "number":
                try:
                    float(value)
                except ValueError:
                    problems.append({"field": str(item.id), "reason": "not_a_number"})
                    continue
            validated.append((item, value, None))

    answered_ids = {str(item.id) for item, _, _ in validated}
    for item in items:
        if item.is_required and str(item.id) not in answered_ids:
            problems.append({"field": str(item.id), "reason": "required"})

    if problems:
        raise ApiError(400, "validation_error", "回答が不正です", details=problems)
    return validated


def _to_response(app: Application, answers: list[AnswerOut] | None = None) -> ApplicationResponse:
    return ApplicationResponse(
        id=str(app.id),
        event_id=str(app.event_id),
        status=app.status,
        promoted=app.promoted,
        applied_at=app.applied_at,
        canceled_at=app.canceled_at,
        answers=answers or [],
    )


async def apply(
    db: AsyncSession, event_id: uuid.UUID, user: User, answers: list[AnswerIn]
) -> ApplicationResponse:
    event = await db.get(Event, event_id)
    if event is None or event.status != "published":
        raise NOT_FOUND

    now = datetime.now(UTC)
    if now < event.apply_starts_at:
        raise ApiError(409, "precondition_failed", "応募受付開始前です")
    if now > event.apply_ends_at:
        raise ApiError(409, "precondition_failed", "応募は締め切られました")

    if await db.get(UserProfile, user.id) is None:
        raise ApiError(422, "profile_required", "応募にはプロフィール登録が必要です")

    duplicate = await db.scalar(
        select(Application).where(
            Application.event_id == event.id, Application.user_id == user.id
        )
    )
    if duplicate is not None:
        raise ApiError(409, "already_applied", "このイベントには応募済みです")

    validated = _validate_answers(await load_items(db, event.id), answers)

    try:
        if event.selection_method == "first_come":
            # 先着: イベント行ロック下で残定員を判定し、定員内なら即 won (不変条件3)。
            # 先着の won は lotteries を使わず直接確定する (01_DB設計書 §4)。
            # 応募行の INSERT はイベント行に FK の KEY SHARE ロックを取るため、
            # デッドロック回避のロック順序として必ず FOR UPDATE を先に取得する。
            locked_event = await db.scalar(
                select(Event).where(Event.id == event.id).with_for_update()
            )
            won_count = await db.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.event_id == event.id, Application.status == "won")
            )
            application = Application(event_id=event.id, user_id=user.id, status="pending")
            db.add(application)
            await db.flush()
            if won_count < locked_event.capacity:
                transition_application(application, "won")
        else:
            application = Application(event_id=event.id, user_id=user.id, status="pending")
            db.add(application)
            await db.flush()

        for item, text_value, json_value in validated:
            db.add(
                ApplicationAnswer(
                    application_id=application.id,
                    form_item_id=item.id,
                    answer_text=text_value,
                    answer_json=json_value,
                )
            )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "already_applied", "このイベントには応募済みです") from exc
    await db.refresh(application)
    return _to_response(application)


async def _answers_for(
    db: AsyncSession, application_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[AnswerOut]]:
    if not application_ids:
        return {}
    rows = (
        await db.execute(
            select(ApplicationAnswer, FormItem)
            .join(FormItem, FormItem.id == ApplicationAnswer.form_item_id)
            .where(ApplicationAnswer.application_id.in_(application_ids))
            .order_by(FormItem.sort_order)
        )
    ).all()
    result: dict[uuid.UUID, list[AnswerOut]] = {}
    for answer, item in rows:
        result.setdefault(answer.application_id, []).append(
            AnswerOut(
                form_item_id=str(item.id),
                label=item.label,
                item_type=item.item_type,
                value=answer.answer_text,
                values=answer.answer_json,
            )
        )
    return result


async def list_applicants(
    db: AsyncSession, event: Event, status: str | None, q: str | None
) -> list[ApplicantItem]:
    conditions = [Application.event_id == event.id]
    if status:
        conditions.append(Application.status == status)
    if q:
        pattern = f"%{q}%"
        conditions.append(
            or_(UserProfile.display_name.ilike(pattern), UserProfile.vrchat_username.ilike(pattern))
        )
    rows = (
        await db.execute(
            select(Application, UserProfile)
            .outerjoin(UserProfile, UserProfile.user_id == Application.user_id)
            .where(*conditions)
            .order_by(Application.applied_at)
        )
    ).all()
    answers = await _answers_for(db, [app.id for app, _ in rows])
    return [
        ApplicantItem(
            id=str(app.id),
            status=app.status,
            promoted=app.promoted,
            applied_at=app.applied_at,
            display_name=profile.display_name if profile else None,
            vrchat_username=profile.vrchat_username if profile else None,
            answers=answers.get(app.id, []),
        )
        for app, profile in rows
    ]


async def get_application_for_user(
    db: AsyncSession, application_id: uuid.UUID, user: User
) -> Application:
    """本人 or 対象イベントの member のみ (非該当は404)。"""
    app = await db.get(Application, application_id)
    if app is None:
        raise NOT_FOUND
    if app.user_id != user.id:
        event = await db.get(Event, app.event_id)
        if event is None or await get_membership(db, event.organization_id, user) is None:
            raise NOT_FOUND
    return app


async def get_application_detail(
    db: AsyncSession, application_id: uuid.UUID, user: User
) -> ApplicationResponse:
    app = await get_application_for_user(db, application_id, user)
    answers = await _answers_for(db, [app.id])
    return _to_response(app, answers.get(app.id, []))


async def cancel_application(
    db: AsyncSession, application_id: uuid.UUID, user: User, reason: str | None
) -> ApplicationResponse:
    """本人のみキャンセル可 (§2.6)。"""
    app = await db.get(Application, application_id)
    if app is None or app.user_id != user.id:
        raise NOT_FOUND
    was_won = app.status == "won"
    transition_application(app, "canceled", cancel_reason=reason)
    if was_won:
        # won → canceled は自動繰り上げをトリガ (02_抽選仕様書 §7)。同一トランザクションで行う。
        # モジュール先頭で import すると循環になるため遅延 import
        from app.services.lottery import auto_promote_on_cancel

        await auto_promote_on_cancel(db, app.event_id)
    await db.commit()
    await db.refresh(app)
    return _to_response(app)


async def list_my_applications(db: AsyncSession, user: User) -> list[MyApplicationItem]:
    rows = (
        await db.execute(
            select(Application, Event, Organization)
            .join(Event, Event.id == Application.event_id)
            .join(Organization, Organization.id == Event.organization_id)
            .where(Application.user_id == user.id)
            .order_by(Application.applied_at.desc())
        )
    ).all()
    return [
        MyApplicationItem(
            id=str(app.id),
            status=app.status,
            promoted=app.promoted,
            applied_at=app.applied_at,
            event=EventBrief(
                id=str(event.id),
                title=event.title,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                status=event.status,
                selection_method=event.selection_method,
                organization_name=org.name,
            ),
            short_code=short_code(app.id),
        )
        for app, event, org in rows
    ]


async def get_entry_code(
    db: AsyncSession, application_id: uuid.UUID, user: User
) -> EntryCodeResponse:
    app = await db.get(Application, application_id)
    if app is None or app.user_id != user.id:
        raise NOT_FOUND
    return EntryCodeResponse(application_id=str(app.id), short_code=short_code(app.id))
