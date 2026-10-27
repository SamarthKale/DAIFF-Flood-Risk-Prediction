"""Training chips for the U-Net challenger (D-14): 256x256 px, 10 m, 12 bands + auto-label.

Runs inside the Colab notebook (Earth Engine login there). Chips are fetched with computePixels
around random centres, so cost scales with the number of chips, not with the basin.
"""

from __future__ import annotations

import numpy as np

from daiff.gee.forest_rf import FEATURES, label_image
from daiff.gee.s2 import composite

CHIP_PX = 256
RES_M = 10


def chip_request(x: float, y: float, crs: str, px: int = CHIP_PX) -> dict:
    """computePixels grid block for a px x px window centred on (x, y)."""
    return {
        "dimensions": {"width": px, "height": px},
        "affineTransform": {
            "scaleX": RES_M,
            "shearX": 0,
            "translateX": x - px * RES_M / 2,
            "shearY": 0,
            "scaleY": -RES_M,
            "translateY": y + px * RES_M / 2,
        },
        "crsCode": crs,
    }


def training_image(ee, aoi, year: int, hansen_id: str):
    """12 composite features + `label` (1 forest, 0 non-forest, 255 ambiguous)."""
    img = composite(ee, aoi, year).select(list(FEATURES))
    # Ambiguous, cloud-masked and out-of-basin pixels all read 255 (ignored in the loss).
    lab = label_image(ee, year, hansen_id).updateMask(img.select("B2").mask()).clip(aoi)
    return img.toFloat().addBands(lab.unmask(255).toFloat())


def to_chw(arr: np.ndarray, bands: tuple[str, ...]) -> np.ndarray:
    """Structured computePixels array -> float32 (bands, H, W); masked pixels become 0."""
    out = np.stack([arr[b] for b in bands]).astype(np.float32)
    return np.nan_to_num(out, nan=0.0)


def keep_chip(label: np.ndarray, min_frac: float = 0.02) -> bool:
    """A chip is useful for training when enough pixels carry a confident auto-label."""
    return float((label != 255).mean()) >= min_frac


def fetch_chip(ee, image, x: float, y: float, crs: str, bands: tuple[str, ...], px: int = CHIP_PX):
    arr = ee.data.computePixels(
        {"expression": image, "fileFormat": "NUMPY_NDARRAY", "grid": chip_request(x, y, crs, px)}
    )
    return to_chw(arr, bands)
