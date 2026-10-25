import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { csvUrl, exportUrl, tileUrl } from "../api";
import { Banner } from "../components/Banner";
import { LabelForm } from "../components/LabelForm";
import { LayerSwitcher } from "../components/LayerSwitcher";
import { PointPanel } from "../components/PointPanel";
import { SubbasinTable } from "../components/SubbasinTable";
import type { PointInfo, SubbasinRow } from "../types";

describe("api urls", () => {
  it("builds tile, csv and export urls", () => {
    expect(tileUrl("forest", 2022)).toBe("/api/tiles/forest/2022/{z}/{x}/{y}.png");
    expect(csvUrl(2022)).toBe("/api/subbasins/2022.csv");
    expect(exportUrl("delta_s", 2021)).toBe("/api/export/delta_s/2021.tif");
  });
});

describe("Banner (NFR-8)", () => {
  it("shows the experimental notice and the model AUC", () => {
    render(<Banner layer="susceptibility" metrics={{ flood_auc: 0.873, forest_oa: null }} />);
    expect(
      screen.getByText(/Experimental decision support — not an official flood warning\./),
    ).toBeInTheDocument();
    expect(screen.getByText(/Model AUC 0\.87 \(held-out events\)/)).toBeInTheDocument();
  });

  it("shows forest accuracy on forest layers", () => {
    render(<Banner layer="forest" metrics={{ flood_auc: 0.9, forest_oa: 0.934 }} />);
    expect(screen.getByText(/Forest OA 93\.4%/)).toBeInTheDocument();
  });

  it("says when accuracy is not yet available", () => {
    render(<Banner layer="forest" metrics={{ flood_auc: null, forest_oa: null }} />);
    expect(screen.getByText(/accuracy not yet validated/)).toBeInTheDocument();
  });
});

describe("LayerSwitcher", () => {
  it("emits the chosen layer", async () => {
    const onChange = vi.fn();
    render(<LayerSwitcher layers={["forest", "susceptibility"]} value="forest" onChange={onChange} />);
    await userEvent.click(screen.getByLabelText(/Flood susceptibility/));
    expect(onChange).toHaveBeenCalledWith("susceptibility");
  });
});

const point: PointInfo = {
  row: 1,
  col: 2,
  year: 2022,
  forest_fraction: [
    { year: 2019, value: 0.9 },
    { year: 2022, value: 0.4 },
  ],
  susceptibility: 0.71,
  risk_class: 4,
  delta_s: 0.12,
  top_features: [
    { name: "hand", contribution: -1.2, value: 3.1 },
    { name: "U", contribution: 0.8, value: 0.2 },
    { name: "Q", contribution: 0.3, value: 40 },
  ],
};

describe("PointPanel (FR-V3)", () => {
  it("renders susceptibility, class, delta and top features", () => {
    render(<PointPanel point={point} error={null} />);
    expect(screen.getByText("0.71")).toBeInTheDocument();
    expect(screen.getByText(/High/)).toBeInTheDocument();
    expect(screen.getByText("+0.120")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("shows No data here on error", () => {
    render(<PointPanel point={null} error="No data here (outside the study area)" />);
    expect(screen.getByText(/No data here/)).toBeInTheDocument();
  });
});

const rows: SubbasinRow[] = [
  { subbasin_id: 1, name: "Amchang", area_km2: 10, forest_loss_ha: 5, forest_fraction: 0.5, mean_s: 0.2, mean_delta_s: 0.01, area_class_1: 1, area_class_2: 2, area_class_3: 3, area_class_4: 2, area_class_5: 2, area_moved_up_km2: 1, risk_class: 2, risk_flag: "no" },
  { subbasin_id: 2, name: "Bhalukpong", area_km2: 12, forest_loss_ha: 50, forest_fraction: 0.3, mean_s: 0.7, mean_delta_s: 0.05, area_class_1: 1, area_class_2: 1, area_class_3: 2, area_class_4: 4, area_class_5: 4, area_moved_up_km2: 3, risk_class: 4, risk_flag: "yes" },
];

describe("SubbasinTable (FR-V2, NFR-6)", () => {
  it("sorts by forest loss (largest first) when the header is clicked", async () => {
    render(<SubbasinTable rows={rows} onSelect={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /Forest loss/ }));
    const cells = screen.getAllByTestId("name-cell").map((c) => c.textContent);
    expect(cells).toEqual(["Bhalukpong", "Amchang"]);
  });

  it("filters by name", async () => {
    render(<SubbasinTable rows={rows} onSelect={() => {}} />);
    await userEvent.type(screen.getByPlaceholderText(/Search sub-basin/), "amch");
    expect(screen.getAllByTestId("name-cell").map((c) => c.textContent)).toEqual(["Amchang"]);
  });
});

describe("LabelForm", () => {
  it("submits the chosen labels for the interpreter", async () => {
    const onSubmit = vi.fn();
    render(<LabelForm pointId="P0007" interpreter="B" initial={null} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("radio", { name: /t0: Forest/ }));
    await userEvent.click(screen.getByRole("radio", { name: /latest: Non-forest/ }));
    await userEvent.click(screen.getByRole("button", { name: /Save/ }));
    expect(onSubmit).toHaveBeenCalledWith({
      point_id: "P0007",
      interpreter: "B",
      label_t0: "forest",
      label_t: "non_forest",
      note: "",
    });
  });
});
