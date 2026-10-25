import type { LabelIn, LayerName, Meta, PointInfo, SamplePoint } from "./types";

const BASE: string = import.meta.env.VITE_API_BASE ?? "";

export const tileUrl = (layer: LayerName | string, year: number) =>
  `${BASE}/api/tiles/${layer}/${year}/{z}/{x}/{y}.png`;
export const csvUrl = (year: number) => `${BASE}/api/subbasins/${year}.csv`;
export const exportUrl = (layer: LayerName | string, year: number) =>
  `${BASE}/api/export/${layer}/${year}.tif`;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const getMeta = () => getJSON<Meta>("/api/meta");
export const getPoint = (lon: number, lat: number, year: number) =>
  getJSON<PointInfo>(`/api/point?lon=${lon}&lat=${lat}&year=${year}`);
export const getSubbasins = (year: number) =>
  getJSON<GeoJSON.FeatureCollection>(`/api/subbasins?year=${year}`);
export const getMetrics = () => getJSON<Record<string, Record<string, unknown>>>("/api/metrics");
export const getLabelPoints = (interpreter: string) =>
  getJSON<{ points: SamplePoint[]; done: number }>(`/api/labelling/points?interpreter=${interpreter}`);
export const postLabel = (body: LabelIn) =>
  getJSON<{ ok: boolean }>("/api/labelling/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const getAgreement = () =>
  getJSON<{ n_both: number; kappa_t: number | null; kappa_t0: number | null; needs_adjudication: string[] }>(
    "/api/labelling/agreement",
  );
