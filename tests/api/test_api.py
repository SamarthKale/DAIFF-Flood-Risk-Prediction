import io
import time

import numpy as np
import pandas as pd
import pytest
import rasterio
from fastapi.testclient import TestClient
from PIL import Image
from rasterio.warp import transform

from daiff.alerts.flags import flags
from daiff.api.app import create_app
from daiff.config import load_config
from daiff.grid import Grid
from daiff.store.cog import read_raster
from daiff.store.run_store import RunStore
from daiff.validation.forest_accuracy import cohens_kappa
from tests.conftest import SYN_CONFIG

# Web-Mercator tile over the synthetic basin centre (≈ 90.97E, 26.2N) at z=12
Z, X, Y = 12, 3083, 1734


def _tile_xyz(lon, lat, z):
    import math

    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def _centre(cfg):
    g = Grid.from_config(cfg)
    xmin, ymin, xmax, ymax = g.bounds
    lon, lat = transform(g.crs, "EPSG:4326", [(xmin + xmax) / 2], [(ymin + ymax) / 2])
    return lon[0], lat[0]


def test_meta(client, api_env):
    cfg, run_id, _ = api_env
    m = client.get("/api/meta").json()
    assert m["run_id"] == run_id and m["years"] == cfg.years.years and m["t0"] == 2019
    assert set(m["layers"]) >= {"forest", "loss", "susceptibility", "riskclass", "delta_s"}
    assert 0.5 < m["metrics"]["flood_auc"] <= 1.0


def test_no_published_run_gives_503(tmp_path):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
    r = TestClient(create_app(cfg)).get("/api/meta")
    assert r.status_code == 503 and r.json()["detail"] == "no published run"


@pytest.mark.parametrize("layer", ["forest", "loss", "susceptibility", "riskclass", "delta_s"])
def test_fr_v1_tile_renders_png(client, api_env, layer):
    cfg = api_env[0]
    x, y = _tile_xyz(*_centre(cfg), 13)
    start = time.perf_counter()
    r = client.get(f"/api/tiles/{layer}/2022/13/{x}/{y}.png")
    assert time.perf_counter() - start < 3.0  # NFR-5 budget, measured locally
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(r.content))
    assert img.size == (256, 256)
    assert np.asarray(img.convert("RGBA"))[..., 3].max() > 0


def test_tile_unknown_layer_or_missing_file_is_404(client):
    assert client.get("/api/tiles/nope/2022/12/0/0.png").status_code == 404
    assert client.get("/api/tiles/preview/2022/12/0/0.png").status_code == 404  # not in synthetic
    assert client.get("/api/tiles/forest/1999/12/0/0.png").status_code == 404


def test_tile_outside_basin_is_transparent(client):
    r = client.get("/api/tiles/forest/2022/12/0/0.png")
    assert r.status_code == 200
    assert np.asarray(Image.open(io.BytesIO(r.content)).convert("RGBA"))[..., 3].max() == 0


