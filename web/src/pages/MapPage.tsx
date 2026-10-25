import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";

import { ApiError, exportUrl, getPoint, getSubbasins, tileUrl } from "../api";
import { Banner } from "../components/Banner";
import { LayerSwitcher, YearSelector } from "../components/LayerSwitcher";
import { Legend } from "../components/Legend";
import { PointPanel } from "../components/PointPanel";
import type { LayerName, Meta, PointInfo } from "../types";

const BASEMAP: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.6 } }],
};

function bbox(fc: GeoJSON.FeatureCollection): [number, number, number, number] {
  let [x0, y0, x1, y1] = [180, 90, -180, -90];
  const visit = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === "number") {
      const [x, y] = c as number[];
      x0 = Math.min(x0, x);
      y0 = Math.min(y0, y);
      x1 = Math.max(x1, x);
      y1 = Math.max(y1, y);
    } else if (Array.isArray(c)) c.forEach(visit);
  };
  fc.features.forEach((f) => visit((f.geometry as GeoJSON.Polygon).coordinates));
  return [x0, y0, x1, y1];
}

export function MapPage({ meta, focus }: { meta: Meta; focus?: number | null }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [layer, setLayer] = useState<LayerName>("susceptibility");
  const [year, setYear] = useState(meta.years[meta.years.length - 1]);
  const [opacity, setOpacity] = useState(0.8);
  const [point, setPoint] = useState<PointInfo | null>(null);
  const [pointError, setPointError] = useState<string | null>(null);
  const [subbasins, setSubbasins] = useState<GeoJSON.FeatureCollection | null>(null);
  const yearRef = useRef(year);
  yearRef.current = year;

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({ container: el.current, style: BASEMAP, center: [92.5, 26.0], zoom: 8 });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl(), "bottom-left");
    m.on("load", () => setReady(true));
    m.on("click", async (e) => {
      setPointError(null);
      try {
        setPoint(await getPoint(e.lngLat.lng, e.lngLat.lat, yearRef.current));
      } catch (err) {
        setPoint(null);
        setPointError(err instanceof ApiError ? err.message : "No data here");
      }
    });
    map.current = m;
    return () => m.remove();
  }, []);

  useEffect(() => {
    getSubbasins(year).then(setSubbasins).catch(() => setSubbasins(null));
  }, [year]);

  // data raster layer
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (m.getLayer("data")) m.removeLayer("data");
    if (m.getSource("data")) m.removeSource("data");
    m.addSource("data", { type: "raster", tiles: [tileUrl(layer, year)], tileSize: 256 });
    m.addLayer(
      { id: "data", type: "raster", source: "data", paint: { "raster-opacity": opacity } },
      m.getLayer("subbasins-line") ? "subbasins-line" : undefined,
    );
  }, [layer, year, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const m = map.current;
    if (m && ready && m.getLayer("data")) m.setPaintProperty("data", "raster-opacity", opacity);
  }, [opacity, ready]);

  // sub-basin outlines (flagged in red)
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !subbasins) return;
    const src = m.getSource("subbasins") as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(subbasins);
    else {
      m.addSource("subbasins", { type: "geojson", data: subbasins });
      m.addLayer({
        id: "subbasins-line",
        type: "line",
        source: "subbasins",
        paint: {
          "line-color": ["case", ["==", ["get", "risk_flag"], "yes"], "#c62828", "#37474f"],
          "line-width": ["case", ["==", ["get", "risk_flag"], "yes"], 2.5, 1],
        },
      });
      m.fitBounds(bbox(subbasins), { padding: 30, duration: 0 });
    }
  }, [subbasins, ready]);

  // zoom to a sub-basin chosen on the Sub-basins page
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !subbasins || focus == null) return;
    const f = subbasins.features.find((x) => x.properties?.subbasin_id === focus);
    if (f) m.fitBounds(bbox({ type: "FeatureCollection", features: [f] }), { padding: 40 });
  }, [focus, subbasins, ready]);

  return (
    <div className="map-layout">
      <aside className="sidebar">
        <LayerSwitcher layers={meta.layers} value={layer} onChange={setLayer} />
        <YearSelector years={meta.years} value={year} onChange={setYear} />
        <label className="panel field">
          <span>Opacity {Math.round(opacity * 100)}%</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
          />
        </label>
        <Legend legend={meta.legends[layer]} />
        <a className="panel link" href={exportUrl(layer, year)}>
          Download this layer (GeoTIFF)
        </a>
        <PointPanel point={point} error={pointError} />
      </aside>
      <section className="map-wrap">
        <Banner layer={layer} metrics={meta.metrics} />
        <div ref={el} className="map" />
      </section>
    </div>
  );
}
