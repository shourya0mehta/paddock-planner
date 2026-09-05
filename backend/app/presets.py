"""Demo pastures. Real places, made-up boundaries.

The shapes are irregular on purpose: the strip algorithm has to cope with
concave pastures, and a rectangle would hide that.
"""

from __future__ import annotations

import math

# A concave, roughly 1 x 0.6 "unit" outline, going counter-clockwise.
_SHAPE = [
    (0.00, 0.10),
    (0.18, 0.00),
    (0.42, 0.04),
    (0.62, 0.00),
    (0.85, 0.08),
    (1.00, 0.22),
    (0.97, 0.45),
    (0.86, 0.60),
    (0.70, 0.56),
    (0.58, 0.64),
    (0.40, 0.60),
    (0.30, 0.50),
    (0.22, 0.58),
    (0.08, 0.52),
    (0.00, 0.35),
]


def _polygon(lon: float, lat: float, acres: float, rotate_deg: float = 0.0) -> dict:
    """Place the unit outline at (lon, lat) scaled to `acres`, rotated."""
    unit_area = _shoelace(_SHAPE)
    target_m2 = acres * 4046.8564224
    scale = math.sqrt(target_m2 / unit_area)
    th = math.radians(rotate_deg)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    ring = []
    cx, cy = 0.5, 0.3
    for x, y in _SHAPE:
        dx, dy = (x - cx) * scale, (y - cy) * scale
        rx = dx * math.cos(th) - dy * math.sin(th)
        ry = dx * math.sin(th) + dy * math.cos(th)
        ring.append([round(lon + rx / m_per_deg_lon, 6), round(lat + ry / m_per_deg_lat, 6)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _shoelace(pts):
    s = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


PRESETS = [
    {
        "id": "colorado",
        "name": "Front Range, Colorado",
        "blurb": "Shortgrass steppe north of Fort Collins. Cow-calf country, and Nofence US is down the road.",
        "center": [-105.0553, 40.8614],
        "pasture": _polygon(-105.0553, 40.8614, 640, rotate_deg=15),
        "water": [-105.058, 40.86],
        "herd": {"species": "cattle", "head": 250, "avg_weight_lb": 1200},
        "source": "rap",
    },
    {
        "id": "texas",
        "name": "Hill Country, Texas",
        "blurb": "Small paddocks with tired fences: the customer Nofence quotes in its US press.",
        "center": [-98.93, 30.32],
        "pasture": _polygon(-98.93, 30.32, 220, rotate_deg=-30),
        "water": [-98.926, 30.322],
        "herd": {"species": "cattle", "head": 90, "avg_weight_lb": 1100},
        "source": "rap",
    },
    {
        "id": "california",
        "name": "Coastal hills, Santa Barbara County",
        "blurb": "Goats on fuel-reduction duty under coast live oak. Tree cover is where the model is least sure.",
        "center": [-120.18, 34.52],
        "pasture": _polygon(-120.18, 34.52, 300, rotate_deg=40),
        "water": [-120.176, 34.523],
        "herd": {"species": "goats", "head": 800, "avg_weight_lb": 120},
        "source": "rap",
    },
    {
        "id": "norway",
        "name": "Batnfjordsøra, Norway",
        "blurb": (
            "Where Nofence started. Outside RAP coverage, so this one runs on the synthetic surface "
            "until a European forage source is wired in (Sentinel-2 is the obvious candidate)."
        ),
        "center": [7.72, 62.89],
        "pasture": _polygon(7.72, 62.89, 45, rotate_deg=10),
        "water": [7.7215, 62.8885],
        "herd": {"species": "sheep", "head": 120, "avg_weight_lb": 150},
        "source": "synthetic",
    },
]
