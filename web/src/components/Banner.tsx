import type { Metrics } from "../types";

const FOREST_LAYERS = new Set(["forest", "loss", "preview"]);

/** NFR-8: every map view says the outputs are experimental and shows the displayed model's skill. */
export function Banner({ layer, metrics }: { layer: string; metrics: Metrics }) {
  let skill = "accuracy not yet validated";
  if (FOREST_LAYERS.has(layer) && metrics.forest_oa != null) {
    skill = `Forest OA ${(metrics.forest_oa * 100).toFixed(1)}% (reference sample)`;
  } else if (!FOREST_LAYERS.has(layer) && metrics.flood_auc != null) {
    skill = `Model AUC ${metrics.flood_auc.toFixed(2)} (held-out events)`;
  }
  return (
    <div className="banner" role="note">
      <strong>Experimental decision support — not an official flood warning.</strong>{" "}
      <span>{skill}</span>
    </div>
  );
}
