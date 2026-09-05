"""Forage data sources.

A source turns a pasture polygon (WGS84) into a `ForageGrid`: herbaceous
biomass in lb/acre plus tree and shrub cover on a 30 m local grid.

Two implementations ship:

* `SyntheticSource`: a deterministic, plausible-looking pasture used for demos
  and tests when there is no network. It is labelled as synthetic everywhere
  it appears in the UI. It is never a fallback for real data.
* `RAPSource` (in rap.py): the Rangeland Analysis Platform, read straight from
  their public Cloud-Optimised GeoTIFFs. Real data, no API key.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from shapely.geometry import Polygon

from .grid import ForageGrid, LocalFrame, empty_grid_for


class ForageSource(Protocol):
    name: str

    def sample(self, poly_wgs: Polygon, frame: LocalFrame, res_m: float = 30.0) -> ForageGrid: ...


class SyntheticSource:
    """A made-up pasture with structure a rancher would recognise.

    A wetter swale running across the field carries more grass, a rocky knob
    carries less, one corner is treed (low confidence), and there is gentle
    noise everywhere. Seeded from the polygon centroid so it is stable across
    runs for the same pasture.
    """

    name = "synthetic"

    def __init__(self, base_lb_ac: float = 1800.0):
        self.base_lb_ac = base_lb_ac

    def sample(self, poly_wgs: Polygon, frame: LocalFrame, res_m: float = 30.0) -> ForageGrid:
        poly_local = frame.project(poly_wgs)
        g = empty_grid_for(poly_local, res_m=res_m)
        xs, ys = g.centroids()
        minx, miny, maxx, maxy = poly_local.bounds
        w = max(maxx - minx, 1.0)
        h = max(maxy - miny, 1.0)
        u = (xs - minx) / w  # 0..1 west->east
        v = (ys - miny) / h  # 0..1 south->north

        c = poly_wgs.centroid
        rng = np.random.default_rng(int(abs(c.x * 1000) + abs(c.y * 1000)) % (2**32))

        # Broad east-west gradient (say, the east end is a south-facing slope).
        base = self.base_lb_ac * (1.45 - 0.9 * u)
        # A swale: a diagonal band of higher production.
        swale = np.exp(-((v - (0.35 + 0.3 * u)) ** 2) / (2 * 0.06**2))
        # A rocky knob in the north-west.
        knob = np.exp(-(((u - 0.2) ** 2) + ((v - 0.8) ** 2)) / (2 * 0.12**2))
        noise = rng.normal(0.0, 0.06, size=xs.shape)
        biomass = base * (1.0 + 0.7 * swale - 0.7 * knob + noise)
        biomass = np.clip(biomass, 150.0, None)

        # A treed corner in the south-east: high tree cover, low herbaceous.
        tree = 90.0 * np.exp(-(((u - 0.97) ** 2) + ((v - 0.15) ** 2)) / (2 * 0.19**2))
        tree = np.clip(tree + rng.normal(0, 2.0, size=xs.shape), 0, 95)
        biomass = biomass * (1.0 - 0.8 * (tree / 100.0))
        shrub = np.clip(12.0 * knob + rng.normal(0, 1.5, size=xs.shape), 0, 60)

        g.biomass_lb_ac = np.where(g.mask, biomass, np.nan)
        g.tree_cover_pct = np.where(g.mask, tree, 0.0)
        g.shrub_cover_pct = np.where(g.mask, shrub, 0.0)
        g.meta = {
            "source": self.name,
            "label": "Synthetic demo pasture (not real data)",
            "year": None,
            "units": "lb DM/acre",
            "notes": [
                "This is a synthetic surface used to demonstrate the planner without network access.",
                "Swap in RAPSource for real Rangeland Analysis Platform data.",
            ],
        }
        return g
