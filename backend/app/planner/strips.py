"""Split a pasture into strips of equal *forage* rather than equal area.

Physical fences get built where they are cheap to build, so paddocks end up
equal-area at best and the animals spend three days in one and nine in the
next. A virtual fence costs nothing to redraw, so the boundaries can follow
the feed. This module does that.

Method
------
1. Pick an axis. We use the long side of the pasture's minimum rotated
   rectangle, so strips are cut across the short dimension, which is how
   people strip-graze anyway. If a water point is given, the sequence starts
   at the end nearest the water.
2. Project every 30 m pixel centre inside the pasture onto the axis and sort.
3. Walk the cumulative forage and cut wherever it crosses k/N of the total,
   interpolating between neighbouring pixels so cuts are not snapped to the
   grid.
4. Turn each interval into a band polygon and intersect it with the pasture.

The same routine with unit weights gives equal-area strips, which is what
the UI shows side by side so the difference is visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from ..forage.grid import ForageGrid


@dataclass
class Axis:
    center: np.ndarray  # (2,)
    u: np.ndarray  # unit vector along which strips advance
    v: np.ndarray  # perpendicular unit vector

    def t(self, xy: np.ndarray) -> np.ndarray:
        return (xy - self.center) @ self.u

    def s(self, xy: np.ndarray) -> np.ndarray:
        return (xy - self.center) @ self.v


@dataclass
class Strip:
    index: int  # 1-based grazing order
    geometry: BaseGeometry  # local CRS
    area_ac: float
    forage_lb: float
    forage_lb_ac: float
    tree_cover_pct: float
    shrub_cover_pct: float
    frac_treed: float
    parts: int = 1
    t_from: float = 0.0
    t_to: float = 0.0
    extra: dict = field(default_factory=dict)


def choose_axis(poly_local: Polygon, water_local: tuple[float, float] | None = None) -> Axis:
    """Long axis of the pasture, oriented so `t` increases away from water."""
    rect = poly_local.minimum_rotated_rectangle
    pts = np.asarray(rect.exterior.coords)[:4]
    edges = [pts[(i + 1) % 4] - pts[i] for i in range(4)]
    lengths = [float(np.hypot(*e)) for e in edges]
    longest = edges[int(np.argmax(lengths))]
    u = longest / (np.linalg.norm(longest) + 1e-12)
    v = np.array([-u[1], u[0]])
    center = np.asarray(poly_local.centroid.coords[0])
    axis = Axis(center=center, u=u, v=v)

    if water_local is not None:
        coords = np.asarray(poly_local.exterior.coords)
        t_poly = axis.t(coords)
        t_w = float(axis.t(np.asarray(water_local, dtype=float)))
        # Start where the water is: flip if the water sits nearer the far end.
        if abs(t_w - t_poly.max()) < abs(t_w - t_poly.min()):
            axis = Axis(center=center, u=-u, v=-v)
    return axis


def auto_strip_count(total_days: float, target_days_per_strip: float = 5.0, lo: int = 2, hi: int = 16) -> int:
    if total_days <= 0:
        return lo
    return int(min(hi, max(lo, round(total_days / target_days_per_strip))))


def _cut_positions(t: np.ndarray, w: np.ndarray, n: int) -> list[float]:
    """Axis positions where cumulative weight crosses k/n of the total.

    Pixels that share an axis position (a whole column, when the pasture is
    axis-aligned) are treated as one lump, and each cut is placed halfway
    between two lumps so no pixel centre ever sits on a cut line. Strips are
    therefore equal to within one pixel-column of forage, and every pixel
    lands in exactly one strip.
    """
    if n <= 1 or len(t) == 0:
        return []
    order = np.argsort(t, kind="stable")
    t_sorted = t[order]
    w_sorted = np.clip(w[order], 0.0, None)
    # Lump identical positions (to 1 mm) together.
    keys = np.round(t_sorted, 3)
    uniq, idx = np.unique(keys, return_index=True)
    lump_w = np.add.reduceat(w_sorted, idx)
    total = float(lump_w.sum())
    if total <= 0.0 or len(uniq) < 2:
        return []
    cum = np.cumsum(lump_w)
    cuts: list[float] = []
    last_j = -1
    for k in range(1, n):
        target = total * k / n
        j = int(np.searchsorted(cum, target, side="left"))  # first lump that reaches the target
        j = min(j, len(uniq) - 1)
        # Decide whether the crossing lump goes left or right of the cut: whichever is closer.
        before = cum[j - 1] if j > 0 else 0.0
        put_right = (target - before) < (cum[j] - target)
        boundary = j if put_right else j + 1  # cut sits before lump `boundary`
        boundary = int(np.clip(boundary, last_j + 2, len(uniq) - 1))
        if boundary >= len(uniq):
            break
        cuts.append(float((uniq[boundary - 1] + uniq[boundary]) / 2.0))
        last_j = boundary - 1
    return cuts


def _band(axis: Axis, t_a: float, t_b: float, s_lo: float, s_hi: float) -> Polygon:
    c, u, v = axis.center, axis.u, axis.v
    corners = [
        c + t_a * u + s_lo * v,
        c + t_b * u + s_lo * v,
        c + t_b * u + s_hi * v,
        c + t_a * u + s_hi * v,
    ]
    return Polygon([tuple(p) for p in corners])


def partition(
    poly_local: Polygon,
    grid: ForageGrid,
    n: int,
    mode: str = "forage",
    water_local: tuple[float, float] | None = None,
) -> list[Strip]:
    """Cut `poly_local` into `n` strips of equal forage (or equal area)."""
    if mode not in ("forage", "area"):
        raise ValueError("mode must be 'forage' or 'area'")
    xs, ys = grid.centroids()
    inside = grid.mask & np.isfinite(grid.biomass_lb_ac)
    pts = np.column_stack([xs[inside], ys[inside]])
    if len(pts) == 0:
        raise ValueError("pasture contains no forage pixels")
    n = int(max(1, min(n, len(pts))))

    axis = choose_axis(poly_local, water_local)
    t = axis.t(pts)
    w = grid.biomass_lb_ac[inside] if mode == "forage" else np.ones(len(pts))
    cuts = _cut_positions(t, w, n)

    coords = np.asarray(poly_local.exterior.coords)
    t_poly = axis.t(coords)
    s_poly = axis.s(coords)
    margin = grid.res_m * 2
    edges = [float(t_poly.min()) - margin, *cuts, float(t_poly.max()) + margin]
    s_lo, s_hi = float(s_poly.min()) - margin, float(s_poly.max()) + margin

    # Assign every pixel to a strip by its axis position, so stats and cuts agree exactly.
    interior = np.asarray(cuts, dtype=float)
    pixel_strip = np.searchsorted(interior, t, side="right")  # 0..len(cuts)

    strips: list[Strip] = []
    for i in range(len(edges) - 1):
        band = _band(axis, edges[i], edges[i + 1], s_lo, s_hi)
        geom = poly_local.intersection(band)
        geom = _drop_slivers(geom, grid.res_m)
        if geom.is_empty:
            continue
        sel = pixel_strip == i
        st = _stats(grid, inside, sel)
        parts = len(geom.geoms) if geom.geom_type == "MultiPolygon" else 1
        strips.append(
            Strip(
                index=len(strips) + 1,
                geometry=geom,
                area_ac=float(geom.area / 4046.8564224),
                forage_lb=st["forage_lb"],
                forage_lb_ac=st["forage_lb_ac"],
                tree_cover_pct=st["tree_cover_pct"],
                shrub_cover_pct=st["shrub_cover_pct"],
                frac_treed=st["frac_treed"],
                parts=parts,
                t_from=edges[i],
                t_to=edges[i + 1],
            )
        )
    return strips


def _stats(grid: ForageGrid, inside: np.ndarray, sel: np.ndarray) -> dict:
    """Aggregate forage and cover for the selected pixels (sel indexes the `inside` pixels)."""
    b = grid.biomass_lb_ac[inside][sel]
    tr = grid.tree_cover_pct[inside][sel]
    sh = grid.shrub_cover_pct[inside][sel]
    n = int(sel.sum())
    if n == 0:
        return {"forage_lb": 0.0, "forage_lb_ac": 0.0, "tree_cover_pct": 0.0, "shrub_cover_pct": 0.0, "frac_treed": 0.0}
    return {
        "forage_lb": float(np.nansum(b) * grid.pixel_area_ac),
        "forage_lb_ac": float(np.nanmean(b)),
        "tree_cover_pct": float(np.nanmean(tr)),
        "shrub_cover_pct": float(np.nanmean(sh)),
        "frac_treed": float(np.mean(tr > 30.0)),
    }


def _drop_slivers(geom: BaseGeometry, res_m: float) -> BaseGeometry:
    """Remove polygon parts thinner than a pixel; they are cut artefacts, not paddocks."""
    if geom.is_empty:
        return geom
    min_area = 0.25 * res_m * res_m
    if geom.geom_type == "Polygon":
        return geom if geom.area >= min_area else shapely.Polygon()
    if geom.geom_type == "MultiPolygon":
        keep = [g for g in geom.geoms if g.area >= min_area]
        if not keep:
            return shapely.Polygon()
        return keep[0] if len(keep) == 1 else shapely.MultiPolygon(keep)
    if geom.geom_type == "GeometryCollection":
        polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        return _drop_slivers(shapely.unary_union(polys), res_m) if polys else shapely.Polygon()
    return shapely.Polygon()
