"""Rangeland Analysis Platform (RAP) as a forage source.

RAP (University of Montana / USDA NRCS) publishes 30 m, CONUS-wide estimates
of herbaceous biomass (lb/acre) and fractional vegetation cover every year as
public Cloud-Optimised GeoTIFFs. Reading a pasture-sized window out of a
CONUS-wide COG over HTTP is a single range request, so no download, no
account, no API key.

Products used here (RAP v3):

* vegetation-biomass-v3-{year}.tif   band 1 = annual forb & grass (AFG)
                                     band 2 = perennial forb & grass (PFG)
                                     units: lb/acre, nodata 65535
* vegetation-cover-v3-{year}.tif     bands: AFG, BGR, LTR, PFG, SHR, TRE (%)

Both are annual: they describe the *last full growing season*, which is the
right number for planning stocking rates but not for "what is standing out
there this week". Within-season production (16-day) lives in Earth Engine;
see rap_gee.py.

URLs are configurable because RAP moves hosts occasionally. Check them with
`python -m scripts.check_rap` before a demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon

from .grid import ForageGrid, LocalFrame, empty_grid_for

BIOMASS_URL = os.environ.get(
    "RAP_BIOMASS_URL",
    "https://rangeland.ntsg.umt.edu/data/rap/rap-vegetation-biomass/v3/vegetation-biomass-v3-{year}.tif",
)
COVER_URL = os.environ.get(
    "RAP_COVER_URL",
    "https://rangeland.ntsg.umt.edu/data/rap/rap-vegetation-cover/v3/vegetation-cover-v3-{year}.tif",
)

COVER_BANDS = {"AFG": 1, "BGR": 2, "LTR": 3, "PFG": 4, "SHR": 5, "TRE": 6}


@dataclass
class RAPSource:
    """Reads RAP v3 annual biomass and cover for a pasture.

    `year=None` means "the most recent year that exists", probed backwards
    from last year. RAP usually publishes a season in the following spring.
    """

    year: int | None = None
    name: str = "rap"

    # -- public -------------------------------------------------------------
    def sample(self, poly_wgs: Polygon, frame: LocalFrame, res_m: float = 30.0) -> ForageGrid:

        year = self.year or self._latest_year()
        poly_local = frame.project(poly_wgs)
        g = empty_grid_for(poly_local, res_m=res_m)

        afg = self._read_band_to_grid(BIOMASS_URL.format(year=year), 1, poly_wgs, g, frame, "bilinear")
        pfg = self._read_band_to_grid(BIOMASS_URL.format(year=year), 2, poly_wgs, g, frame, "bilinear")
        tre = self._read_band_to_grid(COVER_URL.format(year=year), COVER_BANDS["TRE"], poly_wgs, g, frame, "average")
        shr = self._read_band_to_grid(COVER_URL.format(year=year), COVER_BANDS["SHR"], poly_wgs, g, frame, "average")

        biomass = afg + pfg
        g.biomass_lb_ac = np.where(g.mask, biomass, np.nan)
        g.tree_cover_pct = np.where(g.mask, np.nan_to_num(tre), 0.0)
        g.shrub_cover_pct = np.where(g.mask, np.nan_to_num(shr), 0.0)
        g.meta = {
            "source": self.name,
            "label": f"RAP v3 herbaceous biomass, {year} growing season",
            "year": year,
            "units": "lb DM/acre",
            "notes": [
                f"Annual herbaceous production for the {year} season (annual + perennial forbs and grasses).",
                "Production, not standing crop: it does not know what has already been eaten this year.",
                "Herbaceous only. Shrub and tree browse (which goats use) is not counted.",
                "30 m pixels; unreliable under tree canopy. Treed pixels are flagged, not trusted.",
            ],
        }
        return g

    # -- internals ----------------------------------------------------------
    def _latest_year(self) -> int:
        import datetime as dt

        import rasterio

        y = dt.date.today().year - 1
        for cand in (y, y - 1, y - 2):
            try:
                with rasterio.open(BIOMASS_URL.format(year=cand)):
                    return cand
            except Exception:  # noqa: BLE001 - probing
                continue
        raise RuntimeError(
            "Could not reach the RAP biomass rasters (offline, or the host moved). "
            "Use the synthetic surface, or point RAP_BIOMASS_URL / RAP_COVER_URL at the current files."
        )

    @staticmethod
    def _read_band_to_grid(
        url: str, band: int, poly_wgs: Polygon, g: ForageGrid, frame: LocalFrame, resampling: str
    ) -> np.ndarray:
        """Window-read one band around the pasture and warp it onto the local grid."""
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_origin
        from rasterio.warp import reproject
        from rasterio.windows import from_bounds

        minx, miny, maxx, maxy = poly_wgs.bounds
        pad = 0.002  # ~200 m so bilinear edges have neighbours
        dst = np.full((g.nrows, g.ncols), np.nan, dtype="float32")
        dst_transform = from_origin(g.x0, g.y1, g.res_m, g.res_m)

        with rasterio.open(url) as src:
            win = from_bounds(minx - pad, miny - pad, maxx + pad, maxy + pad, src.transform)
            win = win.round_offsets().round_lengths()
            data = src.read(band, window=win).astype("float32")
            nodata = src.nodata
            if nodata is not None:
                data[data == nodata] = np.nan
            src_transform = src.window_transform(win)
            reproject(
                source=data,
                destination=dst,
                src_transform=src_transform,
                src_crs=src.crs,
                src_nodata=np.nan,
                dst_transform=dst_transform,
                dst_crs=frame.crs,
                dst_nodata=np.nan,
                resampling=getattr(Resampling, resampling),
            )
        return dst.astype(float)
