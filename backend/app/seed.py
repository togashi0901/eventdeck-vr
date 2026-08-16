"""シードデータ投入 (CLAUDE.md §8)。`make seed` で実行する。

- 主催者: organizer@example.com / Passw0rd! (確認済み)
- 参加者: fan01@example.com 〜 fan08@example.com / Passw0rd! (確認済み・プロフィール登録済み)
- 団体「Team EventDeck」+ 公開イベント1件 (定員5・抽選・受付中)

冪等: 既存データがあればそのまま残し、無いものだけ作る。
"""
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Event, Organization, OrganizationMember, User, UserProfile

SEED_PASSWORD = "Passw0rd!"


async def _get_or_create_user(db, email: str, *, verified: bool = True) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(SEED_PASSWORD),
            email_verified_at=datetime.now(UTC) if verified else None,
        )
        db.add(user)
        await db.flush()
        print(f"  + user {email}")
    return user


async def seed() -> None:
    async with SessionLocal() as db:
        print("== seed: users ==")
        organizer = await _get_or_create_user(db, "organizer@example.com")

        fans: list[User] = []
        for i in range(1, 9):
            fan = await _get_or_create_user(db, f"fan{i:02d}@example.com")
            fans.append(fan)
            if await db.get(UserProfile, fan.id) is None:
                db.add(
                    UserProfile(
                        user_id=fan.id,
                        display_name=f"ファン{i:02d}",
                        vrchat_username=f"fan{i:02d}_vrc",
                        platform="pcvr" if i % 2 else "quest_standalone",
                        x_account=f"fan{i:02d}_x",
                    )
                )
                print(f"  + profile fan{i:02d}")

        print("== seed: organization ==")
        org = await db.scalar(select(Organization).where(Organization.slug == "team-eventdeck"))
        if org is None:
            org = Organization(
                name="Team EventDeck",
                slug="team-eventdeck",
                description="EventDeck VR 開発用のデモ団体",
            )
            db.add(org)
            await db.flush()
            print("  + organization Team EventDeck")
        member = await db.get(OrganizationMember, (org.id, organizer.id))
        if member is None:
            db.add(OrganizationMember(organization_id=org.id, user_id=organizer.id, role="owner"))
            print("  + organizer as owner")

        print("== seed: event ==")
        event = await db.scalar(
            select(Event).where(Event.organization_id == org.id, Event.title == "デモVRライブ")
        )
        if event is None:
            now = datetime.now(UTC)
            db.add(
                Event(
                    organization_id=org.id,
                    created_by=organizer.id,
                    title="デモVRライブ",
                    description="シードデータの公開イベント (定員5・抽選・受付中)",
                    platform="vrchat",
                    world_name="EventDeck Demo Hall",
                    starts_at=now + timedelta(days=14),
                    ends_at=now + timedelta(days=14, hours=2),
                    capacity=5,
                    selection_method="lottery",
                    apply_starts_at=now - timedelta(days=1),
                    apply_ends_at=now + timedelta(days=7),
                    status="published",
                    visibility="public",
                )
            )
            print("  + event デモVRライブ (published)")

        await db.commit()
        print("== seed: done ==")


if __name__ == "__main__":
    asyncio.run(seed())
