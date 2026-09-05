import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import MapboxDraw from "@mapbox/mapbox-gl-draw";
import "maplibre-gl/dist/maplibre-gl.css";
import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";
import type { PlanResponse } from "./api";

// mapbox-gl-draw was written for Mapbox GL; these class names make it work on MapLibre.
const C = (MapboxDraw as unknown as { constants: { classes: Record<string, string> } }).constants.classes;
C.CANVAS = "maplibregl-canvas";
C.CONTROL_BASE = "maplibregl-ctrl";
C.CONTROL_PREFIX = "maplibregl-ctrl-";
C.CONTROL_GROUP = "maplibregl-ctrl-group";
C.ATTRIBUTION = "maplibregl-ctrl-attrib";

// Worker files are copied to public/maplibre by scripts/copy-maplibre-worker.mjs (runs before dev/build).
maplibregl.setWorkerUrl(`${import.meta.env.BASE_URL}maplibre/maplibre-gl-worker.mjs`);

const IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

export interface MapViewProps {
  pasture: GeoJSON.Polygon | null;
  water: [number, number] | null;
  result: PlanResponse | null;
  mode: "forage" | "area";
  compare: boolean;
  showForage: boolean;
  settingWater: boolean;
  focusToken: number; // bump to re-fit the map to the pasture
  hovered: number | null;
  onPasture: (p: GeoJSON.Polygon | null) => void;
  onWater: (w: [number, number]) => void;
  onHover: (i: number | null) => void;
}

