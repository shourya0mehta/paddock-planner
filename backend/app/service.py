"""The one function the API calls: polygon in, plan out."""

from __future__ import annotations

import datetime as dt

from .forage.grid import LocalFrame, geojson_from_geometry, polygon_from_geojson
from .forage.sources import ForageSource, SyntheticSource
from .planner.confidence import grade_strip, pasture_notes
from .planner.herd import Herd, grazing_days
from .planner.rotation import rotation_closes, schedule, total_days
from .planner.strips import auto_strip_count, partition
from .render import forage_png
from .schemas import MAX_ACRES, PastureOut, PlanOut, PlanRequest, PlanResponse, StripOut


def make_source(req: PlanRequest) -> ForageSource:
    if req.source == "rap":
        from .forage.rap import RAPSource

        return RAPSource(year=req.rap_year)
    return SyntheticSource()


def build_plan(req: PlanRequest, source: ForageSource | None = None) -> PlanResponse:
    source = source or make_source(req)
    poly_wgs = polygon_from_geojson(req.pasture)
    frame = LocalFrame.for_polygon(poly_wgs)
    poly_local = frame.project(poly_wgs)
    water_local = tuple(frame.to_local.transform(*req.water)) if req.water else None

    grid = source.sample(poly_wgs, frame)
    herd = Herd(species=req.herd.species, head=req.herd.head, avg_weight_lb=req.herd.avg_weight_lb)
    start = req.start_date or dt.date.today()

    area_ac = poly_local.area / 4046.8564224
    forage_total = grid.forage_lb_total()
    days_total = grazing_days(forage_total, req.utilization, herd) if forage_total > 0 else 0.0
    n = req.n_strips or auto_strip_count(days_total, req.target_days_per_strip)

    warnings: list[str] = []
    if area_ac > MAX_ACRES:
        warnings.append(f"Pasture is {area_ac:,.0f} acres; Nofence's single-pasture limit is {MAX_ACRES:,}.")
    if forage_total <= 0:
        warnings.append("No forage pixels found inside the pasture.")

    def run(mode: str) -> tuple[PlanOut, list]:
        strips = partition(poly_local, grid, n, mode=mode, water_local=water_local)
        stays = schedule(strips, herd, req.utilization, start, growth_lb_ac_day=req.growth_lb_ac_day)
        out = []
        for s, st in zip(strips, stays, strict=True):
            conf = grade_strip(s, herd.species, grid.meta.get("source", "unknown"))
            out.append(
                StripOut(
                    index=s.index,
                    geometry=geojson_from_geometry(frame.unproject(s.geometry)),
                    area_ac=round(s.area_ac, 2),
                    forage_lb=round(s.forage_lb),
                    forage_lb_ac=round(s.forage_lb_ac),
                    grazing_days=round(st.days, 2),
                    start=st.start,
                    end=st.end,
                    rest_days_needed=None if st.rest_days_needed is None else round(st.rest_days_needed, 1),
                    ready_again=st.ready_again,
                    confidence=conf.grade,
                    confidence_reasons=conf.reasons,
                    tree_cover_pct=round(s.tree_cover_pct, 1),
                    shrub_cover_pct=round(s.shrub_cover_pct, 1),
                    parts=s.parts,
                )
            )
        days = [o.grazing_days for o in out] or [0.0]
        plan = PlanOut(
            mode=mode, strips=out, total_days=round(total_days(stays), 2), days_min=min(days), days_max=max(days)
        )
        return plan, stays

    equal_forage, forage_stays = run("forage")
    equal_area, _ = run("area")
    ok, msg = rotation_closes(forage_stays)

    return PlanResponse(
        pasture=PastureOut(
            area_ac=round(area_ac, 1),
            forage_lb_total=round(forage_total),
            forage_lb_ac_mean=round(forage_total / area_ac) if area_ac > 0 else 0,
            grazing_days_total=round(days_total, 1),
            vertices=len(poly_wgs.exterior.coords) - 1,
            over_size_limit=area_ac > MAX_ACRES,
        ),
        herd={
            "species": herd.species,
            "head": herd.head,
            "avg_weight_lb": herd.weight_lb,
            "animal_units": round(herd.animal_units, 1),
            "demand_lb_per_day": round(herd.demand_lb_per_day),
        },
        assumptions={
            "utilization": req.utilization,
            "intake_fraction_of_bw": 0.026,
            "n_strips": n,
            "target_days_per_strip": req.target_days_per_strip,
            "start_date": start.isoformat(),
            "growth_lb_ac_day": req.growth_lb_ac_day,
            "pixel_m": grid.res_m,
        },
        source=grid.meta,
        equal_forage=equal_forage,
        equal_area=equal_area,
        raster=forage_png(grid, frame),
        rotation_check={"ok": ok, "message": msg},
        notes=pasture_notes(grid.meta, herd.species),
        warnings=warnings,
    )
