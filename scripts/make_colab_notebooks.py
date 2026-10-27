"""Write notebooks/colab/unet_train.ipynb and unet_infer.ipynb (run: python scripts/make_colab_notebooks.py)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notebooks" / "colab"

SETUP = """\
# 1. Install the project and sign in. Free GPU: Runtime > Change runtime type > T4 GPU.
!git clone -q https://github.com/SamarthKale/DAIFF-Flood-Risk-Prediction.git daiff
%cd daiff
!pip install -q --no-deps -e .
!pip install -q pydantic pyyaml earthengine-api rasterio pandas
import os, numpy as np, ee
PROJECT = "YOUR-EARTH-ENGINE-PROJECT-ID"   # <- your Earth Engine project id (same one as in .env)
ee.Authenticate()                           # opens a Google sign-in; use the account that owns PROJECT
ee.Initialize(project=PROJECT)
from google.colab import drive
drive.mount("/content/drive")
DRIVE = "/content/drive/MyDrive/DAIFF"
for sub in ("chips", "unet", "unet_out"):
    os.makedirs(f"{DRIVE}/{sub}", exist_ok=True)
from daiff.config import load_config
from daiff.gee.ingest import make_ctx
cfg = load_config("configs/kopili.yaml", env={"DAIFF_GEE_PROJECT": PROJECT})
ctx = make_ctx(ee, cfg)
"""

CHIPS = """\
# 2. Fetch training chips (256x256 px at 10 m, 12 bands + auto-label) around random points.
# Cost: about N_PER_YEAR small computePixels calls per year. Start with N_PER_YEAR = 20 to measure quota.
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from rasterio.warp import transform
from daiff.gee import refdata
from daiff.gee.chips import CHIP_PX, fetch_chip, keep_chip, training_image
from daiff.gee.forest_rf import FEATURES

N_PER_YEAR = 150
YEARS = list(range(2018, 2027))
BANDS = tuple(FEATURES) + ("label",)
ref = pd.read_csv("reference/forest_sample_points_kopili.csv")   # chips must stay away from these points
ref_xy = ref[["x", "y"]].to_numpy()

def centres(year):
    pts = ee.FeatureCollection.randomPoints(ctx.aoi, N_PER_YEAR * 3, 7000 + year).getInfo()["features"]
    lon = [f["geometry"]["coordinates"][0] for f in pts]
    lat = [f["geometry"]["coordinates"][1] for f in pts]
    xs, ys = transform("EPSG:4326", ctx.grid.crs, lon, lat)
    xy = np.column_stack([xs, ys])
    d = np.sqrt(((xy[:, None, :] - ref_xy[None, :, :]) ** 2).sum(-1)).min(1)
    return xy[d > 1.5 * CHIP_PX * 10]            # 1.5 chip-widths away from every reference point

for year in YEARS:
    out = f"{DRIVE}/chips/chips_{year}.npz"
    if os.path.exists(out):
        continue
    img = training_image(ee, ctx.aoi, year, refdata.DATASETS["hansen"])
    def get(xy):
        try:
            return fetch_chip(ee, img, xy[0], xy[1], ctx.grid.crs, BANDS)
        except Exception as exc:
            print("chip failed:", exc)
            return None
    with ThreadPoolExecutor(8) as pool:
        got = pool.map(get, centres(year)[: N_PER_YEAR * 2])
        chips = [c for c in got if c is not None and keep_chip(c[-1])]
    chips = chips[:N_PER_YEAR]
    np.savez_compressed(out, x=np.stack([c[:-1] for c in chips]).astype(np.float16),
                        y=np.stack([c[-1] for c in chips]).astype(np.uint8))
    print(year, len(chips), "chips saved")
"""

TRAIN = """\
# 3. Train. A checkpoint goes to Drive every epoch, so after a disconnect just re-run this cell to resume.
import glob, torch
from torch import nn
from daiff.forest.unet import UNet, count_params
dev = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", dev, "(switch the runtime to a T4 GPU if this says cpu)")
X, Y = [], []
for f in sorted(glob.glob(DRIVE + "/chips/chips_*.npz")):
    d = np.load(f)
    X.append(d["x"])
    Y.append(d["y"])
X = np.concatenate(X)
Y = np.concatenate(Y)
rng = np.random.default_rng(42)
idx = rng.permutation(len(X))
cut = int(0.8 * len(X))
tr, va = idx[:cut], idx[cut:]
model = UNet(in_bands=12, n_classes=2).to(dev)
print("params:", count_params(model), "chips:", len(X))
opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
loss_fn = nn.CrossEntropyLoss(ignore_index=255)
CKPT = DRIVE + "/unet/ckpt.pt"
start = 0
if os.path.exists(CKPT):
    st = torch.load(CKPT, map_location=dev)
    model.load_state_dict(st["model"])
    opt.load_state_dict(st["opt"])
    start = st["epoch"] + 1

def batch(ids, aug):
    x = torch.from_numpy(X[ids].astype(np.float32))
    y = torch.from_numpy(Y[ids].astype(np.int64))
    if aug:
        k = int(rng.integers(4))
        x, y = torch.rot90(x, k, (2, 3)), torch.rot90(y, k, (1, 2))
        if rng.random() < 0.5:
            x, y = x.flip(3), y.flip(2)
    return x.to(dev), y.to(dev)

