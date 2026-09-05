"""Turn ordered strips into a calendar.

Each strip gets a start and end date from its grazing days. Rest periods are
computed only when a growth rate is available (see forage/rap_gee.py); the
planner refuses to invent one.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .herd import Herd, grazing_days
from .strips import Strip


@dataclass
class Stay:
    strip_index: int
    days: float
    start: dt.date
    end: dt.date  # last grazing day, inclusive
    rest_days_needed: float | None
    ready_again: dt.date | None


def schedule(
    strips: list[Strip],
    herd: Herd,
    utilization: float,
    start: dt.date,
    growth_lb_ac_day: float | None = None,
    min_days: float = 1.0,
) -> list[Stay]:
    """Sequential stays. Fractional days are kept; the UI rounds for display."""
    stays: list[Stay] = []
    cursor = start
    for s in strips:
        days = max(min_days, grazing_days(s.forage_lb, utilization, herd)) if s.forage_lb > 0 else min_days
        end = cursor + dt.timedelta(days=max(0, round(days) - 1))
        rest = None
        ready = None
        if growth_lb_ac_day and growth_lb_ac_day > 0 and s.forage_lb_ac > 0:
            # Regrow what was taken: utilisation share of the pre-graze standing crop.
            taken_lb_ac = s.forage_lb_ac * utilization
            rest = taken_lb_ac / growth_lb_ac_day
            ready = end + dt.timedelta(days=round(rest))
        stays.append(
            Stay(strip_index=s.index, days=days, start=cursor, end=end, rest_days_needed=rest, ready_again=ready)
        )
        cursor = end + dt.timedelta(days=1)
    return stays


def total_days(stays: list[Stay]) -> float:
    return float(sum(s.days for s in stays))


def rotation_closes(stays: list[Stay]) -> tuple[bool, str]:
    """Does the first strip recover before the herd gets back to it?

    Only answerable with rest data. Returns (ok, message).
    """
    if not stays or stays[0].ready_again is None:
        return (False, "Rest periods need a growth rate (16-day RAP series). Not computed.")
    first = stays[0]
    back = stays[-1].end + dt.timedelta(days=1)
    if first.ready_again <= back:
        slack = (back - first.ready_again).days
        return (True, f"Strip 1 is ready {slack} day(s) before the herd returns.")
    short = (first.ready_again - back).days
    return (False, f"Strip 1 needs {short} more day(s) of rest before the herd returns. Slow down or add ground.")
