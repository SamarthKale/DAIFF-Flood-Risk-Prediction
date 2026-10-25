import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";

import type { SubbasinRow } from "../types";
import { RISK_NAMES } from "./PointPanel";

const col = createColumnHelper<SubbasinRow>();
const num = (d: number) => (v: number | null) => (v == null ? "—" : v.toFixed(d));

const columns = [
  col.accessor("name", {
    header: "Sub-basin",
    cell: (c) => <span data-testid="name-cell">{c.getValue()}</span>,
  }),
  col.accessor("forest_loss_ha", { header: "Forest loss (ha)", cell: (c) => num(1)(c.getValue()) }),
  col.accessor("forest_fraction", { header: "Forest fraction", cell: (c) => num(2)(c.getValue()) }),
  col.accessor("mean_s", { header: "Mean susceptibility", cell: (c) => num(2)(c.getValue()) }),
  col.accessor("mean_delta_s", { header: "Mean ΔS", cell: (c) => num(3)(c.getValue()) }),
  col.accessor("risk_class", {
    header: "Risk class",
    cell: (c) => <span className={`pill risk-${c.getValue()}`}>{RISK_NAMES[c.getValue()] ?? "—"}</span>,
  }),
  col.accessor("area_moved_up_km2", { header: "Area moved up (km²)", cell: (c) => num(2)(c.getValue()) }),
  col.accessor("area_km2", { header: "Area (km²)", cell: (c) => num(1)(c.getValue()) }),
];

export function SubbasinTable({
  rows,
  onSelect,
}: {
  rows: SubbasinRow[];
  onSelect: (row: SubbasinRow) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filter, setFilter] = useState("");
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, globalFilter: filter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFilter,
    globalFilterFn: (row, _id, value: string) =>
      row.original.name.toLowerCase().includes(value.toLowerCase()),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });
  return (
    <div>
      <input
        className="search"
        placeholder="Search sub-basin by name…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <table className="table">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th key={h.id}>
                  <button className="th-btn" onClick={h.column.getToggleSortingHandler()}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
                  </button>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((r) => (
            <tr
              key={r.id}
              className={r.original.risk_flag === "yes" ? "flagged" : undefined}
              onClick={() => onSelect(r.original)}
            >
              {r.getVisibleCells().map((c) => (
                <td key={c.id}>{flexRender(c.column.columnDef.cell, c.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
