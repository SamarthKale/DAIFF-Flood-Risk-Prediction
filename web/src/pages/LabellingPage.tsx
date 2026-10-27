import maplibregl from "maplibre-gl";
import { useCallback, useEffect, useRef, useState } from "react";

import { getAgreement, getLabelPoints, getMeta, postLabel, tileUrl } from "../api";
import { LabelForm } from "../components/LabelForm";
import type { Interpreter, LabelIn, SamplePoint } from "../types";

const IMAGERY: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    esri: {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [{ id: "esri", type: "raster", source: "esri" }],
};

export function LabellingPage() {
  const [who, setWho] = useState<Interpreter>("A");
  const [points, setPoints] = useState<SamplePoint[]>([]);
  const [i, setI] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [agree, setAgree] = useState<Awaited<ReturnType<typeof getAgreement>> | null>(null);
  const [years, setYears] = useState<number[]>([]);
  const [layer, setLayer] = useState<"esri" | number>("esri");
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const marker = useRef<maplibregl.Marker | null>(null);

  const load = useCallback(() => {
    getLabelPoints(who)
      .then((r) => {
        setPoints(r.points);
        setError(null);
        const first = r.points.findIndex((p) => !p.label);
        setI(first < 0 ? 0 : first);
      })
      .catch((e) => setError(e.message));
    getAgreement().then(setAgree).catch(() => setAgree(null));
  }, [who]);
  useEffect(load, [load]);

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({ container: el.current, style: IMAGERY, center: [92.5, 26], zoom: 15 });
    map.current = m;
    return () => m.remove();
  }, []);

  useEffect(() => {
    getMeta()
      .then((m) => setYears(m.layers.includes("preview") ? m.years : []))
      .catch(() => setYears([]));
  }, []);

  // Dated Sentinel-2 composites let the interpreter compare the t0 and latest seasons.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      if (m.getLayer("s2")) m.removeLayer("s2");
      if (m.getSource("s2")) m.removeSource("s2");
      if (layer === "esri") return;
      m.addSource("s2", { type: "raster", tiles: [tileUrl("preview", layer)], tileSize: 256 });
      m.addLayer({ id: "s2", type: "raster", source: "s2" });
    };
    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [layer]);

  const p = points[i];
  useEffect(() => {
    if (!p || !map.current) return;
    map.current.jumpTo({ center: [p.lon, p.lat], zoom: 16 });
    marker.current?.remove();
    marker.current = new maplibregl.Marker({ color: "#ffeb3b" }).setLngLat([p.lon, p.lat]).addTo(map.current);
  }, [p]);

  const save = async (body: LabelIn) => {
    await postLabel(body);
    const next = points.map((x, k) => (k === i ? { ...x, label: body } : x));
    setPoints(next);
    setI(Math.min(i + 1, points.length - 1));
    getAgreement().then(setAgree).catch(() => undefined);
  };

  const done = points.filter((x) => x.label).length;
  const visible = who === "ADJ" && agree ? new Set(agree.needs_adjudication) : null;
  return (
    <div className="map-layout">
      <aside className="sidebar">
        <label className="panel field">
          <span>Interpreter</span>
          <select value={who} onChange={(e) => setWho(e.target.value as Interpreter)}>
            <option value="A">Interpreter A</option>
            <option value="B">Interpreter B</option>
            <option value="ADJ">Adjudicator</option>
          </select>
        </label>
        {years.length > 0 && (
          <label className="panel field">
            <span>Imagery</span>
            <select
              aria-label="Imagery"
              value={String(layer)}
              onChange={(e) => setLayer(e.target.value === "esri" ? "esri" : Number(e.target.value))}
            >
              <option value="esri">Esri high-resolution (undated)</option>
              {years.map((y) => (
                <option key={y} value={y}>
                  Sentinel-2 dry season {y - 1}-{String(y).slice(2)}
                </option>
              ))}
            </select>
          </label>
        )}
        {error && <div className="panel muted">{error}</div>}
        {p && (
          <>
            <div className="panel">
              <div className="stat-label">
                Point {i + 1} / {points.length} · {done} labelled
              </div>
              <div className="stat">{p.point_id}</div>
              <div className="muted small">
                {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
              </div>
              {visible && !visible.has(p.point_id) && (
                <div className="muted small">A and B agree on this point — no adjudication needed.</div>
              )}
              <div className="nav-buttons">
                <button onClick={() => setI(Math.max(0, i - 1))}>◀ Prev</button>
                <button onClick={() => setI(Math.min(points.length - 1, i + 1))}>Next ▶</button>
              </div>
            </div>
            <LabelForm pointId={p.point_id} interpreter={who} initial={p.label} onSubmit={save} />
          </>
        )}
        {agree && (
          <div className="panel small">
            Points labelled by both A and B: {agree.n_both}
            <br />κ (latest year): {agree.kappa_t?.toFixed(3) ?? "—"} · κ (t0): {agree.kappa_t0?.toFixed(3) ?? "—"}
            <br />
            Waiting for adjudication: {agree.needs_adjudication.length}
          </div>
        )}
        <p className="muted small">
          Label from the imagery and the Sentinel-2 time series; do not look at the other interpreter's
          labels. Forest = tree canopy ≥ 30%.
        </p>
      </aside>
      <section className="map-wrap">
        <div ref={el} className="map" />
      </section>
    </div>
  );
}
