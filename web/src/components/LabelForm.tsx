import { useEffect, useState } from "react";

import type { Interpreter, LabelIn, LabelValue } from "../types";

const OPTIONS: { value: LabelValue; name: string }[] = [
  { value: "forest", name: "Forest" },
  { value: "non_forest", name: "Non-forest" },
  { value: "unsure", name: "Unsure" },
];

export function LabelForm({
  pointId,
  interpreter,
  initial,
  onSubmit,
}: {
  pointId: string;
  interpreter: Interpreter;
  initial: { label_t0: LabelValue; label_t: LabelValue; note: string } | null;
  onSubmit: (body: LabelIn) => void;
}) {
  const [t0, setT0] = useState<LabelValue | null>(initial?.label_t0 ?? null);
  const [t, setT] = useState<LabelValue | null>(initial?.label_t ?? null);
  const [note, setNote] = useState(initial?.note ?? "");
  useEffect(() => {
    setT0(initial?.label_t0 ?? null);
    setT(initial?.label_t ?? null);
    setNote(initial?.note ?? "");
  }, [pointId, initial]);

  const group = (label: string, value: LabelValue | null, set: (v: LabelValue) => void) => (
    <fieldset className="label-group">
      <legend>{label}</legend>
      {OPTIONS.map((o) => (
        <label key={o.value} className="radio">
          <input
            type="radio"
            name={`${label}-${pointId}`}
            aria-label={`${label}: ${o.name}`}
            checked={value === o.value}
            onChange={() => set(o.value)}
          />
          {o.name}
        </label>
      ))}
    </fieldset>
  );

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        if (t0 && t) onSubmit({ point_id: pointId, interpreter, label_t0: t0, label_t: t, note });
      }}
    >
      {group("t0", t0, setT0)}
      {group("latest", t, setT)}
      <input
        className="search"
        placeholder="Note (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <button type="submit" className="primary" disabled={!t0 || !t}>
        Save and next
      </button>
    </form>
  );
}
