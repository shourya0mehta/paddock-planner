"""Pull the within-season growth rate for a preset from RAP's 16-day product.

    pip install earthengine-api && earthengine authenticate
    cd backend && python -m scripts.fetch_growth colorado 2026-04-01

Prints the 16-day herbaceous production series and the growth rate you can
paste into the UI's "growth rate" box (lb/acre/day) to get rest periods.
"""

from __future__ import annotations

import datetime as dt
import sys

from app.forage.grid import polygon_from_geojson
from app.forage.rap_gee import current_growth_rate_lb_ac_day, growth_series
from app.presets import PRESETS


def main(preset_id: str = "colorado", season_start: str | None = None) -> int:
    import ee

    ee.Initialize()
    p = next(p for p in PRESETS if p["id"] == preset_id)
    poly = polygon_from_geojson(p["pasture"])
    start = dt.date.fromisoformat(season_start) if season_start else dt.date(dt.date.today().year, 3, 1)
    series = growth_series(poly, start)
    for g in series:
        print(f"{g.start}  annual {g.afg_lb_ac:7.1f}  perennial {g.pfg_lb_ac:7.1f}  total {g.herb_lb_ac:7.1f} lb/ac")
    rate = current_growth_rate_lb_ac_day(series)
    print(f"\ncurrent growth rate: {rate:.2f} lb/acre/day" if rate else "\nno data in range")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