EPOCHS, BS = 40, 8
for ep in range(start, EPOCHS):
    model.train()
    order = rng.permutation(tr)
    tot = 0.0
    for i in range(0, len(order), BS):
        x, y = batch(order[i:i + BS], True)
        opt.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()
        opt.step()
        tot += float(loss)
    model.eval()
    tp = fp = fn = 0
    with torch.no_grad():
        for i in range(0, len(va), BS):
            x, y = batch(va[i:i + BS], False)
            p = model(x).argmax(1)
            m = y != 255
            tp += int(((p == 1) & (y == 1) & m).sum())
            fp += int(((p == 1) & (y == 0) & m).sum())
            fn += int(((p == 0) & (y == 1) & m).sum())
    f1 = 2 * tp / max(1, 2 * tp + fp + fn)
    print(f"epoch {ep:2d} loss {tot / max(1, len(order) // BS):.4f} val forest-F1 (auto-labels) {f1:.3f}")
    torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "epoch": ep}, CKPT)
print("done. checkpoint:", CKPT)
"""

INFER_PARAMS = """\
# 2. What to predict. Do the reference points first (cheap), then the full maps only if the U-Net looks good.
import torch, pandas as pd
from daiff.forest.unet import UNet
from daiff.gee import refdata
from daiff.gee.chips import fetch_chip, training_image
from daiff.gee.forest_rf import FEATURES
YEARS = [2018, 2026]            # t0 and the latest season; add more years if the quota allows
dev = "cuda" if torch.cuda.is_available() else "cpu"
model = UNet(12, 2).to(dev)
model.load_state_dict(torch.load(DRIVE + "/unet/ckpt.pt", map_location=dev)["model"])
model.eval()
BANDS = tuple(FEATURES)

def prob_forest(chw):
    with torch.no_grad():
        return torch.softmax(model(torch.from_numpy(chw)[None].to(dev)), 1)[0, 1].cpu().numpy()
"""

INFER_POINTS = """\
# 3. Reference points: p(forest) at each labelling point for each year -> unet_points.csv.
from concurrent.futures import ThreadPoolExecutor
ref = pd.read_csv("reference/forest_sample_points_kopili.csv")
rows = []
for year in YEARS:
    img = training_image(ee, ctx.aoi, year, refdata.DATASETS["hansen"]).select(list(BANDS))
    def one(r):
        try:
            p = prob_forest(fetch_chip(ee, img, r.x, r.y, ctx.grid.crs, BANDS, px=64))
            return (r.point_id, year, float(p[32, 32]))
        except Exception as exc:
            print("point failed", r.point_id, exc)
            return None
    with ThreadPoolExecutor(8) as pool:
        rows += [x for x in pool.map(one, ref.itertuples()) if x]
pd.DataFrame(rows, columns=["point_id", "year", "p_forest"]).to_csv(DRIVE + "/unet_out/unet_points.csv", index=False)
print(len(rows), "predictions written to", DRIVE + "/unet_out/unet_points.csv")
"""

INFER_MAPS = """\
# 4. (Optional, heavy) full-basin class maps, one GeoTIFF per year on the 10 m grid.
# Test first with a small window: WINDOW = (row0, row1, col0, col1) in 10 m pixels, e.g. (8000, 8512, 10000, 10512).
import rasterio
from rasterio.windows import Window
WINDOW = None            # None = whole basin (about 1,400 tiles per year: run only if the points look good)
TILE, HALO = 512, 32
g10 = ctx.fine
H, W = g10.shape
r0, r1, c0, c1 = WINDOW or (0, H, 0, W)
for year in YEARS:
    path = f"/content/forest10m_{year}.tif"
    img = training_image(ee, ctx.aoi, year, refdata.DATASETS["hansen"]).select(list(BANDS))
    prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="uint8", crs=g10.crs,
                transform=g10.transform, nodata=255, tiled=True, blockxsize=512, blockysize=512,
                compress="deflate")
    with rasterio.open(path, "w", **prof) as dst:
        for r in range(r0, r1, TILE):
            for c in range(c0, c1, TILE):
                h, w = min(TILE, H - r), min(TILE, W - c)
                x = g10.transform.c + (c + TILE / 2) * 10
                y = g10.transform.f - (r + TILE / 2) * 10
                try:
                    p = prob_forest(fetch_chip(ee, img, x, y, g10.crs, BANDS, px=TILE + 2 * HALO))
                except Exception as exc:
                    print("tile failed", r, c, exc)
                    continue
                cls = np.where(p[HALO:HALO + TILE, HALO:HALO + TILE] >= 0.5, 1, 0).astype("uint8")
                dst.write(cls[:h, :w], 1, window=Window(c, r, w, h))
    !cp {path} {DRIVE}/unet_out/
    print(year, "done")
# Then download My Drive/DAIFF/unet_out to the laptop and run:
#   uv run daiff forest import-unet -c configs/kopili.yaml --dir <that folder>
"""


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train = notebook(
        [
            md(
                "# DAIFF U-Net forest challenger: training\n\nRun the cells top to bottom in "
                "Chrome (Colab). Needs a free T4 GPU runtime; **GPU work only ever runs here, never "
                "on the laptop**. Chips and checkpoints are saved to `My Drive/DAIFF/` so a "
                "disconnect only costs the current epoch. Earth Engine quota: start with "
                "`N_PER_YEAR = 20` and check usage before raising it.\n"
            ),
            code(SETUP),
            code(CHIPS),
            code(TRAIN),
        ]
    )
    infer = notebook(
        [
            md(
                "# DAIFF U-Net forest challenger: inference\n\nRun after `unet_train` has saved "
                "`DAIFF/unet/ckpt.pt`. Step 3 writes `unet_points.csv` (used to compare the U-Net "
                "with the Random Forest on the labelled reference sample); step 4 optionally "
                "writes full 10 m maps.\n"
            ),
            code(SETUP),
            code(INFER_PARAMS),
            code(INFER_POINTS),
            code(INFER_MAPS),
        ]
    )
    for name, nb in (("unet_train", train), ("unet_infer", infer)):
        (OUT / f"{name}.ipynb").write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
