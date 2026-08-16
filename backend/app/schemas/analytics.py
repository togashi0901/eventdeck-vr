from datetime import date, datetime

from pydantic import BaseModel


class DailyApplications(BaseModel):
    date: date
    count: int


class EventAnalyticsResponse(BaseModel):
    """イベント分析 (§2.10)。"""

    applications_total: int
    """キャンセル含む全応募数。"""
    by_status: dict[str, int]
    checkin_rate: float
    first_timer_rate: float
    """応募者 (キャンセル除く・ユニークユーザー) のうち初参加者の割合。"""
    daily_applications: list[DailyApplications]


class OrgEventAnalyticsRow(BaseModel):
    event_id: str
    title: str
    starts_at: datetime
    status: str
    applications_total: int
    won_count: int
    checkin_count: int
    checkin_rate: float


class OrgAnalyticsSummaryResponse(BaseModel):
    """団体横断の分析 (§2.10)。"""

    events: list[OrgEventAnalyticsRow]
    unique_attendees: int
    """団体のイベントに1回以上入場したユニークユーザー数。"""
    repeat_attendees: int
    """2回以上入場したユニークユーザー数。"""
    repeat_rate: float
    """リピート率 = repeat_attendees / unique_attendees (0除算は0.0)。"""
