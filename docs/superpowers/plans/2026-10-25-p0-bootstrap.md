# P0 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. If superpowers is not installed, execute the tasks in order yourself, following CLAUDE.md's session protocol.

**Goal:** Stand up the `daiff` Python package with typed config, the common grid and its FR-D5 check,
a provenance-tagged COG store, the stage-DAG runner, a synthetic raw basin, CLI checks, CI, and the
setup/verification docs. After this, P1 can build science stages on top of it without Earth Engine.

**Architecture:** src-layout package `daiff` managed by uv (Python 3.12). Pure-Python modules with
small, single-purpose files: `config` (pydantic over YAML), `grid` (snapped UTM grid + alignment
check), `store/` (COG I/O, provenance, run store, raw-input layout, metadata check), `pipeline/`
(fingerprinted DAG runner), `synthetic` (fake basin writing the same raw layout GEE will produce in
P3), and `cli` (typer).

**Tech Stack:** Python 3.12, uv, numpy, rasterio (bundled GDAL), pydantic v2, PyYAML, typer,
python-dotenv, pandas, pytest, pytest-cov, ruff, GitHub Actions, gitleaks.

**Spec:** `docs/superpowers/specs/2026-10-25-daiff-system-design.md` (sections 4, 5, 6.1–6.4, 6.16,
8, 11). Requirement texts: `docs/srs/requirements.md`.

## Global Constraints

- Python `>=3.12`; `.python-version` = `3.12`; uv `link-mode = "copy"` (repo may live on exFAT).
- Grid CRS `EPSG:32646`; 30 m cells; origin snapped to multiples of the resolution; the 10 m grid
  nests 3 × 3 per cell with a shared origin.
- float32 nodata = NaN; uint8 class nodata = 255.
- COG: DEFLATE, predictor on, 512 × 512 blocks, AUTO overviews. Tags contain no timestamps.
- Provenance tag keys: `DAIFF_RUN_ID`, `DAIFF_CONFIG_HASH`, `DAIFF_CODE_COMMIT`, `DAIFF_MODEL_ID`,
  `DAIFF_INPUTS`, `DAIFF_DATA_VERSIONS`, `DAIFF_YEAR`, `DAIFF_T0`.
- `run_id` = first 12 hex chars of SHA-256(config hash + code commit + sorted input checksums).
- Appendix C output names exactly: `forest_<year>.tif`, `loss_<t0>_<year>.tif`, `coupling_<year>.tif`,
  `susceptibility_<year>.tif`, `riskclass_<year>.tif`, `delta_s_<year>.tif`, `subbasin_<year>.csv`,
  `run_metadata.json`. The published run is named in `data/store/CURRENT` (plain text, no symlink).
- Season year *t* = dry season 1 Nov (t−1) – 31 Mar t (D-18).
- No machine-specific paths in code, config or tests. Relative config paths resolve against the
  config file's directory. `DAIFF_DATA_ROOT` overrides the data root.
- Test names carry requirement IDs where one applies (`test_fr_d5_…`, `test_nfr_3_…`).
- Every task ends per CLAUDE.md: tick the checkbox, update `docs/STATUS.md`, commit with **no AI
  co-author trailer**, `git push origin main`. Never wait for CI.

## Review Focus

1. **Different machines, same science** — two teammates with different `DAIFF_DATA_ROOT` or Earth
   Engine projects must get the same config hash, run_id and provenance tags. Pinned in Task 2
   (hash ignores machine settings) and Task 5 (inputs recorded relative to the data root).
2. **Paths with spaces** — Windows home folders like `C:\Users\Samarth Kale` contain spaces;
   writing and reading rasters there must work. Pinned in Task 4.
3. **Sub-pixel misalignment** — a half-cell (15 m) shift must fail FR-D5, while float noise
   (≤ 1e-6 m) must pass. Pinned in Task 3.
4. **A session dies mid-stage** — a stage that raises must leave no "done" state, so the next run
   redoes it. Pinned in Task 6.
5. **Nothing published yet** — `check-metadata` with no `CURRENT` run must exit with a clear message
   (code 2), not a traceback. Pinned in Task 8.

---

## File map

| File | Responsibility |
|---|---|
| `pyproject.toml`, `.python-version`, `.env.example`, `README.md` | Package, tooling, env template, quick start |
| `src/daiff/__init__.py` | `__version__` |
| `src/daiff/cli.py` | `daiff` typer app: `--version`, `synth`, `check-grid`, `check-metadata` |
| `src/daiff/config.py` | Pydantic config models, `load_config`, `config_hash`, `section_hash` |
| `configs/synthetic.yaml`, `configs/kopili.yaml` | Project configs |
| `src/daiff/grid.py` | `Grid`, `check_alignment`, `AlignmentReport`, `LayerProblem` |
| `src/daiff/store/__init__.py` | Re-exports of the store API |
| `src/daiff/store/cog.py` | `write_cog`, `read_raster`, `read_tags`, `read_band_names`, `GridMismatchError` |
| `src/daiff/store/provenance.py` | `sha256_file`, `code_commit`, `compute_run_id`, `build_tags`, `REQUIRED_TAGS` |
| `src/daiff/store/run_store.py` | `RunStore`, `publish`, `current_run`, `write_run_metadata`, `RUN_METADATA_KEYS` |
| `src/daiff/store/check.py` | `check_metadata`, `MetadataProblem` |
| `src/daiff/store/raw_layout.py` | `RawLayout` — paths of raw inputs shared by synthetic (P0) and GEE (P3) |
| `src/daiff/pipeline/__init__.py`, `src/daiff/pipeline/runner.py` | `Stage`, `StageContext`, `StageResult`, `Runner`, `fingerprint`, `PipelineError` |
| `src/daiff/synthetic.py` | `make_basin` |
| `tests/conftest.py` | `REPO`, `SYN_CONFIG`, `small_grid`, `synthetic_cfg` fixtures |
| `.github/workflows/ci.yml` | Lint, tests + coverage, gitleaks |
| `docs/setup/gee.md`, `docs/verification_matrix.md`, `docs/test_log.md`, `docs/LICENSES.md`, `docs/perf/README.md` | Human setup, traceability, SRS 8.3 log, NFR-7, NFR-1/2 log home |

---

### Task 1: Package scaffold and `daiff --version`

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.env.example`, `README.md`, `src/daiff/__init__.py`, `src/daiff/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `daiff.__version__ = "0.1.0"`; `daiff.cli.app` (a `typer.Typer`); console script `daiff`.

- [x] **Step 1: Write `pyproject.toml` and `.python-version`**

`.python-version` contains `3.12`. `pyproject.toml`:

```toml
[project]
name = "daiff"
version = "0.1.0"
description = "AI-Based Deforestation Monitoring and Flood Risk Prediction (DAIFF)"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "numpy>=2.0",
  "pandas>=2.2",
  "rasterio>=1.4",
  "pydantic>=2.7",
  "pyyaml>=6.0",
  "typer>=0.12",
  "python-dotenv>=1.0",
  "earthengine-api>=1.0",   # installed early so teammates can run the GEE smoke test (docs/setup/gee.md)
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.6"]

[project.scripts]
daiff = "daiff.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/daiff"]

[tool.uv]
link-mode = "copy"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "gee: needs live Google Earth Engine access (skipped in CI)",
  "slow: long-running test",
  "colab: needs a Colab GPU runtime",
]
```

- [x] **Step 2: Write `.env.example` and `README.md`**

