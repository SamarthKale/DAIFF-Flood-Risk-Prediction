import type { LayerName } from "../types";

export const LAYER_LABELS: Record<LayerName, string> = {
  preview: "Sentinel-2 composite",
  forest: "Forest fraction",
  loss: "Forest loss since baseline",
  susceptibility: "Flood susceptibility",
  riskclass: "Flood risk class",
  delta_s: "Change in susceptibility (ΔS)",
};

export function LayerSwitcher({
  layers,
  value,
  onChange,
}: {
  layers: LayerName[];
  value: LayerName;
  onChange: (l: LayerName) => void;
}) {
  return (
    <fieldset className="panel">
      <legend>Map layer</legend>
      {layers.map((l) => (
        <label key={l} className="radio">
          <input
            type="radio"
            name="layer"
            value={l}
            checked={value === l}
            onChange={() => onChange(l)}
          />
          {LAYER_LABELS[l]}
        </label>
      ))}
    </fieldset>
  );
}

export function YearSelector({
  years,
  value,
  onChange,
}: {
  years: number[];
  value: number;
  onChange: (y: number) => void;
}) {
  return (
    <label className="panel field">
      <span>Year</span>
      <select value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {years.map((y) => (
          <option key={y} value={y}>
            {y} (dry season {y - 1}–{String(y).slice(2)})
          </option>
        ))}
      </select>
    </label>
  );
}
