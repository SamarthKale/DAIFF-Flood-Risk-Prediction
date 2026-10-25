import { useEffect, useState } from "react";

import { csvUrl, getSubbasins } from "../api";
import { YearSelector } from "../components/LayerSwitcher";
import { SubbasinTable } from "../components/SubbasinTable";
import type { Meta, SubbasinRow } from "../types";

export function SubbasinsPage({ meta, onSelect }: { meta: Meta; onSelect: (id: number) => void }) {
  const [year, setYear] = useState(meta.years[meta.years.length - 1]);
  const [rows, setRows] = useState<SubbasinRow[]>([]);
  useEffect(() => {
    getSubbasins(year).then((fc) =>
      setRows(fc.features.map((f) => f.properties as SubbasinRow)),
    );
  }, [year]);
  const flagged = rows.filter((r) => r.risk_flag === "yes").length;
  return (
    <div className="page">
      <div className="toolbar">
        <YearSelector years={meta.years} value={year} onChange={setYear} />
        <a className="button" href={csvUrl(year)}>
          Download table (CSV)
        </a>
        <span className="muted">
          {rows.length} sub-basins · {flagged} flagged high / very high risk (FR-A1)
        </span>
      </div>
      <SubbasinTable rows={rows} onSelect={(r) => onSelect(r.subbasin_id)} />
      <p className="muted small">
        Forest loss is measured since the baseline year {meta.t0}. Click a row to view it on the map.
      </p>
    </div>
  );
}
