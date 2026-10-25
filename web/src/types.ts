export type LayerName = "preview" | "forest" | "loss" | "susceptibility" | "riskclass" | "delta_s";

export interface Metrics {
  flood_auc: number | null;
  forest_oa: number | null;
}

export interface Legend {
  type: "continuous" | "categorical" | "rgb";
  label: string;
  min?: number;
  max?: number;
  cmap?: string;
  classes?: { value: number; color: string; name: string }[];
}

export interface Meta {
  run_id: string;
  project: string;
  basin: string;
  years: number[];
  t0: number;
  layers: LayerName[];
  legends: Record<string, Legend>;
  metrics: Metrics;
}

export interface PointInfo {
  row: number;
  col: number;
  year: number;
  forest_fraction: { year: number; value: number | null }[];
  susceptibility: number;
  risk_class: number;
  delta_s: number | null;
  top_features: { name: string; contribution: number; value: number }[];
}

export interface SubbasinRow {
  subbasin_id: number;
  name: string;
  area_km2: number;
  forest_loss_ha: number;
  forest_fraction: number | null;
  mean_s: number | null;
  mean_delta_s: number | null;
  area_class_1: number;
  area_class_2: number;
  area_class_3: number;
  area_class_4: number;
  area_class_5: number;
  area_moved_up_km2: number;
  risk_class: number;
  risk_flag: "yes" | "no";
}

export type LabelValue = "forest" | "non_forest" | "unsure";
export type Interpreter = "A" | "B" | "ADJ";

export interface LabelIn {
  point_id: string;
  interpreter: Interpreter;
  label_t0: LabelValue;
  label_t: LabelValue;
  note: string;
}

export interface SamplePoint {
  point_id: string;
  lon: number;
  lat: number;
  stratum: number;
  label: { label_t0: LabelValue; label_t: LabelValue; note: string } | null;
}
