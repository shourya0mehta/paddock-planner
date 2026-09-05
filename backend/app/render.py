"""Render the forage grid to a PNG the map can drape over the pasture."""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from .forage.grid import ForageGrid, LocalFrame

# Straw -> grass green. Light where there is little to eat, saturated where there is a lot.
_STOPS = [
    (0.00, (247, 236, 195)),
    (0.35, (214, 220, 130)),
    (0.65, (140, 182, 92)),
    (1.00, (39, 110, 61)),
]


def _colormap(x: np.ndarray) -> np.ndarray:
    """x in [0,1] -> RGB uint8 array (..., 3)."""
    out = np.zeros(x.shape + (3,), dtype=np.uint8)
    for i in range(len(_STOPS) - 1):
        p0, c0 = _STOPS[i]
        p1, c1 = _STOPS[i + 1]
        sel = (x >= p0) & (x <= p1)
        f = np.where(p1 > p0, (x - p0) / (p1 - p0), 0.0)
        for ch in range(3):
            out[..., ch] = np.where(sel, (c0[ch] + f * (c1[ch] - c0[ch])).astype(np.uint8), out[..., ch])
    return out


def forage_png(grid: ForageGrid, frame: LocalFrame, upscale: int = 4) -> dict:
    """PNG (base64) of biomass, plus the four corners in WGS84 for an image source."""
    b = grid.biomass_lb_ac
    valid = grid.mask & np.isfinite(b)
    if valid.any():
        lo = float(np.nanpercentile(b[valid], 2))
        hi = float(np.nanpercentile(b[valid], 98))
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo:
        hi = lo + 1.0
    x = np.clip((np.nan_to_num(b, nan=lo) - lo) / (hi - lo), 0, 1)
    rgb = _colormap(x)
    alpha = np.where(valid, 200, 0).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])
    img = Image.fromarray(rgba, mode="RGBA")
    if upscale > 1:
        img = img.resize((img.width * upscale, img.height * upscale), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    corners = [frame.to_wgs.transform(x_, y_) for (x_, y_) in grid.corners_local()]
    return {
        "png_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
        "coordinates": [[lon, lat] for (lon, lat) in corners],  # NW, NE, SE, SW
        "legend": {"min_lb_ac": round(lo), "max_lb_ac": round(hi), "units": "lb DM/acre"},
    }
