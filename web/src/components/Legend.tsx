import type { Legend as LegendT } from "../types";

const GRADIENTS: Record<string, string> = {
  greens: "linear-gradient(90deg,#f7fcf5,#74c476,#00441b)",
  reds: "linear-gradient(90deg,#fff5f0,#fb6a4a,#67000d)",
  viridis: "linear-gradient(90deg,#440154,#3b528b,#21918c,#5ec962,#fde725)",
  rdbu_r: "linear-gradient(90deg,#2166ac,#f7f7f7,#b2182b)",
};

export function Legend({ legend }: { legend: LegendT | undefined }) {
  if (!legend) return null;
  return (
    <div className="panel legend">
      <div className="legend-title">{legend.label}</div>
      {legend.type === "continuous" && (
        <>
          <div className="ramp" style={{ background: GRADIENTS[legend.cmap ?? "viridis"] }} />
          <div className="ramp-labels">
            <span>{legend.min}</span>
            <span>{legend.max}</span>
          </div>
        </>
      )}
      {legend.type === "categorical" &&
        legend.classes?.map((c) => (
          <div key={c.value} className="swatch-row">
            <span className="swatch" style={{ background: c.color }} />
            {c.name}
          </div>
        ))}
    </div>
  );
}
