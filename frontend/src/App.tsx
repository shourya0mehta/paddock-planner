import { useEffect, useMemo, useState } from "react";
import MapView from "./MapView";
import { fetchPresets, planToGeoJSON, postPlan } from "./api";
import type { PlanRequest, PlanResponse, Preset, Species, StripOut } from "./api";

type Mode = "forage" | "area";

const today = () => new Date().toISOString().slice(0, 10);

export default function App() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [pasture, setPasture] = useState<GeoJSON.Polygon | null>(null);
  const [water, setWater] = useState<[number, number] | null>(null);
  const [settingWater, setSettingWater] = useState(false);
  const [species, setSpecies] = useState<Species>("cattle");
  const [head, setHead] = useState(80);
  const [weight, setWeight] = useState<number | "">(1200);
  const [utilization, setUtilization] = useState(0.5);
  const [nStrips, setNStrips] = useState<number | "">("");
  const [targetDays, setTargetDays] = useState(5);
  const [startDate, setStartDate] = useState(today());
  const [source, setSource] = useState<"rap" | "synthetic">("synthetic");
  const [growth, setGrowth] = useState<number | "">("");
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [mode, setMode] = useState<Mode>("forage");
  const [compare, setCompare] = useState(false);
  const [showForage, setShowForage] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focusToken, setFocusToken] = useState(0);
  const [hovered, setHovered] = useState<number | null>(null);
  const [showNotes, setShowNotes] = useState(false);

  useEffect(() => {
    fetchPresets()
      .then((ps) => {
        setPresets(ps);
        if (ps[0]) loadPreset(ps[0]);
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadPreset(p: Preset) {
    setPasture(p.pasture);
    setWater(p.water);
    setSpecies(p.herd.species);
    setHead(p.herd.head);
    setWeight(p.herd.avg_weight_lb);
    setSource(p.source);
    setResult(null);
    setError(null);
    setFocusToken((t) => t + 1);
  }

  async function run() {
    if (!pasture) {
      setError("Draw a pasture first (polygon tool, top right of the map).");
      return;
    }
    setBusy(true);
    setError(null);
    const req: PlanRequest = {
      pasture,
      water,
      herd: { species, head, avg_weight_lb: weight === "" ? null : weight },
      utilization,
      n_strips: nStrips === "" ? null : nStrips,
      target_days_per_strip: targetDays,
      start_date: startDate || null,
      source,
      growth_lb_ac_day: growth === "" ? null : growth,
    };
    try {
      const r = await postPlan(req);
      setResult(r);
      setFocusToken((t) => t + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function download() {
    if (!result || !pasture) return;
    const fc = planToGeoJSON(result, pasture, water, mode);
    const blob = new Blob([JSON.stringify(fc, null, 2)], { type: "application/geo+json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `paddocks-${mode}-${startDate}.geojson`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const plan = result ? (mode === "forage" ? result.equal_forage : result.equal_area) : null;
  const other = result ? (mode === "forage" ? result.equal_area : result.equal_forage) : null;
  const isSynthetic = result?.source.source === "synthetic";

  const spread = useMemo(() => {
    if (!result) return null;
    const ef = result.equal_forage;
    const ea = result.equal_area;
    return { ef: `${ef.days_min.toFixed(0)}–${ef.days_max.toFixed(0)}`, ea: `${ea.days_min.toFixed(0)}–${ea.days_max.toFixed(0)}` };
  }, [result]);

  return (
    <div className="app">
      <aside className="panel">
        <header className="brand">
          <h1>Paddock Planner</h1>
          <p className="thesis">
            Satellites say what grew. Collars say what was eaten. The difference is what's left, and the fence should follow it.
          </p>
        </header>

        <section>
          <h2>Pasture</h2>
          <div className="presets">
            {presets.map((p) => (
              <button key={p.id} className="chip" onClick={() => loadPreset(p)} title={p.blurb}>
                {p.name}
              </button>
            ))}
          </div>
          <p className="hint">
            Or draw your own with the polygon tool on the map. Up to 500 vertices and 10,000 acres, same as the Nofence app.
          </p>
          <div className="row">
            <button className={settingWater ? "btn active" : "btn"} onClick={() => setSettingWater((v) => !v)}>
              {settingWater ? "Click the map to place water…" : water ? "Move water point" : "Set water point"}
            </button>
            {water && (
              <button className="btn ghost" onClick={() => setWater(null)}>
                Clear
              </button>
            )}
          </div>
        </section>

        <section>
          <h2>Herd</h2>
          <div className="grid3">
            <label>
              Species
              <select value={species} onChange={(e) => setSpecies(e.target.value as Species)}>
                <option value="cattle">Cattle</option>
                <option value="sheep">Sheep</option>
                <option value="goats">Goats</option>
              </select>
            </label>
            <label>
              Head
              <input type="number" min={1} value={head} onChange={(e) => setHead(+e.target.value)} />
            </label>
            <label>
              Avg lb
              <input type="number" min={1} value={weight} placeholder="default" onChange={(e) => setWeight(e.target.value === "" ? "" : +e.target.value)} />
            </label>
          </div>
        </section>

        <section>
          <h2>Plan</h2>
          <label className="slider">
            <span>
              Utilization <b>{Math.round(utilization * 100)}%</b> <small>take {Math.round(utilization * 100)}, leave {100 - Math.round(utilization * 100)}</small>
            </span>
            <input type="range" min={0.25} max={0.75} step={0.05} value={utilization} onChange={(e) => setUtilization(+e.target.value)} />
          </label>
          <div className="grid3">
            <label>
              Strips
              <input type="number" min={1} max={30} value={nStrips} placeholder="auto" onChange={(e) => setNStrips(e.target.value === "" ? "" : +e.target.value)} />
            </label>
            <label>
              Target days/strip
              <input type="number" min={1} max={60} value={targetDays} onChange={(e) => setTargetDays(+e.target.value)} />
            </label>
            <label>
              Start
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>
          </div>
          <div className="grid2">
            <label>
              Forage data
              <select value={source} onChange={(e) => setSource(e.target.value as "rap" | "synthetic")}>
                <option value="rap">RAP satellite (US only)</option>
                <option value="synthetic">Synthetic demo surface</option>
              </select>
            </label>
            <label>
              Growth lb/ac/day <small>optional</small>
              <input type="number" min={0} step={1} value={growth} placeholder="from 16-day RAP" onChange={(e) => setGrowth(e.target.value === "" ? "" : +e.target.value)} />
            </label>
          </div>
          <button className="btn primary" onClick={run} disabled={busy}>
            {busy ? "Reading satellite data…" : "Plan the rotation"}
          </button>
          {error && <p className="error">{error}</p>}
        </section>

        {result && plan && other && spread && (
          <section className="results">
            {isSynthetic && <div className="banner">Synthetic surface. Numbers are for exercising the tool, not for a rancher.</div>}
            {result.warnings.map((w) => (
              <div className="banner warn" key={w}>
                {w}
              </div>
            ))}
            <div className="stats">
              <Stat label="Acres" value={fmt(result.pasture.area_ac)} />
              <Stat label="lb/acre" value={fmt(result.pasture.forage_lb_ac_mean)} />
              <Stat label="Grazing days" value={fmt(result.pasture.grazing_days_total)} sub={`${result.herd.head} ${result.herd.species}, ${fmt(result.herd.animal_units)} AU`} />
            </div>
            <p className="source">{result.source.label}</p>

            <div className="modes">
              <button className={mode === "forage" ? "seg on" : "seg"} onClick={() => setMode("forage")}>
                Equal forage <small>{spread.ef} days</small>
              </button>
              <button className={mode === "area" ? "seg on" : "seg"} onClick={() => setMode("area")}>
                Equal area <small>{spread.ea} days</small>
              </button>
            </div>
            <div className="toggles">
              <label>
                <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} /> Overlay the other cut
              </label>
              <label>
                <input type="checkbox" checked={showForage} onChange={(e) => setShowForage(e.target.checked)} /> Forage layer
              </label>
            </div>
            <p className="legend">
              <span className="swatch" /> {result.raster.legend.min_lb_ac}–{result.raster.legend.max_lb_ac} {result.raster.legend.units}
            </p>

            <table className="strips">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Acres</th>
                  <th>lb/ac</th>
                  <th>Days</th>
                  <th>Dates</th>
                  <th>Trust</th>
                </tr>
              </thead>
              <tbody>
                {plan.strips.map((s) => (
                  <StripRow key={s.index} s={s} hovered={hovered === s.index} onHover={setHovered} />
                ))}
              </tbody>
            </table>

            <p className={result.rotation_check.ok ? "check ok" : "check"}>{result.rotation_check.message}</p>

            <div className="row">
              <button className="btn" onClick={download}>
                Download GeoJSON
              </button>
              <button className="btn ghost" onClick={() => setShowNotes((v) => !v)}>
                {showNotes ? "Hide" : "What this can't see"}
              </button>
            </div>
            {showNotes && (
              <ul className="notes">
                {result.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
                <li>
                  Intake is {((result.assumptions.intake_fraction_of_bw as number) * 100).toFixed(1)}% of body weight per day, the NRCS planning number. Real intake moves with forage quality and weather.
                </li>
              </ul>
            )}
          </section>
        )}
      </aside>

      <MapView
        pasture={pasture}
        water={water}
        result={result}
        mode={mode}
        compare={compare}
        showForage={showForage}
        settingWater={settingWater}
        focusToken={focusToken}
        hovered={hovered}
        onPasture={(g) => {
          setPasture(g);
          setResult(null);
        }}
        onWater={(w) => {
          setWater(w);
          setSettingWater(false);
        }}
        onHover={setHovered}
      />
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="v">{value}</div>
      <div className="l">{label}</div>
      {sub && <div className="s">{sub}</div>}
    </div>
  );
}

function StripRow({ s, hovered, onHover }: { s: StripOut; hovered: boolean; onHover: (i: number | null) => void }) {
  return (
    <tr className={hovered ? "hov" : ""} onMouseEnter={() => onHover(s.index)} onMouseLeave={() => onHover(null)} title={s.confidence_reasons.join("\n")}>
      <td className="n">{s.index}</td>
      <td>{s.area_ac.toFixed(1)}</td>
      <td>{fmt(s.forage_lb_ac)}</td>
      <td className="days">{s.grazing_days.toFixed(1)}</td>
      <td className="dates">
        {md(s.start)} – {md(s.end)}
      </td>
      <td>
        <span className={`trust ${s.confidence}`}>{s.confidence}</span>
      </td>
    </tr>
  );
}

const fmt = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 0 });
const md = (iso: string) => {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};
