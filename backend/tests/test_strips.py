import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

from app.forage.grid import ForageGrid, empty_grid_for
from app.planner.strips import auto_strip_count, choose_axis, partition

SQM_PER_ACRE = 4046.8564224


def _grid(poly: Polygon, biomass_fn, res_m: float = 30.0) -> ForageGrid:
    g = empty_grid_for(poly, res_m=res_m)
    xs, ys = g.centroids()
    g.biomass_lb_ac = np.where(g.mask, biomass_fn(xs, ys), np.nan)
    return g


def rect(w: float, h: float) -> Polygon:
    return Polygon([(0, 0), (w, 0), (w, h), (0, h)])


def test_uniform_forage_gives_equal_area_strips():
    poly = rect(3000, 900)
    g = _grid(poly, lambda x, y: np.full_like(x, 2000.0))
    strips = partition(poly, g, 5)
    assert len(strips) == 5
    areas = np.array([s.area_ac for s in strips])
    assert np.allclose(areas, areas.mean(), rtol=0.03)
    # Strips are cut across the long (x) axis: each spans the full 900 m height.
    for s in strips:
        _, miny, _, maxy = s.geometry.bounds
        assert maxy - miny == pytest.approx(900, abs=1)


def test_gradient_forage_gives_equal_forage_not_equal_area():
    poly = rect(3000, 600)
    # Forage climbs steeply from west to east.
    g = _grid(poly, lambda x, y: 400.0 + 2400.0 * (x / 3000.0))
    strips = partition(poly, g, 4, mode="forage")
    forage = np.array([s.forage_lb for s in strips])
    areas = np.array([s.area_ac for s in strips])
    assert np.allclose(forage, forage.mean(), rtol=0.05), forage
    assert areas.max() / areas.min() > 1.8, areas  # visibly unequal areas
    # Every pixel ends up in exactly one strip: totals are conserved.
    assert forage.sum() == pytest.approx(g.forage_lb_total(), rel=1e-6)
    assert areas.sum() == pytest.approx(poly.area / SQM_PER_ACRE, rel=1e-6)


def test_equal_area_mode_ignores_forage():
    poly = rect(3000, 600)
    g = _grid(poly, lambda x, y: 400.0 + 2400.0 * (x / 3000.0))
    strips = partition(poly, g, 4, mode="area")
    areas = np.array([s.area_ac for s in strips])
    assert np.allclose(areas, areas.mean(), rtol=0.03)


def test_water_point_sets_the_starting_end():
    poly = rect(3000, 600)
    g = _grid(poly, lambda x, y: np.full_like(x, 1500.0))
    west = partition(poly, g, 3, water_local=(0.0, 300.0))
    east = partition(poly, g, 3, water_local=(3000.0, 300.0))
    assert west[0].geometry.centroid.x < west[-1].geometry.centroid.x
    assert east[0].geometry.centroid.x > east[-1].geometry.centroid.x


def test_concave_pasture_can_yield_multipart_strip_and_conserves_area():
    # A "C" shape: a band across the open side is split into two pieces.
    outer = rect(3000, 3000)
    notch = Polygon([(1200, -10), (1800, -10), (1800, 2200), (1200, 2200)])
    poly = outer.difference(notch)
    g = _grid(poly, lambda x, y: np.full_like(x, 1000.0))
    strips = partition(poly, g, 5, mode="area")
    assert any(s.parts > 1 for s in strips)
    assert sum(s.area_ac for s in strips) == pytest.approx(poly.area / SQM_PER_ACRE, rel=1e-6)
    assert all(s.geometry.is_valid for s in strips)


def test_axis_follows_long_side():
    tall = rect(500, 4000)
    ax = choose_axis(tall)
    assert abs(ax.u[1]) > 0.99  # advances along y
    wide = rect(4000, 500)
    ax = choose_axis(wide)
    assert abs(ax.u[0]) > 0.99


def test_more_strips_than_pixels_is_clamped():
    poly = rect(90, 60)  # 3 x 2 pixels
    g = _grid(poly, lambda x, y: np.full_like(x, 1000.0))
    strips = partition(poly, g, 50)
    assert 1 <= len(strips) <= 6


def test_auto_strip_count_bounds():
    assert auto_strip_count(0) == 2
    assert auto_strip_count(9, target_days_per_strip=3) == 3
    assert auto_strip_count(1000, target_days_per_strip=1) == 16


def test_rejects_empty_pasture():
    poly = rect(3000, 600)
    g = _grid(poly, lambda x, y: np.full_like(x, np.nan))
    with pytest.raises(ValueError):
        partition(poly, g, 3)


def test_strip_geometries_are_disjoint_and_cover_pasture():
    poly = rect(2400, 900)
    g = _grid(poly, lambda x, y: 800.0 + 1200.0 * (y / 900.0) + 600.0 * (x / 2400.0))
    strips = partition(poly, g, 6)
    union = shapely.unary_union([s.geometry for s in strips])
    assert union.area == pytest.approx(poly.area, rel=1e-6)
    for i, a in enumerate(strips):
        for b in strips[i + 1 :]:
            assert a.geometry.intersection(b.geometry).area < 1.0
