import datetime as dt

import pytest
from shapely.geometry import Polygon

from app.planner.herd import Herd, grazing_days
from app.planner.rotation import rotation_closes, schedule
from app.planner.strips import Strip


def test_animal_units_and_demand():
    cows = Herd(species="cattle", head=100, avg_weight_lb=1200)
    assert cows.animal_units == pytest.approx(120.0)
    assert cows.demand_lb_per_day == pytest.approx(100 * 1200 * 0.026)  # 3,120 lb DM/day

    goats = Herd(species="goats", head=350)  # default 120 lb
    assert goats.animal_units == pytest.approx(42.0)


def test_grazing_days_take_half_leave_half():
    cows = Herd(species="cattle", head=50, avg_weight_lb=1000)  # 1,300 lb/day
    # 100 acres at 2,000 lb/acre = 200,000 lb; half is available -> 100,000 / 1,300
    assert grazing_days(200_000, 0.5, cows) == pytest.approx(76.92, rel=1e-3)


def test_grazing_days_rejects_bad_utilization():
    with pytest.raises(ValueError):
        grazing_days(1000, 0.0, Herd(species="sheep", head=10))
    with pytest.raises(ValueError):
        grazing_days(1000, 1.5, Herd(species="sheep", head=10))


def test_herd_validation():
    with pytest.raises(ValueError):
        Herd(species="llamas", head=3)
    with pytest.raises(ValueError):
        Herd(species="cattle", head=0)


def _strip(i: int, forage_lb: float, forage_lb_ac: float) -> Strip:
    return Strip(
        index=i,
        geometry=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        area_ac=1.0,
        forage_lb=forage_lb,
        forage_lb_ac=forage_lb_ac,
        tree_cover_pct=0.0,
        shrub_cover_pct=0.0,
        frac_treed=0.0,
    )


def test_schedule_is_back_to_back_and_rest_is_only_computed_with_growth():
    herd = Herd(species="cattle", head=10, avg_weight_lb=1000)  # 260 lb/day
    strips = [_strip(1, 2600, 1300), _strip(2, 5200, 1300)]  # 5 and 10 days at 50%
    start = dt.date(2026, 9, 10)
    stays = schedule(strips, herd, 0.5, start)
    assert [round(s.days) for s in stays] == [5, 10]
    assert stays[0].start == start and stays[0].end == dt.date(2026, 9, 14)
    assert stays[1].start == dt.date(2026, 9, 15) and stays[1].end == dt.date(2026, 9, 24)
    assert stays[0].rest_days_needed is None
    ok, msg = rotation_closes(stays)
    assert not ok and "growth" in msg.lower()

    # With growth of 25 lb/acre/day, regrowing the 650 lb/acre taken needs 26 days.
    stays = schedule(strips, herd, 0.5, start, growth_lb_ac_day=25.0)
    assert stays[0].rest_days_needed == pytest.approx(26.0)
    assert stays[0].ready_again == dt.date(2026, 9, 14) + dt.timedelta(days=26)
    ok, msg = rotation_closes(stays)
    assert not ok  # herd is back on Sep 25, strip 1 is ready Oct 10


def test_rotation_closes_when_rest_fits():
    herd = Herd(species="cattle", head=10, avg_weight_lb=1000)
    strips = [_strip(i, 2600, 1300) for i in range(1, 9)]  # 8 x 5 days = 40 days
    stays = schedule(strips, herd, 0.5, dt.date(2026, 9, 10), growth_lb_ac_day=25.0)
    ok, _ = rotation_closes(stays)
    assert ok
