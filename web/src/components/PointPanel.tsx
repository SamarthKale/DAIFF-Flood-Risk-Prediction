import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { PointInfo } from "../types";

export const RISK_NAMES = ["", "Very low", "Low", "Moderate", "High", "Very high"];

const FEATURE_LABELS: Record<string, string> = {
  elevation: "Elevation",
  slope: "Slope",
  twi: "Wetness index (TWI)",
  hand: "Height above drainage (HAND)",
  dist_river: "Distance to river",
  hsg: "Soil group",
  rain_mean_annual: "Mean annual rainfall",
  rain_p10y_1d: "10-year design rainfall",
  f: "Forest fraction (C1)",
  dF: "Local forest loss (C1)",
  U: "Upstream forest loss (C2)",
  CN: "Curve number (C3)",
  Q: "Runoff depth (C3)",
};

/** FR-V3: forest fraction over time, susceptibility and the three most influential features. */
export function PointPanel({ point, error }: { point: PointInfo | null; error: string | null }) {
  if (error) return <div className="panel muted">{error}</div>;
  if (!point) return <div className="panel muted">Click the map to inspect a location.</div>;
  const ds = point.delta_s;
  return (
    <div className="panel point">
      <div className="stat-row">
        <div>
          <div className="stat-label">Susceptibility {point.year}</div>
          <div className="stat">{point.susceptibility.toFixed(2)}</div>
        </div>
        <div>
          <div className="stat-label">Risk class</div>
          <div className={`stat risk-${point.risk_class}`}>{RISK_NAMES[point.risk_class] ?? "—"}</div>
        </div>
        <div>
          <div className="stat-label">ΔS vs baseline</div>
          <div className="stat">{ds == null ? "—" : `${ds >= 0 ? "+" : ""}${ds.toFixed(3)}`}</div>
        </div>
      </div>
      <div className="stat-label">Forest fraction over time</div>
      <div style={{ height: 120 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={point.forest_fraction}>
            <XAxis dataKey="year" fontSize={11} />
            <YAxis domain={[0, 1]} fontSize={11} width={28} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#2e7d32" dot />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="stat-label">Most influential features here</div>
      <ol className="features">
        {point.top_features.map((f) => (
          <li key={f.name}>
            {FEATURE_LABELS[f.name] ?? f.name}{" "}
            <span className={f.contribution >= 0 ? "up" : "down"}>
              {f.contribution >= 0 ? "raises" : "lowers"} risk
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
