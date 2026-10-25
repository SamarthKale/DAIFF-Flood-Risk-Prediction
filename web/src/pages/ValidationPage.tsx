import { useEffect, useState } from "react";

import { getMetrics } from "../api";

type AnyRec = Record<string, unknown>;
const fmt = (v: unknown, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");

function Card({ title, value, note }: { title: string; value: string; note?: string }) {
  return (
    <div className="card">
      <div className="stat-label">{title}</div>
      <div className="stat">{value}</div>
      {note && <div className="muted small">{note}</div>}
    </div>
  );
}

export function ValidationPage() {
  const [m, setM] = useState<Record<string, AnyRec> | null>(null);
  useEffect(() => {
    getMetrics().then(setM).catch(() => setM({}));
  }, []);
  if (!m) return <div className="page">Loading…</div>;
  const flood = (m.flood ?? m.flood_train ?? {}) as AnyRec;
  const forest = (m.forest ?? {}) as AnyRec;
  const abl = (flood.ablation ?? {}) as AnyRec;
  const cv = (flood.block_cv ?? {}) as AnyRec;
  const imp = (flood.permutation_importance ?? []) as AnyRec[];
  const f1 = (forest.fr_f1 ?? {}) as AnyRec;
  const f2 = (forest.fr_f2 ?? {}) as AnyRec;
  return (
    <div className="page">
      <h2>Flood susceptibility (SRS 7.4)</h2>
      <div className="cards">
        <Card title="AUC, held-out events (FR-R2)" value={fmt(flood.auc)} note="target ≥ 0.80" />
        <Card title="HAND < 5 m baseline AUC" value={fmt(flood.hand_baseline_auc_binary)} note="model must beat by ≥ 0.05" />
        <Card title="Flooded test cells in high/very high" value={fmt(flood.share_flooded_in_high, 2)} note="target ≥ 0.60" />
        <Card title="Area in high/very high" value={fmt(flood.high_class_area_share, 2)} note="target ≤ 0.30" />
        <Card
          title="Coupling ablation ΔAUC (FR-R3)"
          value={fmt(abl.delta)}
          note={Array.isArray(abl.ci95) ? `95% CI [${fmt(abl.ci95[0])}, ${fmt(abl.ci95[1])}]` : "run daiff validate"}
        />
        <Card title="Spatial block CV AUC" value={fmt(cv.auc_mean)} note={cv.auc_std != null ? `± ${fmt(cv.auc_std)}` : undefined} />
      </div>
      {imp.length > 0 && (
        <>
          <h3>Permutation importance (test events)</h3>
          <table className="table narrow">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Mean drop in AUC</th>
              </tr>
            </thead>
            <tbody>
              {imp.map((r) => (
                <tr key={String(r.feature)}>
                  <td>{String(r.feature)}</td>
                  <td>{fmt(r.importance_mean, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <h2>Forest change (SRS 7.3)</h2>
      {Object.keys(forest).length === 0 ? (
        <p className="muted">
          Not validated yet: label the reference sample on the Labelling page, then run{" "}
          <code>daiff validate --what forest</code>.
        </p>
      ) : (
        <div className="cards">
          <Card title="Overall accuracy (FR-F1)" value={fmt(f1.overall_accuracy)} note="target ≥ 0.90" />
          <Card title="Forest F1 (FR-F1)" value={fmt(f1.forest_f1)} note="target ≥ 0.85" />
          <Card title="Loss F1 (FR-F2)" value={fmt(f2.loss_f1)} note="target ≥ 0.70" />
          <Card title="Interpreter agreement κ" value={fmt(forest.kappa_t)} />
        </div>
      )}
    </div>
  );
}