`.env.example` (every value empty, with one comment line each): `DAIFF_GEE_PROJECT=`, `DAIFF_DATA_ROOT=`,
`SMTP_HOST=`, `SMTP_PORT=`, `SMTP_USER=`, `SMTP_PASSWORD=`, `ALERT_EMAIL_TO=`.
`README.md`: project title, one-paragraph description (copy the first paragraph of the spec §1), a
"Quick start" with `uv sync --extra dev`, `uv run pytest -m "not gee and not slow"`, a pointer to
`CLAUDE.md` and `docs/STATUS.md`, and a "Licence: to be decided by the team (see docs/STATUS.md)" line.

- [x] **Step 3: Write the failing test** — `tests/test_cli.py`

```python
from typer.testing import CliRunner

from daiff import __version__
from daiff.cli import app


def test_cli_version_prints_package_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"daiff {__version__}"
```

- [x] **Step 4: Create the environment and run the test to verify it fails**

Run: `uv sync --extra dev` (uv downloads Python 3.12 if it is missing), then
`uv run pytest tests/test_cli.py -v`.
Expected: FAIL — `ModuleNotFoundError: No module named 'daiff'` or an import error for `app`.

- [x] **Step 5: Implement `src/daiff/__init__.py` and `src/daiff/cli.py`**

`__init__.py`: module docstring + `__version__ = "0.1.0"`. `cli.py`: `app = typer.Typer(no_args_is_help=True)`
with an `@app.callback(invoke_without_command=True)` that has an eager `--version` option printing
`daiff {__version__}` and exiting 0.

- [x] **Step 6: Run the tests and lint**

Run: `uv run pytest tests/test_cli.py -v && uv run ruff check . && uv run ruff format --check .`
Expected: 1 passed; ruff reports no problems (run `uv run ruff format .` first if needed).

- [x] **Step 7: Close the task**

Tick this task, set STATUS "Last done: P0 Task 1", "Next task: P0 Task 2". Then:
```bash
git add pyproject.toml uv.lock .python-version .env.example README.md src tests docs/STATUS.md docs/superpowers/plans/2026-10-25-p0-bootstrap.md
git commit -m "feat(cli): scaffold daiff package with uv and --version"
git push origin main
```

---

### Task 2: Typed configuration

