"""Paddock Planner API.

POST /api/plan      polygon + herd -> equal-forage strips, calendar, raster
GET  /api/presets   demo pastures
GET  /api/health

The built frontend (frontend/dist) is served from / when present, so one
container is the whole app.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .presets import PRESETS
from .schemas import PlanRequest, PlanResponse
from .service import build_plan

log = logging.getLogger("paddock")
app = FastAPI(title="Paddock Planner", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/presets")
def presets() -> list[dict]:
    return PRESETS


@app.post("/api/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    try:
        return build_plan(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("plan failed")
        # Real-data failures (no network, RAP host moved) should be readable, not a 500 wall.
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e


_DIST = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = _DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")
