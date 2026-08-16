# -*- coding: utf-8 -*-
"""
EventDeck VR 抽選アルゴリズム v1 リファレンス実装
仕様: 02_抽選仕様書_EventDeckVR.md

DBに依存しない純粋関数。実装時は service 層からこのロジックを呼び出し、
戻り値を lottery_results / applications に書き込む。
"""
from dataclasses import dataclass
from random import Random
from typing import Callable, Optional


@dataclass(frozen=True)
class QuotaConfig:
    name: str                 # 例: "first_timer", "general"
    count: Optional[int]      # None = 残枠すべて (一般枠のみ許可)
    filter: str               # "first_timer" | "repeater" | "all"


@dataclass(frozen=True)
class LotteryResult:
    application_id: str
    result: str               # "won" | "lost" | "waitlisted"
    draw_rank: int            # シャッフル後の並び順 (1始まり)
    quota_name: str           # won: 当選枠名 / waitlisted: "waitlist" / lost: "none"


def run_lottery(
    application_ids: list[str],
    quotas: list[QuotaConfig],
    remaining_capacity: int,
    waitlist_count: int,
    seed: int,
    is_match: Callable[[str, str], bool],
) -> list[LotteryResult]:
    """
    抽選を実行する。決定的: 同じ入力(集合・設定・シード)からは常に同じ結果を返す。

    application_ids: 抽選対象の応募ID集合 (順序は結果に影響しない)
    quotas: 枠の定義。定義順に適用する。count=None の枠は最後に1つだけ置けて残枠を吸収する
    remaining_capacity: この抽選で当選にできる最大人数 (capacity - 既存won数)
    waitlist_count: 補欠として選ぶ人数
    seed: 乱数シード (実行時に生成し lotteries.seed に保存したもの)
    is_match: (application_id, filter名) -> bool。"all" は常にTrueを返すこと
    """
    if remaining_capacity < 0:
        raise ValueError("remaining_capacity must be >= 0")
    none_counts = [q for q in quotas if q.count is None]
    if len(none_counts) > 1:
        raise ValueError("count=None (残枠吸収) の枠は1つまで")
    if none_counts and quotas[-1].count is not None:
        raise ValueError("count=None の枠は最後に置くこと")
    fixed_total = sum(q.count for q in quotas if q.count is not None)
    if fixed_total > remaining_capacity:
        raise ValueError("枠の合計が残定員を超えています")

    # 1. 正規順序に整列してからシャッフル (入力順に依存しないため)
    ordered = sorted(application_ids)
    rng = Random(seed)
    rng.shuffle(ordered)
    rank = {app_id: i + 1 for i, app_id in enumerate(ordered)}  # draw_rank

    # 2. 枠を定義順に適用して当選者を選ぶ
    selected: dict[str, str] = {}  # app_id -> quota_name
    for q in quotas:
        limit = q.count if q.count is not None else remaining_capacity - len(selected)
        taken = 0
        for app_id in ordered:
            if taken >= limit or len(selected) >= remaining_capacity:
                break
            if app_id in selected:
                continue
            if q.filter == "all" or is_match(app_id, q.filter):
                selected[app_id] = q.name
                taken += 1

    # 3. 未当選者のうちシャッフル順で先頭 waitlist_count 名を補欠にする
    waitlisted: set[str] = set()
    for app_id in ordered:
        if len(waitlisted) >= waitlist_count:
            break
        if app_id not in selected:
            waitlisted.add(app_id)

    # 4. 結果を組み立てる (全対象ぶん)
    results = []
    for app_id in ordered:
        if app_id in selected:
            results.append(LotteryResult(app_id, "won", rank[app_id], selected[app_id]))
        elif app_id in waitlisted:
            results.append(LotteryResult(app_id, "waitlisted", rank[app_id], "waitlist"))
        else:
            results.append(LotteryResult(app_id, "lost", rank[app_id], "none"))
    return results