const drawStyles = [
  { id: "gl-draw-polygon-fill", type: "fill", filter: ["all", ["==", "$type", "Polygon"]], paint: { "fill-color": "#ffffff", "fill-opacity": 0.06 } },
  { id: "gl-draw-polygon-stroke", type: "line", filter: ["all", ["==", "$type", "Polygon"]], layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#ffffff", "line-width": 2.5 } },
  { id: "gl-draw-line", type: "line", filter: ["all", ["==", "$type", "LineString"]], paint: { "line-color": "#ffffff", "line-width": 2.5, "line-dasharray": [2, 2] } },
  { id: "gl-draw-vertex-halo", type: "circle", filter: ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"]], paint: { "circle-radius": 7, "circle-color": "#1f2a22" } },
  { id: "gl-draw-vertex", type: "circle", filter: ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"]], paint: { "circle-radius": 4.5, "circle-color": "#ffffff" } },
  { id: "gl-draw-midpoint", type: "circle", filter: ["all", ["==", "meta", "midpoint"]], paint: { "circle-radius": 3.5, "circle-color": "#f3d27a" } },
];

export default function MapView(p: MapViewProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const draw = useRef<MapboxDraw | null>(null);
  const ready = useRef(false);
  const labels = useRef<maplibregl.Marker[]>([]);
  const waterMarker = useRef<maplibregl.Marker | null>(null);
  const cb = useRef(p);
  cb.current = p;

  // ---- init once ----------------------------------------------------------
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: {
        version: 8,
        sources: { imagery: { type: "raster", tiles: [IMAGERY], tileSize: 256, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" } },
        layers: [{ id: "imagery", type: "raster", source: "imagery" }],
      },
      center: [-105.03, 40.86],
      zoom: 12.5,
      attributionControl: false,
    });
    m.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "imperial" }), "bottom-left");

    const d = new MapboxDraw({ displayControlsDefault: false, controls: { polygon: true, trash: true }, styles: drawStyles });
    m.addControl(d as unknown as maplibregl.IControl, "top-right");
    draw.current = d;

    const emit = () => {
      const all = d.getAll();
      const polys = all.features.filter((f) => f.geometry.type === "Polygon");
      if (polys.length > 1) {
        // One pasture at a time: keep the newest.
        polys.slice(0, -1).forEach((f) => f.id && d.delete(String(f.id)));
      }
      const last = polys[polys.length - 1];
      cb.current.onPasture(last ? (last.geometry as GeoJSON.Polygon) : null);
    };
    const on = (m as unknown as { on: (t: string, f: () => void) => void }).on.bind(m);
    on("draw.create", emit);
    on("draw.update", emit);
    on("draw.delete", emit);
    m.on("click", (e: maplibregl.MapMouseEvent) => {
      if (cb.current.settingWater) cb.current.onWater([+e.lngLat.lng.toFixed(6), +e.lngLat.lat.toFixed(6)]);
    });

    m.on("load", () => {
      m.addSource("forage", { type: "image", url: BLANK, coordinates: [[0, 0], [0.001, 0], [0.001, -0.001], [0, -0.001]] });
      m.addLayer({ id: "forage", type: "raster", source: "forage", paint: { "raster-opacity": 0.78, "raster-resampling": "nearest" }, layout: { visibility: "none" } });
      m.addSource("strips", { type: "geojson", data: EMPTY });
      m.addSource("compare", { type: "geojson", data: EMPTY });
      m.addLayer({ id: "strips-fill", type: "fill", source: "strips", paint: { "fill-color": "#ffffff", "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.28, 0.0] } });
      m.addLayer({ id: "strips-line", type: "line", source: "strips", paint: { "line-color": "#ffffff", "line-width": 2.2 } });
      m.addLayer({ id: "strips-line-ink", type: "line", source: "strips", paint: { "line-color": "#1f2a22", "line-width": 0.8, "line-opacity": 0.9 } });
      m.addLayer({ id: "compare-line", type: "line", source: "compare", paint: { "line-color": "#e2643a", "line-width": 2.4, "line-dasharray": [1.5, 1.2] }, layout: { visibility: "none" } });
      m.on("mousemove", "strips-fill", (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
        const f = e.features?.[0];
        cb.current.onHover(f ? (f.properties?.order as number) : null);
      });
      m.on("mouseleave", "strips-fill", () => cb.current.onHover(null));
      ready.current = true;
      // Apply whatever props arrived before load.
      sync(m);
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- keep the map in step with props --------------------------------------
  const sync = (m: maplibregl.Map) => {
    const { result, mode, compare, showForage, pasture, water } = cb.current;
    const plan = result ? (mode === "forage" ? result.equal_forage : result.equal_area) : null;
    const other = result ? (mode === "forage" ? result.equal_area : result.equal_forage) : null;

    (m.getSource("strips") as maplibregl.GeoJSONSource | undefined)?.setData(plan ? toFC(plan.strips) : EMPTY);
    (m.getSource("compare") as maplibregl.GeoJSONSource | undefined)?.setData(other && compare ? toFC(other.strips) : EMPTY);
    m.setLayoutProperty("compare-line", "visibility", compare && other ? "visible" : "none");

    const forage = m.getSource("forage") as maplibregl.ImageSource | undefined;
    if (forage && result) {
      forage.updateImage({ url: `data:image/png;base64,${result.raster.png_base64}`, coordinates: result.raster.coordinates as [[number, number], [number, number], [number, number], [number, number]] });
    }
    m.setLayoutProperty("forage", "visibility", result && showForage ? "visible" : "none");

    labels.current.forEach((k) => k.remove());
    labels.current = [];
    if (plan) {
      for (const s of plan.strips) {
        const node = document.createElement("div");
        node.className = "strip-label";
        node.textContent = String(s.index);
        node.title = `${s.grazing_days.toFixed(1)} days, ${Math.round(s.forage_lb_ac)} lb/ac`;
        const [lng, lat] = centroidOf(s.geometry);
        labels.current.push(new maplibregl.Marker({ element: node }).setLngLat([lng, lat]).addTo(m));
      }
    }

    if (waterMarker.current) {
      waterMarker.current.remove();
      waterMarker.current = null;
    }
    if (water) {
      const node = document.createElement("div");
      node.className = "water-marker";
      node.title = "Water";
      waterMarker.current = new maplibregl.Marker({ element: node }).setLngLat(water).addTo(m);
    }

    // Draw layer mirrors the pasture prop (presets arrive from outside the draw tool).
    const d = draw.current;
    if (d) {
      const current = d.getAll().features.find((f) => f.geometry.type === "Polygon");
      const same = current && JSON.stringify(current.geometry) === JSON.stringify(pasture);
      if (!same) {
        d.deleteAll();
        if (pasture) d.add({ type: "Feature", geometry: pasture, properties: {} });
      }
    }
  };

  useEffect(() => {
    const m = map.current;
    if (m && ready.current) sync(m);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.result, p.mode, p.compare, p.showForage, p.pasture, p.water]);

  useEffect(() => {
    const m = map.current;
    if (!m || !p.pasture) return;
    const [w, s, e, n] = bbox(p.pasture);
    m.fitBounds([[w, s], [e, n]], { padding: 60, duration: 700, maxZoom: 16 });
  }, [p.focusToken, p.pasture]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready.current) return;
    const src = m.getSource("strips") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    const plan = p.result ? (p.mode === "forage" ? p.result.equal_forage : p.result.equal_area) : null;
    plan?.strips.forEach((s) => m.setFeatureState({ source: "strips", id: s.index }, { hover: s.index === p.hovered }));
  }, [p.hovered, p.result, p.mode]);

  useEffect(() => {
    const m = map.current;
    if (m) m.getCanvas().style.cursor = p.settingWater ? "crosshair" : "";
  }, [p.settingWater]);

  return <div ref={el} className="map" />;
}

// ---- helpers ---------------------------------------------------------------
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
const BLANK = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

function toFC(strips: PlanResponse["equal_forage"]["strips"]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: strips.map((s) => ({ type: "Feature", id: s.index, geometry: s.geometry, properties: { order: s.index, days: s.grazing_days } })),
  };
}

function ringCoords(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): number[][] {
  if (g.type === "Polygon") return g.coordinates[0];
  // Largest part of a multipolygon carries the label.
  let best = g.coordinates[0];
  let bestArea = -1;
  for (const poly of g.coordinates) {
    const a = Math.abs(shoelace(poly[0]));
    if (a > bestArea) {
      bestArea = a;
      best = poly;
    }
  }
  return best[0];
}

function shoelace(r: number[][]): number {
  let s = 0;
  for (let i = 0; i < r.length - 1; i++) s += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1];
  return s / 2;
}

function centroidOf(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): [number, number] {
  const r = ringCoords(g);
  const a = shoelace(r);
  if (Math.abs(a) < 1e-12) return [r[0][0], r[0][1]];
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < r.length - 1; i++) {
    const f = r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1];
    cx += (r[i][0] + r[i + 1][0]) * f;
    cy += (r[i][1] + r[i + 1][1]) * f;
  }
  return [cx / (6 * a), cy / (6 * a)];
}

function bbox(g: GeoJSON.Polygon): [number, number, number, number] {
  let w = 180;
  let s = 90;
  let e = -180;
  let n = -90;
  for (const [x, y] of g.coordinates[0]) {
    w = Math.min(w, x);
    e = Math.max(e, x);
    s = Math.min(s, y);
    n = Math.max(n, y);
  }
  return [w, s, e, n];
}
