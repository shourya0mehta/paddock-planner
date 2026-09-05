export type Species = "cattle" | "sheep" | "goats";

export interface Preset {
  id: string;
  name: string;
  blurb: string;
  center: [number, number];
  pasture: GeoJSON.Polygon;
  water: [number, number] | null;
  herd: { species: Species; head: number; avg_weight_lb: number };
  source: "rap" | "synthetic";
}

export interface PlanRequest {
  pasture: GeoJSON.Polygon;
  water: [number, number] | null;
  herd: { species: Species; head: number; avg_weight_lb: number | null };
  utilization: number;
  n_strips: number | null;
  target_days_per_strip: number;
  start_date: string | null;
  source: "rap" | "synthetic";
  growth_lb_ac_day: number | null;
}

export interface StripOut {
  index: number;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon;
  area_ac: number;
  forage_lb: number;
  forage_lb_ac: number;
  grazing_days: number;
  start: string;
  end: string;
  rest_days_needed: number | null;
  ready_again: string | null;
  confidence: "high" | "medium" | "low";
  confidence_reasons: string[];
  tree_cover_pct: number;
  shrub_cover_pct: number;
  parts: number;
}

export interface PlanOut {
  mode: "forage" | "area";
  strips: StripOut[];
  total_days: number;
  days_min: number;
  days_max: number;
}

export interface PlanResponse {
  pasture: {
    area_ac: number;
    forage_lb_total: number;
    forage_lb_ac_mean: number;
    grazing_days_total: number;
    vertices: number;
    over_size_limit: boolean;
  };
  herd: { species: Species; head: number; avg_weight_lb: number; animal_units: number; demand_lb_per_day: number };
  assumptions: Record<string, unknown> & { n_strips: number; start_date: string };
  source: { source: string; label: string; year: number | null; units: string; notes: string[] };
  equal_forage: PlanOut;
  equal_area: PlanOut;
  raster: { png_base64: string; coordinates: [number, number][]; legend: { min_lb_ac: number; max_lb_ac: number; units: string } };
  rotation_check: { ok: boolean; message: string };
  notes: string[];
  warnings: string[];
}

export async function fetchPresets(): Promise<Preset[]> {
  const r = await fetch("/api/presets");
  if (!r.ok) throw new Error(`presets: ${r.status}`);
  return r.json();
}

export async function postPlan(req: PlanRequest): Promise<PlanResponse> {
  const r = await fetch("/api/plan", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const j = await r.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return r.json();
}

export function planToGeoJSON(res: PlanResponse, pasture: GeoJSON.Polygon, water: [number, number] | null, mode: "forage" | "area") {
  const plan = mode === "forage" ? res.equal_forage : res.equal_area;
  const features: GeoJSON.Feature[] = plan.strips.map((s) => ({
    type: "Feature",
    geometry: s.geometry,
    properties: {
      kind: "strip",
      order: s.index,
      area_ac: s.area_ac,
      forage_lb: s.forage_lb,
      forage_lb_ac: s.forage_lb_ac,
      grazing_days: s.grazing_days,
      start: s.start,
      end: s.end,
      confidence: s.confidence,
      notes: s.confidence_reasons.join("; "),
    },
  }));
  features.push({ type: "Feature", geometry: pasture, properties: { kind: "pasture", area_ac: res.pasture.area_ac } });
  if (water) features.push({ type: "Feature", geometry: { type: "Point", coordinates: water }, properties: { kind: "water" } });
  return { type: "FeatureCollection", features, properties: { mode, source: res.source.label, assumptions: res.assumptions } };
}
