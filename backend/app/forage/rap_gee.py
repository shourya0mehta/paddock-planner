"""Within-season growth from RAP's 16-day production product (Earth Engine).

The annual COGs tell you how much a pasture produced last season. To size a
*rest period* you need how fast it is growing *now*, which is what the 16-day
NPP product gives. It only lives in Earth Engine, so this module is optional:
it needs the `earthengine-api` package and an authenticated account
(`earthengine authenticate`). Without it the planner still runs; rest
periods are simply reported as "needs growth data".

Asset: projects/rap-data-365417/assets/npp-partitioned-16day-v3
Bands: afgNPP, pfgNPP, shrNPP, treNPP (net primary production, scaled)

NPP -> aboveground herbaceous biomass follows RAP's published Earth Engine
script (Jones et al. 2021, Robinson et al. 2019):

    biomass_lb_ac = NPP * 0.0001            # stored scale -> kg C / m2
                    * 2.20462 * 4046.86     # kg/m2 -> lb/acre
                    * fANPP                 # fraction of NPP that is aboveground
                    * 2.5                   # carbon -> dry matter (40% C)
    fANPP = 0.171 + 0.0129 * MAT            # MAT = mean annual temperature (C)

VERIFY the constants against rangelands.app/support before quoting numbers
from this module in front of anyone. They are transcribed, not fetched.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from shapely.geometry import Polygon, mapping

NPP_16DAY = "projects/rap-data-365417/assets/npp-partitioned-16day-v3"
GRIDMET_MAT = "projects/rap-data-365417/assets/gridmet-MAT"


@dataclass
class GrowthPeriod:
    start: dt.date
    afg_lb_ac: float
    pfg_lb_ac: float

    @property
    def herb_lb_ac(self) -> float:
        return self.afg_lb_ac + self.pfg_lb_ac


def growth_series(poly_wgs: Polygon, season_start: dt.date, until: dt.date | None = None) -> list[GrowthPeriod]:
    """Mean 16-day herbaceous production (lb/acre per period) over the pasture."""
    import ee  # optional dependency

    until = until or dt.date.today()
    region = ee.Geometry(mapping(poly_wgs))
    mat = ee.ImageCollection(GRIDMET_MAT).filterDate(f"{season_start.year}-01-01", f"{season_start.year}-12-31").first()
    fanpp = mat.multiply(0.0129).add(0.171)

    def to_biomass(img):
        lb = (
            img.select(["afgNPP", "pfgNPP"])
            .multiply(0.0001)
            .multiply(2.20462)
            .multiply(4046.86)
            .multiply(fanpp)
            .multiply(2.5)
        )
        stats = lb.reduceRegion(ee.Reducer.mean(), region, 30, maxPixels=1e8)
        return ee.Feature(None, stats).set("date", img.date().format("YYYY-MM-dd"))

    coll = ee.ImageCollection(NPP_16DAY).filterDate(season_start.isoformat(), until.isoformat()).filterBounds(region)
    feats = coll.map(to_biomass).getInfo()["features"]
    out = []
    for f in feats:
        p = f["properties"]
        if p.get("afgNPP") is None:
            continue
        out.append(
            GrowthPeriod(
                start=dt.date.fromisoformat(p["date"]),
                afg_lb_ac=float(p["afgNPP"]),
                pfg_lb_ac=float(p["pfgNPP"]),
            )
        )
    return sorted(out, key=lambda g: g.start)


def current_growth_rate_lb_ac_day(series: list[GrowthPeriod], periods: int = 2) -> float | None:
    """Average daily herbaceous growth over the last `periods` 16-day windows."""
    if not series:
        return None
    recent = series[-periods:]
    return sum(g.herb_lb_ac for g in recent) / (16.0 * len(recent))