def test_fr_v2_csv_is_byte_identical_to_pipeline(client, api_env):
    cfg, run_id, _ = api_env
    r = client.get("/api/subbasins/2022.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.content == RunStore(cfg.data_root, run_id).subbasin_csv(2022).read_bytes()


def test_subbasins_geojson_has_table_and_utf8_names(client):
    fc = client.get("/api/subbasins?year=2022").json()
    props = [f["properties"] for f in fc["features"]]
    assert len(props) == 4 and {"forest_loss_ha", "mean_s", "risk_flag", "name"} <= props[0].keys()
    assert "Āmchang Kopili-ūpper" in {p["name"] for p in props}


def test_fr_v2_geotiff_export_has_crs_and_transform(client, api_env):
    cfg = api_env[0]
    r = client.get("/api/export/susceptibility/2022.tif")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    with rasterio.MemoryFile(r.content) as mem, mem.open() as src:
        g = Grid.from_config(cfg)
        assert src.crs.to_epsg() == 32646 and src.transform == g.transform


def test_flags_match_table(client, api_env):
    cfg, run_id, _ = api_env
    table = pd.read_csv(RunStore(cfg.data_root, run_id).subbasin_csv(2022))
    assert client.get("/api/flags?year=2022").json()["flagged"] == flags(table)


def test_fr_v3_point_values_match_rasters_at_10_random_points(client, api_env):
    cfg, run_id, _ = api_env
    s = RunStore(cfg.data_root, run_id)
    g = Grid.from_config(cfg)
    S = read_raster(s.susceptibility(2022), g)
    F = {y: read_raster(s.forest(y), g) for y in cfg.years.years}
    rng = np.random.default_rng(3)
    land = np.argwhere(~np.isnan(S))
    for r, c in land[rng.choice(len(land), 10, replace=False)]:
        x = g.transform.c + (c + 0.5) * g.res
        y = g.transform.f - (r + 0.5) * g.res
        lon, lat = transform(g.crs, "EPSG:4326", [x], [y])
        p = client.get(f"/api/point?lon={lon[0]}&lat={lat[0]}&year=2022").json()
        assert (p["row"], p["col"]) == (r, c)
        assert p["susceptibility"] == pytest.approx(float(S[r, c]), abs=1e-6)
        assert [v["value"] for v in p["forest_fraction"]] == pytest.approx(
            [float(F[y][r, c]) for y in cfg.years.years], abs=1e-6, nan_ok=True
        )
        assert len(p["top_features"]) == 3


def test_point_outside_grid_is_404(client):
    r = client.get("/api/point?lon=10&lat=10&year=2022")
    assert r.status_code == 404 and "No data" in r.json()["detail"]


def test_metrics_endpoint(client):
    m = client.get("/api/metrics").json()
    assert "flood_train" in m


def test_labelling_upsert_and_agreement(api_env, tmp_path):
    cfg = api_env[0]
    pts = pd.DataFrame(
        {
            "point_id": ["P0001", "P0002"],
            "row": [0, 1],
            "col": [0, 1],
            "x": [0, 0],
            "y": [0, 0],
            "lon": [91.0, 91.0],
            "lat": [26.2, 26.2],
            "stratum": [1, 3],
        }
    )
    pts.to_csv(tmp_path / "forest_sample_points_synthetic.csv", index=False)
    c = TestClient(create_app(cfg, reference_dir=tmp_path))
    body = {"point_id": "P0001", "interpreter": "A", "label_t0": "forest", "label_t": "forest"}
    assert c.post("/api/labelling/labels", json=body).status_code == 200
    c.post("/api/labelling/labels", json={**body, "label_t": "non_forest"})  # overwrite A only
    c.post("/api/labelling/labels", json={**body, "interpreter": "B"})
    c.post("/api/labelling/labels", json={**body, "point_id": "P0002", "label_t": "non_forest"})
    c.post(
        "/api/labelling/labels",
        json={**body, "point_id": "P0002", "interpreter": "B", "label_t": "non_forest"},
    )
    labels = pd.read_csv(tmp_path / "forest_labels_synthetic.csv")
    assert len(labels) == 4
    a = labels[(labels.point_id == "P0001") & (labels.interpreter == "A")].iloc[0]
    assert a.label_t == "non_forest"
    pts_a = c.get("/api/labelling/points?interpreter=A").json()
    assert [p["point_id"] for p in pts_a["points"]] == ["P0001", "P0002"]
    assert pts_a["points"][0]["label"]["label_t"] == "non_forest"
    ag = c.get("/api/labelling/agreement").json()
    assert ag["kappa_t"] == pytest.approx(
        cohens_kappa(["non_forest", "non_forest"], ["forest", "non_forest"])
    )
    assert ag["needs_adjudication"] == ["P0001"]
    bad = c.post("/api/labelling/labels", json={**body, "label_t": "tree"})
    assert bad.status_code == 422