**Files:**
- Create: `src/daiff/config.py`, `configs/synthetic.yaml`, `configs/kopili.yaml`, `tests/conftest.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `load_config(path: str | Path, env: Mapping[str, str] | None = None) -> DaiffConfig`. With
    `env=None`, the environment is `{**dotenv_values(<config dir>/../.env), **os.environ}`.
  - `DaiffConfig` (pydantic, `extra="forbid"`, frozen) with fields `project`, `grid`, `years`,
    `gee`, `runtime`, `paths`, `synthetic: SyntheticConfig | None = None`, and property
    `data_root -> Path`, the resolved effective root = `(DAIFF_DATA_ROOT or <config dir>/paths.data_root) / project.name`.
  - `ProjectConfig(name: str  # ^[a-z0-9_-]+$, basin: str)`
  - `GridConfig(crs: str = "EPSG:32646", res: float = 30.0, bounds: tuple[float, float, float, float] | None = None, buffer_m: float = 1000.0)`
  - `YearsConfig(t0: int, years: list[int], season_start_month: int = 11, season_end_month: int = 3)`.
    Validation: years strictly increasing, all ≥ 2015, t0 ∈ years.
  - `GeeConfig(project: str | None = None, asset_root: str | None = None)`. Env `DAIFF_GEE_PROJECT`
    overrides `project`.
  - `RuntimeConfig(seed: int = 42)`
  - `PathsConfig(data_root: Path = Path("../data"))`
  - `SyntheticConfig(size: int = 200, subbasin_split: int = 2)`
  - `config_hash(cfg: DaiffConfig) -> str` — 64-hex SHA-256 of canonical JSON (`sort_keys=True`,
    `separators=(",", ":")`) of `cfg.model_dump(mode="json")`, **excluding** `paths`,
    `gee.project` and `gee.asset_root` (machine/person-specific).
  - `section_hash(cfg: DaiffConfig, name: str) -> str` — the same, for one top-level section.
  - `tests/conftest.py` fixtures: `REPO: Path` (repo root), `SYN_CONFIG = REPO / "configs" / "synthetic.yaml"`,
    `synthetic_cfg(tmp_path) -> DaiffConfig` (loaded with `env={"DAIFF_DATA_ROOT": str(tmp_path)}`),
    `small_grid` (added in Task 3).

- [x] **Step 1: Write the configs**

`configs/synthetic.yaml`:
```yaml
project: {name: synthetic, basin: synthetic}
grid:
  crs: EPSG:32646
  res: 30
  bounds: [300000, 2899980, 306000, 2905980]   # 200 x 200 cells
  buffer_m: 0
years:
  t0: 2019
  years: [2019, 2020, 2021, 2022, 2023, 2024]
gee: {project: null, asset_root: null}
runtime: {seed: 42}
paths: {data_root: ../data}
synthetic: {size: 200, subbasin_split: 2}
```
`configs/kopili.yaml`: `project: {name: kopili, basin: "Kopili, Assam"}`; grid crs EPSG:32646,
res 30, `bounds: null` (comment: "set from the AOI in P3"), buffer_m 1000; years t0 2019 (comment:
"D-24 — re-check L2A coverage in P3"), years 2019–2026; gee nulls; seed 42; data_root `../data`.

- [x] **Step 2: Write the failing tests** — `tests/test_config.py` (plus the conftest fixtures above)

```python
import pytest
from pydantic import ValidationError

from daiff.config import config_hash, load_config, section_hash
from tests.conftest import REPO, SYN_CONFIG


def _variant(tmp_path, old, new):
    p = tmp_path / "configs" / "variant.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(SYN_CONFIG.read_text().replace(old, new))
    return p


def test_load_synthetic_config():
    cfg = load_config(SYN_CONFIG, env={})
    assert cfg.project.name == "synthetic"
    assert cfg.grid.crs == "EPSG:32646" and cfg.grid.res == 30
    assert cfg.years.t0 == 2019 and cfg.years.years == [2019, 2020, 2021, 2022, 2023, 2024]
    assert cfg.data_root == (REPO / "data" / "synthetic").resolve()


def test_env_overrides_data_root_and_gee_project(tmp_path):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path), "DAIFF_GEE_PROJECT": "p1"})
    assert cfg.data_root == (tmp_path / "synthetic").resolve()
    assert cfg.gee.project == "p1"


def test_config_hash_ignores_machine_specific_settings(tmp_path):
    a = load_config(SYN_CONFIG, env={})
    b = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path), "DAIFF_GEE_PROJECT": "x"})
    assert config_hash(a) == config_hash(b)
    assert len(config_hash(a)) == 64


def test_config_hash_and_section_hash_track_science_settings(tmp_path):
    base = load_config(SYN_CONFIG, env={})
    changed = load_config(_variant(tmp_path, "seed: 42", "seed: 7"), env={})
    assert config_hash(changed) != config_hash(base)
    assert section_hash(changed, "runtime") != section_hash(base, "runtime")
    assert section_hash(changed, "grid") == section_hash(base, "grid")


def test_unknown_key_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        load_config(
            _variant(tmp_path, "runtime: {seed: 42}", "runtime: {seed: 42, sede: 1}"), env={}
        )


@pytest.mark.parametrize(
    "years_line",
    [
        "years: [2020, 2019, 2021, 2022, 2023, 2024]",  # not increasing
        "years: [2019, 2019, 2021, 2022, 2023, 2024]",  # duplicate
        "years: [2020, 2021, 2022, 2023, 2024, 2025]",  # t0 2019 missing
        "years: [2014, 2019, 2021, 2022, 2023, 2024]",  # before 2015
    ],
)
def test_invalid_years_are_rejected(tmp_path, years_line):
    with pytest.raises(ValidationError):
        load_config(
            _variant(tmp_path, "years: [2019, 2020, 2021, 2022, 2023, 2024]", years_line), env={}
        )
```

Add `tests/__init__.py` (empty) so `from tests.conftest import …` works.

- [x] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daiff.config'`.

- [x] **Step 4: Implement `src/daiff/config.py`** with the interfaces above. Apply env overrides to
the raw YAML dict before validation (`gee.project`). Compute the effective data root at load time
and keep it in a private attribute behind the `data_root` property.

- [x] **Step 5: Run the tests and lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [x] **Step 6: Close the task** — tick, update STATUS (next: Task 3), then
`git add configs src tests docs` · `git commit -m "feat(config): typed YAML config with portable hashing"` · `git push origin main`.

---

### Task 3: Common grid and FR-D5 alignment check

**Files:**
- Create: `src/daiff/grid.py`
- Modify: `tests/conftest.py` (add `small_grid`)
- Test: `tests/test_grid.py`

**Interfaces:**
- Consumes: `DaiffConfig` (Task 2).
- Produces:
  - `@dataclass(frozen=True) class Grid: crs: str; transform: affine.Affine; width: int; height: int`
    - `Grid.from_bounds(crs: str, bounds: tuple[float, float, float, float], res: float, buffer_m: float = 0.0) -> Grid`
      — expand by the buffer, then snap xmin/ymin down and xmax/ymax up to multiples of `res`.
    - `Grid.from_config(cfg: DaiffConfig) -> Grid` — raises `ValueError("grid.bounds is not set …")` when bounds are None.
    - `res -> float`, `bounds -> tuple[float, float, float, float]`, `shape -> tuple[int, int]` (height, width), `cell_area_m2 -> float`
    - `nested(factor: int) -> Grid` — same origin, `res / factor`, `width * factor`, `height * factor`
    - `xy_to_rowcol(x: float, y: float) -> tuple[int, int]` — raises `ValueError` outside the grid
    - `to_dict() -> dict` / `Grid.from_dict(d: dict) -> Grid` (keys `crs`, `transform` as 6 floats `[a, b, c, d, e, f]`, `width`, `height`; unknown keys are ignored)
  - `@dataclass(frozen=True) class LayerProblem: path: Path; field: Literal["missing", "crs", "transform", "shape"]; expected: str; actual: str`
  - `@dataclass class AlignmentReport: checked: list[Path]; problems: list[LayerProblem]` with property `ok -> bool`
  - `check_alignment(paths: Sequence[Path], grid: Grid, atol: float = 1e-6) -> AlignmentReport`
  - Fixture `small_grid = Grid.from_bounds("EPSG:32646", (300000, 2900010, 300120, 2900100), res=30)` (4 × 3 cells)

- [x] **Step 1: Write the failing tests** — `tests/test_grid.py`

```python
import numpy as np
import pytest
import rasterio
from affine import Affine

from daiff.config import load_config
from daiff.grid import Grid, check_alignment
from tests.conftest import REPO

B = (300010.0, 2900020.0, 300095.0, 2900100.0)


def _write(path, grid, crs=None, transform=None, shape=None):
    h, w = shape or grid.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype="float32",
        crs=crs or grid.crs,
        transform=transform or grid.transform,
    ) as dst:
        dst.write(np.zeros((h, w), "float32"), 1)
    return path


def test_from_bounds_snaps_outward_to_resolution():
    g = Grid.from_bounds("EPSG:32646", B, res=30)
    assert g.transform == Affine(30, 0, 300000, 0, -30, 2900100)
    assert (g.width, g.height) == (4, 3)


def test_from_bounds_applies_buffer_before_snapping():
    g = Grid.from_bounds("EPSG:32646", B, res=30, buffer_m=60)
    assert g.transform.c == 299940 and g.width == 8


def test_nested_grid_shares_origin_and_is_three_times_finer():
    n = Grid.from_bounds("EPSG:32646", B, res=30).nested(3)
    assert n.transform == Affine(10, 0, 300000, 0, -10, 2900100)
    assert (n.width, n.height) == (12, 9)


def test_cell_area_and_xy_to_rowcol():
    g = Grid.from_bounds("EPSG:32646", B, res=30)
    assert g.cell_area_m2 == 900.0
    assert g.xy_to_rowcol(300001.0, 2900099.0) == (0, 0)
    assert g.xy_to_rowcol(300119.0, 2900011.0) == (2, 3)
    with pytest.raises(ValueError):
        g.xy_to_rowcol(299999.0, 2900050.0)


def test_dict_roundtrip():
    g = Grid.from_bounds("EPSG:32646", B, res=30)
    assert Grid.from_dict(g.to_dict()) == g


def test_from_config_uses_bounds_and_requires_them(synthetic_cfg):
    assert Grid.from_config(synthetic_cfg).shape == (200, 200)
    kopili = load_config(REPO / "configs" / "kopili.yaml", env={})
    with pytest.raises(ValueError, match="grid.bounds"):
        Grid.from_config(kopili)


def test_fr_d5_aligned_layers_pass(tmp_path, small_grid):
    report = check_alignment([_write(tmp_path / "a.tif", small_grid)], small_grid)
    assert report.ok and report.problems == []


def test_fr_d5_detects_crs_mismatch(tmp_path, small_grid):
    report = check_alignment([_write(tmp_path / "a.tif", small_grid, crs="EPSG:32645")], small_grid)
    assert not report.ok and report.problems[0].field == "crs"


def test_fr_d5_detects_shape_mismatch(tmp_path, small_grid):
    report = check_alignment([_write(tmp_path / "a.tif", small_grid, shape=(3, 5))], small_grid)
    assert [p.field for p in report.problems] == ["shape"]


def test_fr_d5_detects_half_cell_shift(tmp_path, small_grid):
    shifted = small_grid.transform @ Affine.translation(0.5, 0)  # 15 m east
    report = check_alignment(
        [_write(tmp_path / "a.tif", small_grid, transform=shifted)], small_grid
    )
    assert [p.field for p in report.problems] == ["transform"]


def test_fr_d5_tolerates_float_noise(tmp_path, small_grid):
    t = small_grid.transform
    noisy = Affine(t.a, t.b, t.c + 1e-7, t.d, t.e, t.f)
    assert check_alignment([_write(tmp_path / "a.tif", small_grid, transform=noisy)], small_grid).ok


def test_fr_d5_reports_missing_file(tmp_path, small_grid):
    report = check_alignment([tmp_path / "nope.tif"], small_grid)
    assert [p.field for p in report.problems] == ["missing"]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_grid.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daiff.grid'`.

- [x] **Step 3: Implement `src/daiff/grid.py`** with the interfaces above. Compare CRS with
`rasterio.crs.CRS.from_user_input(grid.crs) == src.crs` and transforms with
`transform.almost_equals(expected, precision=atol)`. Check one problem per field, in the order missing → crs → shape → transform.

- [x] **Step 4: Run the tests and lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [x] **Step 5: Close the task** — tick, update STATUS, `git commit -m "feat(grid): snapped UTM grid and FR-D5 alignment check"`, push.

---

### Task 4: COG writer and reader

**Files:**
- Create: `src/daiff/store/__init__.py`, `src/daiff/store/cog.py`
- Test: `tests/store/__init__.py`, `tests/store/test_cog.py`

**Interfaces:**
- Consumes: `Grid` (Task 3).
- Produces:
  - `write_cog(path: Path, array: np.ndarray, grid: Grid, *, nodata: float | int, tags: Mapping[str, str], band_names: Sequence[str] | None = None) -> Path`
    — `array` is 2-D `(h, w)` or 3-D `(bands, h, w)` matching `grid.shape`, otherwise `ValueError`.
    Creates parent directories.
  - `read_raster(path: Path, grid: Grid) -> np.ndarray` — 2-D for single-band, 3-D otherwise.
    Raises `GridMismatchError` (subclass of `ValueError`) when `check_alignment` fails.
  - `read_tags(path: Path) -> dict[str, str]`; `read_band_names(path: Path) -> list[str]`

- [x] **Step 1: Write the failing tests** — `tests/store/test_cog.py`

```python
import hashlib

import numpy as np
import pytest
import rasterio
from rasterio.enums import Compression

from daiff.grid import Grid
from daiff.store.cog import GridMismatchError, read_band_names, read_raster, read_tags, write_cog


def test_float_roundtrip_preserves_nan_and_tags(tmp_path, small_grid):
    arr = np.arange(12, dtype="float32").reshape(3, 4)
    arr[0, 0] = np.nan
    p = write_cog(tmp_path / "a.tif", arr, small_grid, nodata=np.nan, tags={"DAIFF_YEAR": "2020"})
    out = read_raster(p, small_grid)
    assert np.isnan(out[0, 0]) and np.array_equal(out[1:], arr[1:])
    assert read_tags(p)["DAIFF_YEAR"] == "2020"


def test_uint8_nodata_255_roundtrip(tmp_path, small_grid):
    arr = np.full((3, 4), 255, dtype="uint8")
    arr[1, 1] = 1
    p = write_cog(tmp_path / "c.tif", arr, small_grid, nodata=255, tags={})
    assert np.array_equal(read_raster(p, small_grid), arr)


def test_multiband_band_names(tmp_path, small_grid):
    arr = np.zeros((4, 3, 4), dtype="float32")
    p = write_cog(
        tmp_path / "m.tif",
        arr,
        small_grid,
        nodata=np.nan,
        tags={},
        band_names=["f", "dF", "U", "Q"],
    )
    assert read_raster(p, small_grid).shape == (4, 3, 4)
    assert read_band_names(p) == ["f", "dF", "U", "Q"]


def test_output_is_cog_with_overviews(tmp_path):
    g = Grid.from_bounds("EPSG:32646", (300000, 2900010, 330720, 2930730), res=30)  # 1024 x 1024
    p = write_cog(tmp_path / "big.tif", np.ones(g.shape, "float32"), g, nodata=np.nan, tags={})
    with rasterio.open(p) as src:
        assert src.tags(ns="IMAGE_STRUCTURE")["LAYOUT"] == "COG"
        assert src.compression == Compression.deflate
        assert src.block_shapes[0] == (512, 512)
        assert src.overviews(1) != []


def test_nfr_3_writing_twice_is_byte_identical(tmp_path, small_grid):
    arr = np.random.default_rng(0).random((3, 4), dtype="float32")
    a = write_cog(tmp_path / "x.tif", arr, small_grid, nodata=np.nan, tags={"K": "v"})
    b = write_cog(tmp_path / "y.tif", arr, small_grid, nodata=np.nan, tags={"K": "v"})
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_read_raster_rejects_misaligned(tmp_path, small_grid):
    p = write_cog(
        tmp_path / "a.tif", np.zeros((3, 4), "float32"), small_grid, nodata=np.nan, tags={}
    )
    other = Grid.from_bounds("EPSG:32646", (300030, 2900010, 300150, 2900100), res=30)
    with pytest.raises(GridMismatchError):
        read_raster(p, other)


def test_write_into_directory_with_spaces(tmp_path, small_grid):
    p = write_cog(
        tmp_path / "dir with space" / "x.tif",
        np.zeros((3, 4), "float32"),
        small_grid,
        nodata=np.nan,
        tags={},
    )
    assert read_raster(p, small_grid).shape == (3, 4)


def test_rejects_array_of_wrong_shape(tmp_path, small_grid):
    with pytest.raises(ValueError):
        write_cog(
            tmp_path / "a.tif", np.zeros((4, 4), "float32"), small_grid, nodata=np.nan, tags={}
        )
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/store/test_cog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daiff.store'`.

- [x] **Step 3: Implement `src/daiff/store/cog.py`**

Write the array into a `rasterio.io.MemoryFile` GTiff (tags via `update_tags`, band names via
`set_band_description`), then `rasterio.shutil.copy(mem, path, driver="COG", COMPRESS="DEFLATE",
PREDICTOR="YES", BLOCKSIZE="512", OVERVIEWS="AUTO", RESAMPLING=<"NEAREST" for integer dtypes,
"AVERAGE" for floats>, NUM_THREADS="1")`. `store/__init__.py` re-exports the public names of the
store modules (extend it in later tasks).

- [x] **Step 4: Run the tests and lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
Expected: all pass. If the band-name test fails because COG CreateCopy drops descriptions, store the
names as a tag `DAIFF_BAND_NAMES` (JSON list) and read them from there in `read_band_names`.

- [x] **Step 5: Close the task** — tick, STATUS, `git commit -m "feat(store): deterministic COG writer and grid-checked reader"`, push.

---

### Task 5: Provenance, run store and NFR-4 metadata check

**Files:**
- Create: `src/daiff/store/provenance.py`, `src/daiff/store/run_store.py`, `src/daiff/store/check.py`
- Modify: `src/daiff/store/__init__.py` (re-exports), `tests/conftest.py` (`make_good_run`)
- Test: `tests/store/test_provenance.py`, `tests/store/test_run_store.py`, `tests/store/test_check.py`

**Interfaces:**
- Consumes: `write_cog`, `read_tags` (Task 4).
- Produces:
  - `sha256_file(path: Path) -> str` (64 hex, streamed in 1 MiB chunks)
  - `code_commit(repo_dir: Path) -> str` — `git rev-parse HEAD`, plus `-dirty` if `git status --porcelain` is non-empty; `"unknown"` when git is missing or the directory is not a repo.
  - `compute_run_id(config_hash: str, commit: str, input_checksums: Sequence[str]) -> str` — 12 hex chars; input order does not matter.
  - `REQUIRED_TAGS: tuple[str, ...]` = the 8 provenance keys (Global Constraints).
  - `build_tags(*, run_id: str, config_hash: str, code_commit: str, model_id: str, inputs: Sequence[Path], data_root: Path, data_versions: Mapping[str, str], year: int | None, t0: int) -> dict[str, str]`
    — `DAIFF_INPUTS` is canonical JSON `[{"path": <POSIX path relative to data_root>, "sha256": …}]` sorted by path;
    `DAIFF_DATA_VERSIONS` is canonical JSON; `DAIFF_YEAR` is `"n/a"` when `year is None`.
  - `class RunStore(data_root: Path, run_id: str)` with `run_dir = data_root / "store" / run_id` and path methods:
    `forest(year)`, `loss(t0, year)`, `coupling(year)`, `susceptibility(year)`, `riskclass(year)`,
    `delta_s(year)`, `subbasin_csv(year)`, `run_metadata`, `forest10m(year)`, `loss10m(t0, year)`,
    `regrowth(t0, year)`, `cn(year)`, `static_features`, `preview(year)`, `subbasins_geojson`,
    `metrics_dir`, `model_id_file`.
  - `RUN_METADATA_KEYS = ("run_id", "config", "config_hash", "code_commit", "data_versions", "inputs", "timings")`
  - `write_run_metadata(store: RunStore, payload: Mapping[str, object]) -> Path` — JSON, `sort_keys=True`, `indent=2`.
  - `publish(data_root: Path, run_id: str) -> None` — writes `data_root/store/CURRENT`; raises `FileNotFoundError` if the run dir is missing.
  - `current_run(data_root: Path) -> str | None`
  - `@dataclass(frozen=True) class MetadataProblem: path: Path; problem: str`
  - `check_metadata(run_dir: Path) -> list[MetadataProblem]` — every `*.tif` must carry every `REQUIRED_TAGS` key with a non-empty value; `run_metadata.json` must exist and contain every `RUN_METADATA_KEYS` key.

- [x] **Step 1: Write the failing tests**

`tests/store/test_provenance.py`:
```python
import json
import re
import subprocess

from daiff.store.provenance import (
    REQUIRED_TAGS,
    build_tags,
    code_commit,
    compute_run_id,
    sha256_file,
)


def test_compute_run_id_is_deterministic_order_free_and_12_hex():
    a = compute_run_id("c" * 64, "abc", ["h1", "h2"])
    assert a == compute_run_id("c" * 64, "abc", ["h2", "h1"])
    assert re.fullmatch(r"[0-9a-f]{12}", a)
    assert a != compute_run_id("c" * 64, "abd", ["h1", "h2"])


def test_build_tags_is_portable_and_timestamp_free(tmp_path):
    f = tmp_path / "raw" / "dem.tif"
    f.parent.mkdir()
    f.write_bytes(b"x")
    tags = build_tags(
        run_id="r" * 12,
        config_hash="c" * 64,
        code_commit="abc",
        model_id="n/a",
        inputs=[f],
        data_root=tmp_path,
        data_versions={"synthetic": "seed=42"},
        year=None,
        t0=2019,
    )
    assert set(REQUIRED_TAGS) <= tags.keys()
    assert json.loads(tags["DAIFF_INPUTS"]) == [{"path": "raw/dem.tif", "sha256": sha256_file(f)}]
    assert tags["DAIFF_YEAR"] == "n/a" and tags["DAIFF_T0"] == "2019"
    assert not any(re.search(r"\d{4}-\d{2}-\d{2}T\d{2}", v) for v in tags.values())


def test_code_commit_reports_clean_dirty_and_unknown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (repo / "f.txt").write_text("1")
    subprocess.run([*git, "add", "f.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
    clean = code_commit(repo)
    assert re.fullmatch(r"[0-9a-f]{40}", clean)
    (repo / "f.txt").write_text("2")
    assert code_commit(repo) == clean + "-dirty"
    assert code_commit(tmp_path / "not_a_repo") == "unknown"
```

`tests/store/test_run_store.py`:
```python
import pytest

from daiff.store.run_store import RunStore, current_run, publish


def test_appendix_c_file_names(tmp_path):
    s = RunStore(tmp_path, "abc123def456")
    d = tmp_path / "store" / "abc123def456"
    assert s.run_dir == d
    assert s.forest(2021) == d / "forest_2021.tif"
    assert s.loss(2019, 2021) == d / "loss_2019_2021.tif"
    assert s.coupling(2021) == d / "coupling_2021.tif"
    assert s.susceptibility(2021) == d / "susceptibility_2021.tif"
    assert s.riskclass(2021) == d / "riskclass_2021.tif"
    assert s.delta_s(2021) == d / "delta_s_2021.tif"
    assert s.subbasin_csv(2021) == d / "subbasin_2021.csv"
    assert s.run_metadata == d / "run_metadata.json"
    assert s.forest10m(2021) == d / "forest10m_2021.tif"
    assert s.loss10m(2019, 2021) == d / "loss10m_2019_2021.tif"
    assert s.regrowth(2019, 2021) == d / "regrowth_2019_2021.tif"
    assert s.cn(2021) == d / "cn_2021.tif"
    assert s.static_features == d / "static_features.tif"
    assert s.preview(2021) == d / "preview_2021.tif"
    assert s.subbasins_geojson == d / "subbasins.geojson"
    assert s.metrics_dir == d / "metrics"
    assert s.model_id_file == d / "model_id.txt"


def test_publish_and_current_run(tmp_path):
    assert current_run(tmp_path) is None
    with pytest.raises(FileNotFoundError):
        publish(tmp_path, "missing")
    RunStore(tmp_path, "abc").run_dir.mkdir(parents=True)
    publish(tmp_path, "abc")
    assert (tmp_path / "store" / "CURRENT").read_text().strip() == "abc"
    assert current_run(tmp_path) == "abc"
```

Add a plain helper to `tests/conftest.py` (Task 8 reuses it):
`make_good_run(data_root: Path, grid: Grid, drop_tag: str | None = None, drop_key: str | None = None) -> RunStore`.
It uses run_id `"abc123def456"` and writes `forest_2020.tif` (zeros, float32) with
`build_tags(run_id="abc123def456", config_hash="c" * 64, code_commit="deadbeef", model_id="n/a",
inputs=[], data_root=data_root, data_versions={"synthetic": "seed=42"}, year=2020, t0=2019)` minus
`drop_tag`. It also writes `run_metadata.json` with every `RUN_METADATA_KEYS` key (simple placeholder
values) minus `drop_key`.

`tests/store/test_check.py`:
```python
from daiff.store.check import check_metadata
from tests.conftest import make_good_run


def test_nfr_4_check_passes_on_complete_run(tmp_path, small_grid):
    assert check_metadata(make_good_run(tmp_path, small_grid).run_dir) == []


def test_nfr_4_flags_missing_tag(tmp_path, small_grid):
    problems = check_metadata(
        make_good_run(tmp_path, small_grid, drop_tag="DAIFF_CODE_COMMIT").run_dir
    )
    assert len(problems) == 1
    assert problems[0].path.name == "forest_2020.tif" and "DAIFF_CODE_COMMIT" in problems[0].problem


def test_nfr_4_flags_missing_run_metadata_key(tmp_path, small_grid):
    problems = check_metadata(make_good_run(tmp_path, small_grid, drop_key="timings").run_dir)
    assert [p.path.name for p in problems] == ["run_metadata.json"]
    assert "timings" in problems[0].problem


def test_nfr_4_flags_missing_run_metadata_file(tmp_path, small_grid):
    store = make_good_run(tmp_path, small_grid)
    store.run_metadata.unlink()
    assert [p.path.name for p in check_metadata(store.run_dir)] == ["run_metadata.json"]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/store -v`
Expected: the new tests FAIL with import errors; the Task 4 tests still pass.

- [x] **Step 3: Implement `provenance.py`, `run_store.py`, `check.py`** with the interfaces above
(`subprocess.run(..., capture_output=True, text=True)` for git; treat `FileNotFoundError` and non-zero
exit as `"unknown"`). Extend `store/__init__.py` re-exports.

- [x] **Step 4: Run the tests and lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [x] **Step 5: Close the task** — tick, STATUS, `git commit -m "feat(store): provenance tags, run store and NFR-4 metadata check"`, push.

---

### Task 6: Fingerprinted stage-DAG runner

**Files:**
- Create: `src/daiff/pipeline/__init__.py`, `src/daiff/pipeline/runner.py`
- Test: `tests/pipeline/__init__.py`, `tests/pipeline/test_runner.py`

**Interfaces:**
- Consumes: `DaiffConfig`, `section_hash` (Task 2); `sha256_file` (Task 5).
- Produces:
  - `@dataclass(frozen=True) class StageContext: cfg: DaiffConfig; data_root: Path; years: tuple[int, ...]`
  - `@dataclass(frozen=True) class Stage: name: str; run: Callable[[StageContext], None]; inputs: Callable[[StageContext], list[Path]]; outputs: Callable[[StageContext], list[Path]]; config_sections: tuple[str, ...] = (); deps: tuple[str, ...] = (); version: str = "1"`
  - `@dataclass(frozen=True) class StageResult: name: str; status: Literal["ran", "skipped"]; seconds: float`
  - `class PipelineError(RuntimeError)`
  - `fingerprint(stage: Stage, ctx: StageContext) -> str` — SHA-256 over `stage.version`, the `section_hash` of each config section, and `(relative path, sha256)` for each input. A missing input raises `PipelineError` naming the path.
  - `class Runner(stages: Sequence[Stage], state_dir: Path)` with
    `order() -> list[str]` (topological; ties broken by declaration order; raises `PipelineError` on a cycle or unknown dep) and
    `run(ctx: StageContext, *, only: Collection[str] | None = None, force: bool = False) -> list[StageResult]`.
    A stage is skipped when its stored fingerprint matches **and** all outputs exist. State goes in
    `state_dir/<name>.json` (`{"fingerprint": …, "outputs": […]}`) **only after** the stage returns.
    A stage exception is re-raised as `PipelineError(f"stage '{name}' failed")` from the original.

- [x] **Step 1: Write the failing tests** — `tests/pipeline/test_runner.py`

```python
from dataclasses import replace

import pytest

from daiff.pipeline import PipelineError, Runner, Stage, StageContext


@pytest.fixture
def ctx(synthetic_cfg, tmp_path):
    return StageContext(cfg=synthetic_cfg, data_root=tmp_path, years=(2019, 2020))


def copy_stage(name, src, dst, calls, deps=(), version="1", boom=None):
    def run(_ctx):
        calls.append(name)
        if boom and boom["on"]:
            raise RuntimeError("boom")
        dst.write_text(src.read_text() + name)

    return Stage(
        name=name,
        run=run,
        inputs=lambda _c: [src],
        outputs=lambda _c: [dst],
        config_sections=("runtime",),
        deps=deps,
        version=version,
    )


@pytest.fixture
def chain(tmp_path):
    a_in = tmp_path / "a_in.txt"
    a_in.write_text("x")
    calls: list[str] = []
    a = copy_stage("a", a_in, tmp_path / "a.txt", calls)
    b = copy_stage("b", tmp_path / "a.txt", tmp_path / "b.txt", calls, deps=("a",))
    return a_in, calls, a, b


def test_runs_in_dependency_order(ctx, tmp_path, chain):
    _, calls, a, b = chain
    results = Runner([b, a], tmp_path / "state").run(ctx)
    assert calls == ["a", "b"] and [r.status for r in results] == ["ran", "ran"]


def test_cycle_and_unknown_dependency_raise(tmp_path, chain):
    _, calls, a, b = chain
    with pytest.raises(PipelineError):
        Runner([replace(a, deps=("b",)), b], tmp_path / "s").order()
    with pytest.raises(PipelineError):
        Runner([replace(a, deps=("zzz",))], tmp_path / "s").order()


def test_skips_when_unchanged(ctx, tmp_path, chain):
    _, calls, a, b = chain
    r = Runner([a, b], tmp_path / "state")
    r.run(ctx)
    assert [x.status for x in r.run(ctx)] == ["skipped", "skipped"] and calls == ["a", "b"]


def test_reruns_on_changed_input_missing_output_or_new_version(ctx, tmp_path, chain):
    a_in, calls, a, b = chain
    state = tmp_path / "state"
    Runner([a, b], state).run(ctx)
    a_in.write_text("y")
    Runner([a, b], state).run(ctx)
    assert calls == ["a", "b", "a", "b"]
    (tmp_path / "b.txt").unlink()
    Runner([a, b], state).run(ctx)
    assert calls[-1] == "b" and len(calls) == 5
    Runner([replace(a, version="2"), b], state).run(ctx)
    assert calls[-1] == "a" and len(calls) == 6  # b's input bytes are unchanged, so b is skipped


def test_force_and_only(ctx, tmp_path, chain):
    _, calls, a, b = chain
    r = Runner([a, b], tmp_path / "state")
    r.run(ctx)
    r.run(ctx, force=True)
    assert calls == ["a", "b", "a", "b"]
    r.run(ctx, only={"b"}, force=True)
    assert calls[-1] == "b" and len(calls) == 5


def test_failed_stage_leaves_no_state_and_reruns(ctx, tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("x")
    calls: list[str] = []
    boom = {"on": True}
    s = copy_stage("a", src, tmp_path / "out.txt", calls, boom=boom)
    with pytest.raises(PipelineError):
        Runner([s], tmp_path / "state").run(ctx)
    assert not (tmp_path / "state" / "a.json").exists()
    boom["on"] = False
    assert [x.status for x in Runner([s], tmp_path / "state").run(ctx)] == ["ran"]


def test_missing_input_is_a_pipeline_error(ctx, tmp_path):
    s = copy_stage("a", tmp_path / "absent.txt", tmp_path / "o.txt", [])
    with pytest.raises(PipelineError, match="absent.txt"):
        Runner([s], tmp_path / "state").run(ctx)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/pipeline -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daiff.pipeline'`.

- [x] **Step 3: Implement `src/daiff/pipeline/runner.py`** with the interfaces above, and re-export
them from `pipeline/__init__.py`. Input paths in the fingerprint are relative to `ctx.data_root` when
possible (POSIX form), so fingerprints are portable between machines. Time each stage with
`time.perf_counter()`.

- [x] **Step 4: Run the tests and lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [x] **Step 5: Close the task** — tick, STATUS, `git commit -m "feat(pipeline): fingerprinted stage DAG runner"`, push.

---

### Task 7: Raw-input layout and synthetic basin

**Files:**
- Create: `src/daiff/store/raw_layout.py`, `src/daiff/synthetic.py`
- Modify: `src/daiff/store/__init__.py` (re-export `RawLayout`)
- Test: `tests/integration/__init__.py`, `tests/integration/test_synthetic.py`

**Interfaces:**
- Consumes: `DaiffConfig`, `Grid`, `write_cog`, `check_alignment`.
- Produces:
  - `class RawLayout(data_root: Path)` with `root = data_root / "raw"` and paths:
    `grid_json` (`raw/grid.json`), `dem` (`raw/dem.tif`, float32 m), `hsg` (`raw/hsg.tif`, uint8 1–4 = A–D, 255 nodata),
    `jrc_occurrence` (`raw/jrc_occurrence.tif`, uint8 0–100), `forest10m(year)` (`raw/forest10m/forest10m_<year>.tif`, uint8 0/1/255 on the 10 m nested grid),
    `dw_class(year)` (`raw/dw_class/dw_class_<year>.tif`, uint8 Dynamic World labels 0–8),
    `chirps_daily_csv` (`raw/rainfall/chirps_subbasin_daily.csv`, columns `date,subbasin_id,precip_mm`),
    `subbasins` (`raw/subbasins.geojson`, RFC 7946 EPSG:4326, properties `subbasin_id: int`, `name: str`);
    plus `layers_30m(years: Sequence[int]) -> list[Path]` (dem, hsg, jrc_occurrence, dw_class per year),
    `layers_10m(years) -> list[Path]` (forest10m per year), `write_grid(grid: Grid) -> Path`, `read_grid() -> Grid`.
    P3's GEE stage must write exactly this layout.
  - `make_basin(cfg: DaiffConfig) -> RawLayout` — requires `cfg.synthetic`, otherwise `ValueError`.
    Deterministic for a given `cfg.runtime.seed`. Raw rasters carry tags `{"DAIFF_SOURCE": "synthetic", "DAIFF_SEED": str(seed)}`.

- [x] **Step 1: Write the failing tests** — `tests/integration/test_synthetic.py`

```python
import hashlib
from datetime import date

import numpy as np
import pandas as pd
import pytest

from daiff.grid import Grid, check_alignment
from daiff.store.cog import read_raster
from daiff.synthetic import make_basin


@pytest.fixture(scope="module")
def basin(tmp_path_factory):
    from daiff.config import load_config
    from tests.conftest import SYN_CONFIG

    root = tmp_path_factory.mktemp("syn")
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(root)})
    return cfg, make_basin(cfg)


def test_writes_every_raw_layer(basin):
    cfg, raw = basin
    years = cfg.years.years
    for p in [
        raw.grid_json,
        raw.chirps_daily_csv,
        raw.subbasins,
        *raw.layers_30m(years),
        *raw.layers_10m(years),
    ]:
        assert p.exists(), p


def test_fr_d5_synthetic_layers_are_aligned(basin):
    cfg, raw = basin
    grid = raw.read_grid()
    assert grid == Grid.from_config(cfg)
    assert check_alignment(raw.layers_30m(cfg.years.years), grid).ok
    assert check_alignment(raw.layers_10m(cfg.years.years), grid.nested(3)).ok


def test_is_deterministic_for_a_seed(basin, tmp_path):
    from daiff.config import load_config
    from tests.conftest import SYN_CONFIG

    cfg, raw = basin
    raw2 = make_basin(load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)}))
    for a, b in zip(raw.layers_30m(cfg.years.years), raw2.layers_30m(cfg.years.years), strict=True):
        assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_forest_declines_after_t0(basin):
    cfg, raw = basin
    fine = raw.read_grid().nested(3)

    def share(year):
        a = read_raster(raw.forest10m(year), fine)
        return a[a != 255].mean()

    assert share(cfg.years.years[-1]) <= share(cfg.years.t0) - 0.02


def test_dem_drains_to_south_outlet(basin):
    _, raw = basin
    dem = read_raster(raw.dem, raw.read_grid())
    n = dem.shape[1]
    assert dem[-1, n // 2] == dem.min()


def test_rainfall_is_gap_free_from_2000(basin):
    cfg, raw = basin
    df = pd.read_csv(raw.chirps_daily_csv, parse_dates=["date"])
    end = date(cfg.years.years[-1], 3, 31)
    expected_days = (end - date(2000, 1, 1)).days + 1
    assert df["date"].min().date() == date(2000, 1, 1) and df["date"].max().date() == end
    assert (df.groupby("subbasin_id").size() == expected_days).all()
    assert df["subbasin_id"].nunique() == cfg.synthetic.subbasin_split**2
    assert (df["precip_mm"] >= 0).all() and np.isfinite(df["precip_mm"]).all()
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_synthetic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daiff.synthetic'`.

- [x] **Step 3: Implement `RawLayout`** in `src/daiff/store/raw_layout.py` (grid.json = `grid.to_dict()` plus `"nested_factor": 3`).

- [x] **Step 4: Implement `make_basin`** in `src/daiff/synthetic.py`. Use one `np.random.default_rng(seed)`
for everything. With N = `cfg.synthetic.size`, row r (north→south), col c, `x = c/(N−1) − 0.5`, `y = r/(N−1)`:
- **DEM**: `z = 400 − 250·y + 120·|x|^1.2 + noise(σ=0.5)`. Carve the channel column `c = N//2` down
  by 5 m and force it to strictly decrease southward, so `(N−1, N//2)` is the global minimum.
- **forest10m** (3N × 3N): forest = 1 except the channel corridor (|x| < 0.03 → 0) and the
  floodplain (y > 0.7 → 0). For the k-th year after t₀: clear k new 60 × 60 px patches (3.6 ha) at
  random positions with y < 0.6, plus three 4 × 4 px patches (0.16 ha, below the MMU). Clearing
  accumulates across years. In the third configured year, set one 30 × 30 px block to 255 (cloud gap).
- **dw_class** (30 m per year): channel cells → 0 (water); a cell with ≥ 5 forest pixels of 9 → 1
  (trees); other floodplain cells → 4 (crops); everything else → 2 (grass).
- **hsg**: `1 + ((r // (N//4)) + (c // (N//4))) % 4`; cells with |x| < 0.05 → 4 (D).
- **jrc_occurrence**: channel column → 95; |x| < 0.05 → 40; else 0.
- **subbasins**: split the grid into `subbasin_split²` rectangles. Ids are `1000 + i` (row-major),
  names `f"Synthetic sub-basin {i + 1}"`. Corners are transformed to EPSG:4326 with
  `rasterio.warp.transform_geom`.
- **rainfall**: daily 2000-01-01 → 31 Mar of the last configured year, per sub-basin. Wet
  probability 0.15 + 0.6·monsoon (monsoon = month in 6–9); amount ~ Gamma(shape 0.8, scale 12 + 25·monsoon)
  when wet, else 0, rounded to 0.1 mm.

- [x] **Step 5: Run the tests and lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
Expected: all pass, and the synthetic tests take under 30 s.

- [x] **Step 6: Close the task** — tick, STATUS, `git commit -m "feat(synthetic): raw-input layout and deterministic synthetic basin"`, push.

---

### Task 8: CLI — `synth`, `check-grid`, `check-metadata`

**Files:**
- Modify: `src/daiff/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `Grid`, `check_alignment`, `RawLayout`, `make_basin`, `current_run`,
  `RunStore`, `check_metadata`.
- Produces commands (each takes `-c/--config PATH`, required):
  - `daiff synth` — runs `make_basin`; prints `wrote synthetic raw inputs to <raw root>`; exit 0.
  - `daiff check-grid` — grid = `Grid.from_config(cfg)` if bounds are set, else `RawLayout.read_grid()`.
    Checks `layers_30m` against the grid and `layers_10m` against `grid.nested(3)`, over the existing
    files for the configured years. Prints `FR-D5 PASS: <n> layers aligned` (exit 0), or `FR-D5 FAIL`
    plus one line per problem `<field> <path> expected=<…> actual=<…>` (exit 1). With no raw layers:
    `FR-D5 FAIL: no raw layers found under <raw root>` (exit 1).
  - `daiff check-metadata [--run-id ID]` — defaults to `current_run(cfg.data_root)`. If there is
    none: `no published run under <data_root>/store — run the pipeline first` (exit 2). Prints
    `NFR-4 PASS: <run_id>` (exit 0) or `NFR-4 FAIL` plus one line per problem (exit 1).

- [x] **Step 1: Write the failing tests** (append to `tests/test_cli.py`)

```python
import numpy as np
from affine import Affine

from daiff.store.cog import write_cog
from tests.conftest import SYN_CONFIG

runner = CliRunner()


def _env(tmp_path):
    return {"DAIFF_DATA_ROOT": str(tmp_path)}


def test_fr_d5_synth_then_check_grid_passes(tmp_path):
    assert runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=_env(tmp_path)).exit_code == 0
    r = runner.invoke(app, ["check-grid", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 0 and "FR-D5 PASS" in r.stdout


def test_fr_d5_check_grid_fails_on_shifted_layer(tmp_path):
    runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    from daiff.config import load_config
    from daiff.grid import Grid
    from daiff.store.raw_layout import RawLayout

    cfg = load_config(SYN_CONFIG, env=_env(tmp_path))
    g = Grid.from_config(cfg)
    shifted = Grid(g.crs, g.transform @ Affine.translation(0.5, 0), g.width, g.height)
    write_cog(
        RawLayout(cfg.data_root).dem, np.zeros(g.shape, "float32"), shifted, nodata=np.nan, tags={}
    )
    r = runner.invoke(app, ["check-grid", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 1 and "FR-D5 FAIL" in r.stdout and "dem.tif" in r.stdout


def test_check_grid_without_raw_layers_fails_clearly(tmp_path):
    r = runner.invoke(app, ["check-grid", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 1 and "no raw layers found" in r.stdout


def test_check_metadata_without_published_run_exits_2(tmp_path):
    r = runner.invoke(app, ["check-metadata", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 2 and "no published run" in r.stdout
```

Add `test_nfr_4_check_metadata_passes_on_published_run(tmp_path, small_grid)`. It calls
`make_good_run(tmp_path / "synthetic", small_grid)` (from `tests/conftest.py`, Task 5) and then
`publish(tmp_path / "synthetic", "abc123def456")`, runs `check-metadata` with `_env(tmp_path)`, and
asserts exit 0 with `"NFR-4 PASS"` in stdout.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: the new tests FAIL with "No such command".

- [x] **Step 3: Implement the three commands** in `src/daiff/cli.py` with the behaviour and exact
messages above (`typer.echo`; `raise typer.Exit(code)`).

- [x] **Step 4: Run the full suite, lint, and try the CLI by hand**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .`
then `uv run daiff synth -c configs/synthetic.yaml && uv run daiff check-grid -c configs/synthetic.yaml`
Expected: all tests pass; the CLI prints `FR-D5 PASS: 15 layers aligned` (dem, hsg, jrc + 6 dw_class
at 30 m; 6 forest10m at 10 m), and data lands in `data/synthetic/raw/` (gitignored).

- [x] **Step 5: Close the task** — tick, STATUS, `git commit -m "feat(cli): synth, check-grid (FR-D5) and check-metadata (NFR-4)"`, push.

---

### Task 9: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a workflow named `ci` running on pushes to `main` and on pull requests, with jobs
  `python` and `secrets`. P1 adds the synthetic end-to-end and coverage gate; P2 adds a `web` job.

- [x] **Step 1: Write the workflow**

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --extra dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -m "not gee and not slow and not colab" --cov=daiff --cov-report=term-missing
  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [x] **Step 2: Validate the YAML locally**

Run: `uv run python -c "import yaml; d = yaml.safe_load(open('.github/workflows/ci.yml')); print(sorted(d['jobs']))"`
Expected: `['python', 'secrets']`

- [x] **Step 3: Close the task** — tick, STATUS, `git commit -m "ci: lint, tests with coverage, gitleaks"`, push.
Then run `gh run list --limit 1` once and write the outcome into STATUS under **CI** (don't wait, don't fix now — D-07).

---

### Task 10: Setup, traceability and licence docs; P0 close-out

**Files:**
- Create: `docs/setup/gee.md`, `docs/verification_matrix.md`, `docs/test_log.md`, `docs/LICENSES.md`, `docs/perf/README.md`
- Modify: `docs/STATUS.md`, `README.md`

**Interfaces:**
- Produces: documents that later phases update in place (verification matrix rows, test-log entries, perf logs).

- [x] **Step 1: Write `docs/setup/gee.md`** — numbered steps a teammate follows alone:
1. Sign in with a personal Google account at https://code.earthengine.google.com/register.
2. Choose **Use with a Cloud project → Unpaid usage → Academia & research**.
3. Create a new Cloud project (suggested ID `daiff-<yourname>`). No billing account is needed for
   non-commercial use. Google may ask you to confirm non-commercial eligibility; answer truthfully
   (student research project).
4. Wait until the project shows Earth Engine as enabled.
5. Locally: `uv sync --extra dev`, then **you run** `uv run earthengine authenticate`. A browser
   opens, you sign in, and the token is stored in your user profile, never in the repo.
6. Put `DAIFF_GEE_PROJECT=<project-id>` in `.env`.
7. Smoke test (PowerShell: replace `<project-id>`):
   `uv run python -c "import ee; ee.Initialize(project='<project-id>'); print(ee.Number(1).add(1).getInfo())"` → prints `2`.
8. Colab: `import ee; ee.Authenticate(); ee.Initialize(project="<project-id>")`.

Also cover:
- **Quotas:** non-commercial projects have a monthly compute quota, so keep exports small.
- **Sharing assets:** EE asset sharing lets teammates read your exports.
- **Troubleshooting:** `ee.Initialize` errors, "project not registered", and a wrong Google account
  in the browser.

- [x] **Step 2: Write `docs/verification_matrix.md`** — one row per requirement in
`docs/srs/requirements.md` (26 FR + 10 NFR), columns `Requirement | Tier | Method | Artifact | Phase | Status`.
Artifacts and phases come from spec §8 and §11. Status after P0:
- FR-D5 **partial**: `tests/test_grid.py`, `daiff check-grid`; Kopili layers pending P3.
- NFR-3 **partial**: byte-identical COG test; end-to-end run comes in P1.
- NFR-4 **partial**: `daiff check-metadata`.
- NFR-9 **partial**: CI exists; coupling tests come in P1.
- NFR-10 **partial**: gitleaks in CI.
- Everything else: **not started**.

- [x] **Step 3: Write `docs/test_log.md`**
- Explain the rule: acceptance entries use Kopili data, frozen test sets and a recorded run_id + commit (SRS 8.3).
- Table columns: `Date | Requirement | Method | Config / run_id / commit | Result | Evidence | By`.
- One first row: a dev check of FR-D5 on the synthetic basin (PASS), marked "dev check — not acceptance".

- [x] **Step 4: Write `docs/LICENSES.md` and `docs/perf/README.md`**
- **`LICENSES.md`**: the data-source table from spec §7, plus a library table (numpy BSD-3, pandas
  BSD-3, rasterio BSD-3 with bundled GDAL MIT, pydantic MIT, PyYAML MIT, typer MIT, python-dotenv
  BSD-3, pytest MIT, pytest-cov MIT, ruff MIT), and "Project code licence: pending team decision
  (proposal MIT)".
- **`perf/README.md`**: the NFR-1/NFR-2 log format — `machine | cores | RAM | workers | stage | seconds | run_id | commit`.

- [x] **Step 5: Update `docs/STATUS.md` for P0 completion**
- Phase table: P0 **done** (with a link to this plan); "Now" set to P1.
- Next task: "Write the P1 science-core plan (`docs/superpowers/plans/<date>-p1-science-core.md`) from spec §6.7–6.12 and §11, then execute it".
- Add a session-log row.
- Add a README line pointing to `docs/setup/gee.md`.

- [x] **Step 6: Final verification**

Run: `uv run pytest -m "not gee and not slow and not colab" -v && uv run ruff check . && uv run ruff format --check .`
Expected: everything passes.

- [x] **Step 7: Commit and push**

```bash
git add docs README.md
git commit -m "docs: GEE setup guide, verification matrix, test log, licences; close P0"
git push origin main
```
