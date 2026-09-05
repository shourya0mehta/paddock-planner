"""Exercise the RAP reader against local GeoTIFFs shaped like the real ones.

The real files are CONUS-wide COGs in EPSG:4326 at ~0.00027 degrees. We
write a small tile with the same CRS, resolution, dtypes and nodata, point
the reader at it, and check the window read + warp onto the UTM grid keeps
values where they belong. This does not test HTTP; `scripts/check_rap.py`
does that before a demo.
"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.forage import rap
from app.forage.grid import LocalFrame, polygon_from_geojson
from app.presets import PRESETS

RES = 0.000269494585236  # RAP v3 pixel size, degrees


@pytest.fixture
def rap_files(tmp_path, monkeypatch):
    p = next(p for p in PRESETS if p["id"] == "colorado")
    poly = polygon_from_geojson(p["pasture"])
    minx, miny, maxx, maxy = poly.bounds
    pad = 0.01
    west, north = minx - pad, maxy + pad
    ncols = int((maxx + pad - west) / RES) + 1
    nrows = int((north - (miny - pad)) / RES) + 1
    transform = from_origin(west, north, RES, RES)

    # Biomass: annual band is a west->east ramp 200..1200, perennial is 800 flat; one nodata hole.
    cols = np.arange(ncols)[None, :].repeat(nrows, axis=0)
    afg = (200 + 1000 * cols / max(ncols - 1, 1)).astype("uint16")
    pfg = np.full((nrows, ncols), 800, dtype="uint16")
    afg[nrows // 2, ncols // 2] = 65535
    bio = tmp_path / "biomass-2025.tif"
    with rasterio.open(
        bio,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=2,
        dtype="uint16",
        crs="EPSG:4326",
        transform=transform,
        nodata=65535,
    ) as dst:
        dst.write(afg, 1)
        dst.write(pfg, 2)

    # Cover: tree cover 60% in the eastern third, 5% elsewhere; shrub 10% everywhere.
    tre = np.where(cols > 2 * ncols / 3, 60, 5).astype("uint8")
    shr = np.full((nrows, ncols), 10, dtype="uint8")
    cov = tmp_path / "cover-2025.tif"
    with rasterio.open(
        cov,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=6,
        dtype="uint8",
        crs="EPSG:4326",
        transform=transform,
        nodata=255,
    ) as dst:
        for b in range(1, 7):
            dst.write(np.zeros((nrows, ncols), dtype="uint8"), b)
        dst.write(shr, rap.COVER_BANDS["SHR"])
        dst.write(tre, rap.COVER_BANDS["TRE"])

    monkeypatch.setattr(rap, "BIOMASS_URL", str(tmp_path / "biomass-{year}.tif"))
    monkeypatch.setattr(rap, "COVER_URL", str(tmp_path / "cover-{year}.tif"))
    return poly


def test_rap_reader_warps_values_onto_local_grid(rap_files):
    poly = rap_files
    frame = LocalFrame.for_polygon(poly)
    g = rap.RAPSource(year=2025).sample(poly, frame)

    assert g.meta["source"] == "rap" and g.meta["year"] == 2025
    inside = g.mask & np.isfinite(g.biomass_lb_ac)
    assert inside.sum() > 1000  # a 640-acre pasture is ~2,600 pixels at 30 m

    b = g.biomass_lb_ac
    # Total = ramp (200..1200) + 800 flat, so everything sits in [1000, 2000].
    assert np.nanmin(b[inside]) >= 990 and np.nanmax(b[inside]) <= 2010
    # West side of the pasture is poorer than the east side: the ramp survived the warp.
    xs, _ = g.centroids()
    west = inside & (xs < np.median(xs[inside]))
    east = inside & (xs >= np.median(xs[inside]))
    assert np.nanmean(b[east]) - np.nanmean(b[west]) > 200

    # Tree cover: high in the east, low in the west; shrub flat at 10.
    assert g.tree_cover_pct[east].mean() > g.tree_cover_pct[west].mean()
    assert abs(g.shrub_cover_pct[inside].mean() - 10) < 1.5

    # The reader treats nodata as missing rather than as 65,535 lb/acre.
    assert np.nanmax(b) < 60_000


def test_latest_year_probe_walks_backwards(rap_files, monkeypatch):
    import datetime as dt

    class FakeDate(dt.date):
        @classmethod
        def today(cls):
            return cls(2027, 3, 1)  # so "last year" is 2026, which does not exist in the fixture

    monkeypatch.setattr(dt, "date", FakeDate)
    assert rap.RAPSource()._latest_year() == 2025  # noqa: SLF001
