"use client";

import maplibregl, { type ExpressionSpecification, type GeoJSONSource, type Map as MLMap, type StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { LEVEL_FILL, LEVEL_PLAIN } from "@/lib/format";
import { useMode } from "@/lib/mode";

const DEFAULT_STYLE = process.env.NEXT_PUBLIC_MAP_STYLE ?? "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#efe6d2" } }],
};

const fillColor: ExpressionSpecification = [
  "match",
  ["coalesce", ["get", "level"], "INSUFFICIENT DATA"],
  "HIGH", LEVEL_FILL.HIGH,
  "MEDIUM", LEVEL_FILL.MEDIUM,
  "LOW", LEVEL_FILL.LOW,
  LEVEL_FILL["INSUFFICIENT DATA"],
];

interface Props {
  geo: GeoJSON.FeatureCollection | null;
  selectedAreaId: string | null;
  onSelect: (areaId: string, caseId: string | null) => void;
  /** Changing this re-fits the map to the data (e.g. switching layers). */
  fitKey?: string;
}

function bounds(fc: GeoJSON.FeatureCollection): [number, number, number, number] {
  let [x0, y0, x1, y1] = [180, 90, -180, -90];
  for (const f of fc.features) {
    const b = (f.properties as { bbox?: number[] } | null)?.bbox;
    if (b) {
      x0 = Math.min(x0, b[0]); y0 = Math.min(y0, b[1]); x1 = Math.max(x1, b[2]); y1 = Math.max(y1, b[3]);
    }
  }
  return [x0, y0, x1, y1];
}

export default function MapView({ geo, selectedAreaId, onSelect, fitKey }: Props) {
  const { mode } = useMode();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const [styleVersion, setStyleVersion] = useState(0); // bumps on every style load (incl. fallback)
  const ready = styleVersion > 0;
  const handlersBound = useRef(false);
  const fitted = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const selectedRef = useRef(selectedAreaId);
  selectedRef.current = selectedAreaId;

  // create map once
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: DEFAULT_STYLE,
      center: [-79.9959, 40.4406],
      zoom: 11,
      attributionControl: { compact: true },
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    let styleOk = false;
    const fallback = setTimeout(() => {
      if (!styleOk) m.setStyle(BLANK_STYLE); // basemap unreachable → plain background
    }, 6000);
    m.on("style.load", () => {
      styleOk = true;
      clearTimeout(fallback);
      setStyleVersion((v) => v + 1);
    });
    return () => {
      clearTimeout(fallback);
      m.remove();
      map.current = null;
    };
  }, []);

  // add / refresh data layers
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !geo) return;
    const src = m.getSource("areas") as GeoJSONSource | undefined;
    if (src) {
      src.setData(geo);
    } else {
      m.addSource("areas", { type: "geojson", data: geo, promoteId: "id" });
      m.addLayer({ id: "areas-fill", type: "fill", source: "areas", paint: { "fill-color": fillColor, "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, 0.82] } });
      m.addLayer({ id: "areas-line", type: "line", source: "areas", paint: { "line-color": "#faf5e8", "line-width": 1 } });
      m.addLayer({ id: "areas-selected", type: "line", source: "areas", filter: ["==", ["get", "id"], selectedRef.current ?? ""], paint: { "line-color": "#f25042", "line-width": 3.5 } });
    }
    if (fitted.current !== (fitKey ?? "default")) {
      m.fitBounds(bounds(geo), { padding: 24, duration: fitted.current ? 500 : 0 });
      fitted.current = fitKey ?? "default";
    }
    if (handlersBound.current) return;
    handlersBound.current = true;
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
    let hovered: string | number | undefined;
    m.on("mousemove", "areas-fill", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      m.getCanvas().style.cursor = "pointer";
      if (hovered !== undefined) m.setFeatureState({ source: "areas", id: hovered }, { hover: false });
      hovered = f.id;
      if (hovered !== undefined) m.setFeatureState({ source: "areas", id: hovered }, { hover: true });
      const p = f.properties as Record<string, string | null>;
      const div = document.createElement("div");
      div.className = "text-xs";
      const title = document.createElement("div");
      title.className = "font-semibold text-sm";
      title.textContent = p.name ?? "";
      const lvl = document.createElement("div");
      const lv = (p.level ?? "INSUFFICIENT DATA") as keyof typeof LEVEL_PLAIN;
      lvl.textContent = modeRef.current === "basic" ? (LEVEL_PLAIN[lv] ?? "") : `Unusualness: ${p.level ?? "unknown"}`;
      div.append(title, lvl);
      if (p.top_signal_headline) {
        const t = document.createElement("div");
        t.className = "mt-1 opacity-80";
        t.textContent = p.top_signal_headline;
        div.append(t);
      }
      popup.setLngLat(e.lngLat).setDOMContent(div).addTo(m);
    });
    m.on("mouseleave", "areas-fill", () => {
      m.getCanvas().style.cursor = "";
      if (hovered !== undefined) m.setFeatureState({ source: "areas", id: hovered }, { hover: false });
      hovered = undefined;
      popup.remove();
    });
    m.on("click", "areas-fill", (e) => {
      const p = e.features?.[0]?.properties as Record<string, string | null> | undefined;
      if (p?.id) onSelectRef.current(p.id, p.case_id ?? null);
    });
  }, [styleVersion, ready, geo, fitKey]);

  // selection outline + zoom
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getLayer("areas-selected")) return;
    m.setFilter("areas-selected", ["==", ["get", "id"], selectedAreaId ?? ""]);
    const f = geo?.features.find((x) => (x.properties as { id?: string } | null)?.id === selectedAreaId);
    const b = (f?.properties as { bbox?: number[] } | undefined)?.bbox;
    if (b) m.fitBounds([b[0], b[1], b[2], b[3]], { padding: 120, maxZoom: 14, duration: 600 });
  }, [selectedAreaId, styleVersion, ready, geo]);

  return (
    <div className="relative h-full w-full">
      <div ref={el} className="h-full w-full" style={{ filter: "sepia(0.15)" }} />
      <div className="dossier pointer-events-none absolute bottom-3 left-3 rounded-sm p-3 text-xs">
        <p className="case-stamp mb-1.5 text-[10px] uppercase text-oxblood">
          {mode === "basic" ? "How unusual is each area?" : "Unusual activity vs. citywide pattern"}
        </p>
        {(["HIGH", "MEDIUM", "LOW", "INSUFFICIENT DATA"] as const).map((l) => (
          <div key={l} className="flex items-center gap-2 py-0.5">
            <span className="inline-block h-3 w-4 rounded-md border-2 border-stroke" style={{ background: LEVEL_FILL[l] }} />
            <span>{mode === "basic" ? LEVEL_PLAIN[l] : l.charAt(0) + l.slice(1).toLowerCase()}</span>
          </div>
        ))}
        <p className="mt-1.5 max-w-[190px] text-[10px] text-ink-muted">Darker means more different from the rest of the city — not better or worse.</p>
      </div>
    </div>
  );
}
