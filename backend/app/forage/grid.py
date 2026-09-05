"""Local-grid utilities.

Everything the planner does happens on a small, regular grid in a local
metric CRS (UTM zone of the pasture centroid). Pixels are 30 m by default to
match the Rangeland Analysis Platform, which is the coarsest input we use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform as shp_transform

SQM_PER_ACRE = 4046.8564224


def utm_crs_for(lon: float, lat: float) -> CRS:
    """UTM zone CRS containing the point. Good to a few cm over a pasture."""
    zone = int((lon + 180) // 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


@dataclass
class LocalFrame:
    """A WGS84 <-> local metric CRS pair for one pasture."""

    crs: CRS
    to_local: Transformer
    to_wgs: Transformer

    @classmethod
    def for_polygon(cls, poly_wgs: Polygon) -> LocalFrame:
        c = poly_wgs.centroid
        crs = utm_crs_for(c.x, c.y)
        wgs = CRS.from_epsg(4326)
        return cls(
            crs=crs,
            to_local=Transformer.from_crs(wgs, crs, always_xy=True),
            to_wgs=Transformer.from_crs(crs, wgs, always_xy=True),
        )

    def project(self, geom):
        return shp_transform(self.to_local.transform, geom)

    def unproject(self, geom):
        return shp_transform(self.to_wgs.transform, geom)


@dataclass
class ForageGrid:
    """A regular grid over a pasture, in the local CRS.

    2-D arrays are (rows, cols) with row 0 at the *north* edge, like a raster.
    `mask` is True inside the pasture. `biomass_lb_ac` is herbaceous forage in
    pounds of dry matter per acre. Cover fractions are percent (0-100).
    """

    x0: float  # west edge of the grid (local CRS, metres)
    y1: float  # north edge of the grid
    res_m: float
    mask: np.ndarray
    biomass_lb_ac: np.ndarray
    tree_cover_pct: np.ndarray
    shrub_cover_pct: np.ndarray
    meta: dict = field(default_factory=dict)

    # ---- geometry helpers -------------------------------------------------
    @property
    def nrows(self) -> int:
        return int(self.mask.shape[0])

    @property
    def ncols(self) -> int:
        return int(self.mask.shape[1])

    @property
    def pixel_area_ac(self) -> float:
        return (self.res_m * self.res_m) / SQM_PER_ACRE

    def centroids(self) -> tuple[np.ndarray, np.ndarray]:
        """Pixel-centre coordinates as 2-D arrays (xs, ys)."""
        cols = np.arange(self.ncols)
        rows = np.arange(self.nrows)
        xs = self.x0 + (cols + 0.5) * self.res_m
        ys = self.y1 - (rows + 0.5) * self.res_m
        return np.meshgrid(xs, ys)

    def corners_local(self) -> list[tuple[float, float]]:
        """Grid corners [NW, NE, SE, SW] in the local CRS."""
        x1 = self.x0 + self.ncols * self.res_m
        y0 = self.y1 - self.nrows * self.res_m
        return [(self.x0, self.y1), (x1, self.y1), (x1, y0), (self.x0, y0)]

    # ---- aggregate helpers ------------------------------------------------
    def forage_lb_total(self) -> float:
        return float(np.nansum(self.biomass_lb_ac[self.mask]) * self.pixel_area_ac)

    def area_ac(self) -> float:
        return float(self.mask.sum() * self.pixel_area_ac)

    def stats_within(self, geom_local) -> dict:
        """Sum forage and mean cover for pixels whose centre falls in `geom_local`."""
        xs, ys = self.centroids()
        inside = self.mask & shapely.contains_xy(geom_local, xs, ys)
        n = int(inside.sum())
        if n == 0:
            return {
                "pixels": 0,
                "area_ac": 0.0,
                "forage_lb": 0.0,
                "forage_lb_ac": 0.0,
                "tree_cover_pct": 0.0,
                "shrub_cover_pct": 0.0,
                "frac_treed": 0.0,
            }
        b = self.biomass_lb_ac[inside]
        t = self.tree_cover_pct[inside]
        s = self.shrub_cover_pct[inside]
        return {
            "pixels": n,
            "area_ac": n * self.pixel_area_ac,
            "forage_lb": float(np.nansum(b) * self.pixel_area_ac),
            "forage_lb_ac": float(np.nanmean(b)),
            "tree_cover_pct": float(np.nanmean(t)),
            "shrub_cover_pct": float(np.nanmean(s)),
            "frac_treed": float(np.mean(t > 30.0)),
        }


def empty_grid_for(poly_local: Polygon, res_m: float = 30.0, pad_px: int = 1) -> ForageGrid:
    """Allocate a grid that covers the polygon, with the pasture mask filled in."""
    minx, miny, maxx, maxy = poly_local.bounds
    x0 = np.floor(minx / res_m) * res_m - pad_px * res_m
    y1 = np.ceil(maxy / res_m) * res_m + pad_px * res_m
    ncols = int(np.ceil((maxx - x0) / res_m)) + pad_px
    nrows = int(np.ceil((y1 - miny) / res_m)) + pad_px
    g = ForageGrid(
        x0=float(x0),
        y1=float(y1),
        res_m=res_m,
        mask=np.zeros((nrows, ncols), dtype=bool),
        biomass_lb_ac=np.full((nrows, ncols), np.nan, dtype=float),
        tree_cover_pct=np.zeros((nrows, ncols), dtype=float),
        shrub_cover_pct=np.zeros((nrows, ncols), dtype=float),
    )
    xs, ys = g.centroids()
    g.mask = shapely.contains_xy(poly_local, xs, ys)
    return g


def polygon_from_geojson(geojson: dict) -> Polygon:
    geom = shape(geojson)
    if geom.geom_type == "MultiPolygon":
        # Take the largest part. Multi-part pastures are a v2 problem.
        geom = max(geom.geoms, key=lambda g: g.area)
    if geom.geom_type != "Polygon":
        raise ValueError(f"pasture must be a Polygon, got {geom.geom_type}")
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


def geojson_from_geometry(geom) -> dict:
    return mapping(geom)
