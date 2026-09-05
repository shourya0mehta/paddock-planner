import base64

from fastapi.testclient import TestClient

from app.main import app
from app.presets import PRESETS

client = TestClient(app)


def _preset(pid: str) -> dict:
    return next(p for p in PRESETS if p["id"] == pid)


def test_health_and_presets():
    assert client.get("/api/health").json() == {"ok": True}
    ids = [p["id"] for p in client.get("/api/presets").json()]
    assert {"colorado", "texas", "california", "norway"} <= set(ids)


def test_plan_synthetic_end_to_end():
    p = _preset("colorado")
    body = {
        "pasture": p["pasture"],
        "water": p["water"],
        "herd": p["herd"],
        "utilization": 0.5,
        "n_strips": 6,
        "start_date": "2026-09-10",
        "source": "synthetic",
    }
    r = client.post("/api/plan", json=body)
    assert r.status_code == 200, r.text
    d = r.json()

    assert d["pasture"]["area_ac"] > 600
    assert d["assumptions"]["n_strips"] == 6
    assert len(d["equal_forage"]["strips"]) == 6
    assert len(d["equal_area"]["strips"]) == 6

    # Equal-forage strips have (nearly) equal grazing days; equal-area ones do not.
    ef = d["equal_forage"]
    ea = d["equal_area"]
    assert ef["days_max"] - ef["days_min"] < 0.1 * ef["days_max"]
    assert ea["days_max"] - ea["days_min"] > 0.3 * ea["days_max"]

    # Strips carry everything the UI needs.
    s = ef["strips"][0]
    for k in ("geometry", "area_ac", "forage_lb", "grazing_days", "start", "end", "confidence", "confidence_reasons"):
        assert k in s
    assert s["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert s["start"] == "2026-09-10"

    # Raster overlay is a real PNG with four corners.
    png = base64.b64decode(d["raster"]["png_base64"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(d["raster"]["coordinates"]) == 4

    assert d["source"]["source"] == "synthetic"
    assert d["rotation_check"]["ok"] is False  # no growth rate supplied


def test_plan_rejects_too_many_vertices():
    ring = [[-105.0 + i * 1e-5, 40.8 + (i % 2) * 1e-5] for i in range(600)] + [[-105.0, 40.8]]
    body = {"pasture": {"type": "Polygon", "coordinates": [ring]}, "herd": {"species": "cattle", "head": 10}}
    r = client.post("/api/plan", json=body)
    assert r.status_code == 422
    assert "500" in r.text


def test_plan_flags_oversize_pasture():
    # ~ 12,000 acres: a 7 km x 7 km square at 40.8N.
    dlat = 7000 / 111_320
    dlon = 7000 / (111_320 * 0.757)
    ring = [[-105.0, 40.8], [-105.0 + dlon, 40.8], [-105.0 + dlon, 40.8 + dlat], [-105.0, 40.8 + dlat], [-105.0, 40.8]]
    body = {
        "pasture": {"type": "Polygon", "coordinates": [ring]},
        "herd": {"species": "cattle", "head": 100},
        "n_strips": 3,
    }
    r = client.post("/api/plan", json=body)
    assert r.status_code == 200
    assert r.json()["pasture"]["over_size_limit"] is True
    assert any("10,000" in w for w in r.json()["warnings"])
