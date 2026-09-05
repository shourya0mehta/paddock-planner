"""Verify the RAP COGs are reachable and read one pasture before a demo.

    cd backend && python -m scripts.check_rap [preset_id]

Prints the year found, the raster's CRS/resolution, and pasture-level forage
numbers. If this fails, the RAP host or path has moved: set RAP_BIOMASS_URL
and RAP_COVER_URL (see app/forage/rap.py) to the current locations listed at
https://rangelands.app/products/.
"""

from __future__ import annotations

import sys
import time

import rasterio

from app.forage.grid import LocalFrame, polygon_from_geojson
from app.forage.rap import BIOMASS_URL, COVER_URL, RAPSource
from app.presets import PRESETS


def main(preset_id: str = "colorado") -> int:
    src = RAPSource()
    year = src._latest_year()  # noqa: SLF001
    print(f"latest RAP year: {year}")
    for url in (BIOMASS_URL, COVER_URL):
        u = url.format(year=year)
        with rasterio.open(u) as ds:
            print(f"{u}\n  crs={ds.crs} res={ds.res} bands={ds.count} nodata={ds.nodata} dtype={ds.dtypes[0]}")

    p = next(p for p in PRESETS if p["id"] == preset_id)
    poly = polygon_from_geojson(p["pasture"])
    frame = LocalFrame.for_polygon(poly)
    t = time.time()
    g = src.sample(poly, frame)
    print(
        f"\n{p['name']}: {g.area_ac():.0f} ac, {g.forage_lb_total():,.0f} lb herbaceous, "
        f"{g.forage_lb_total() / max(g.area_ac(), 1):,.0f} lb/ac mean, "
        f"tree cover mean {g.tree_cover_pct[g.mask].mean():.1f}% ({time.time() - t:.1f}s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
