# -*- coding: utf-8 -*-
"""lottery_v1 の性質検証テスト (pytest)"""
import pytest
from random import Random
from lottery_v1 import run_lottery, QuotaConfig


def ids(n):
    return [f"app-{i:04d}" for i in range(n)]

ALL = [QuotaConfig("general", None, "all")]

def match_none(app_id, f):  # 誰も優先条件に合致しない
    return False


def test_deterministic_same_seed():
    """同じ入力・同じシードなら結果は完全一致する (再現性=公平性の証跡)"""
    a = run_lottery(ids(100), ALL, 30, 10, seed=42, is_match=match_none)
    b = run_lottery(ids(100), ALL, 30, 10, seed=42, is_match=match_none)
    assert a == b

def test_input_order_independent():
    """入力リストの順序が違っても結果は同じ (正規順序ソートの検証)"""
    apps = ids(50)
    shuffled = list(apps); Random(999).shuffle(shuffled)
    a = run_lottery(apps, ALL, 10, 5, seed=7, is_match=match_none)
    b = run_lottery(shuffled, ALL, 10, 5, seed=7, is_match=match_none)
    assert sorted(a, key=lambda r: r.application_id) == sorted(b, key=lambda r: r.application_id)

def test_different_seed_differs():
    a = run_lottery(ids(100), ALL, 30, 0, seed=1, is_match=match_none)
    b = run_lottery(ids(100), ALL, 30, 0, seed=2, is_match=match_none)
    assert {r.application_id for r in a if r.result == "won"} != \
           {r.application_id for r in b if r.result == "won"}

def test_capacity_and_waitlist_counts():
    res = run_lottery(ids(100), ALL, 30, 10, seed=5, is_match=match_none)
    assert sum(r.result == "won" for r in res) == 30
    assert sum(r.result == "waitlisted" for r in res) == 10
    assert sum(r.result == "lost" for r in res) == 60
    assert len(res) == 100

def test_under_capacity_all_win():
    """定員割れ: 応募者全員が当選、補欠は発生しない"""
    res = run_lottery(ids(20), ALL, 50, 10, seed=5, is_match=match_none)
    assert all(r.result == "won" for r in res)

def test_priority_quota():
    """初参加者優先枠: 合致者が枠数まで優先的に当選する"""
    first_timers = {f"app-{i:04d}" for i in range(15)}  # 15人が初参加
    def is_match(app_id, f):
        return f == "first_timer" and app_id in first_timers
    quotas = [QuotaConfig("first_timer", 10, "first_timer"),
              QuotaConfig("general", None, "all")]
    res = run_lottery(ids(100), quotas, 30, 0, seed=11, is_match=is_match)
    ft_won = [r for r in res if r.result == "won" and r.quota_name == "first_timer"]
    assert len(ft_won) == 10
    assert all(r.application_id in first_timers for r in ft_won)
    assert sum(r.result == "won" for r in res) == 30

def test_priority_quota_shortage_flows_to_general():
    """優先枠の合致者が枠数より少ない場合、余りは一般枠として消化され定員は守られる"""
    first_timers = {"app-0001", "app-0002"}  # 2人しかいない (枠は10)
    def is_match(app_id, f):
        return f == "first_timer" and app_id in first_timers
    quotas = [QuotaConfig("first_timer", 10, "first_timer"),
              QuotaConfig("general", None, "all")]
    res = run_lottery(ids(100), quotas, 30, 0, seed=11, is_match=is_match)
    assert sum(r.result == "won" for r in res) == 30
    assert {r.application_id for r in res
            if r.quota_name == "first_timer"} == first_timers

def test_draw_rank_is_permutation():
    res = run_lottery(ids(50), ALL, 10, 5, seed=3, is_match=match_none)
    assert sorted(r.draw_rank for r in res) == list(range(1, 51))

def test_waitlist_promotion_order_definable():
    """補欠は draw_rank 昇順で繰り上げる、が成立する (waitlist内で順位が一意)"""
    res = run_lottery(ids(100), ALL, 30, 10, seed=5, is_match=match_none)
    wl = sorted([r for r in res if r.result == "waitlisted"], key=lambda r: r.draw_rank)
    assert len({r.draw_rank for r in wl}) == 10

def test_invalid_configs():
    with pytest.raises(ValueError):  # count=Noneが2つ
        run_lottery(ids(10), [QuotaConfig("a", None, "all"), QuotaConfig("b", None, "all")],
                    5, 0, seed=1, is_match=match_none)
    with pytest.raises(ValueError):  # count=Noneが最後にない
        run_lottery(ids(10), [QuotaConfig("a", None, "all"), QuotaConfig("b", 2, "all")],
                    5, 0, seed=1, is_match=match_none)
    with pytest.raises(ValueError):  # 枠合計 > 残定員
        run_lottery(ids(10), [QuotaConfig("a", 6, "all")], 5, 0, seed=1, is_match=match_none)

def test_seed_reproduction_snapshot():
    """監査シナリオ: 保存済み seed から結果を後日再現できる"""
    apps = ids(40)
    original = run_lottery(apps, ALL, 12, 4, seed=20260709, is_match=match_none)
    reproduced = run_lottery(list(apps), ALL, 12, 4, seed=20260709, is_match=match_none)
    assert original == reproduced
