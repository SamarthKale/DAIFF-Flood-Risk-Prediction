import { useEffect, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes, useNavigate } from "react-router-dom";

import { ApiError, getMeta } from "./api";
import { LabellingPage } from "./pages/LabellingPage";
import { MapPage } from "./pages/MapPage";
import { SubbasinsPage } from "./pages/SubbasinsPage";
import { ValidationPage } from "./pages/ValidationPage";
import type { Meta } from "./types";

function Shell({ meta }: { meta: Meta }) {
  const [focus, setFocus] = useState<number | null>(null);
  const navigate = useNavigate();
  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          DAIFF <span className="muted">· {meta.basin} · forest change &amp; flood risk</span>
        </div>
        <nav>
          <NavLink to="/" end>
            Map
          </NavLink>
          <NavLink to="/subbasins">Sub-basins</NavLink>
          <NavLink to="/validation">Validation</NavLink>
          <NavLink to="/labelling">Labelling</NavLink>
        </nav>
        <div className="muted small">run {meta.run_id}</div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<MapPage meta={meta} focus={focus} />} />
          <Route
            path="/subbasins"
            element={
              <SubbasinsPage
                meta={meta}
                onSelect={(id) => {
                  setFocus(id);
                  navigate("/");
                }}
              />
            }
          />
          <Route path="/validation" element={<ValidationPage />} />
          <Route path="/labelling" element={<LabellingPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getMeta()
      .then(setMeta)
      .catch((e) =>
        setError(
          e instanceof ApiError && e.status === 503
            ? "No published run yet — run `daiff run -c <config>` first."
            : `Cannot reach the DAIFF API (${e.message}). Start it with \`daiff serve -c <config>\`.`,
        ),
      );
  }, []);
  if (error) return <div className="page error">{error}</div>;
  if (!meta) return <div className="page">Loading…</div>;
  return (
    <BrowserRouter>
      <Shell meta={meta} />
    </BrowserRouter>
  );
}
