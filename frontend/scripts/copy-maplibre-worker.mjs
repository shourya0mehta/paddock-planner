// MapLibre 6 loads its worker relative to its own module URL, which the bundler
// does not preserve. Serve the worker (and the shared chunk it imports) as
// static files and point MapLibre at them (see MapView.tsx).
import { cpSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "node_modules", "maplibre-gl", "dist");
const dst = join(here, "..", "public", "maplibre");
mkdirSync(dst, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) cpSync(join(src, f), join(dst, f));
console.log("copied maplibre worker to public/maplibre/");
