import numpy as np

from daiff.gee.chips import CHIP_PX, chip_request, keep_chip, to_chw
from daiff.grid import Grid


def test_fr_f1_chip_request_is_centred_and_10m():
    r = chip_request(500000.0, 2900000.0, "EPSG:32646")
    a = r["affineTransform"]
    assert r["dimensions"] == {"width": CHIP_PX, "height": CHIP_PX}
    assert a["scaleX"] == 10 and a["scaleY"] == -10
    assert a["translateX"] == 500000.0 - CHIP_PX * 5
    assert a["translateY"] == 2900000.0 + CHIP_PX * 5


def test_fr_f1_keep_chip_needs_enough_confident_labels():
    lab = np.full((CHIP_PX, CHIP_PX), 255, np.uint8)
    assert not keep_chip(lab, min_frac=0.02)
    lab[:20, :] = 1
    assert keep_chip(lab, min_frac=0.02)


def test_fr_f1_to_chw_orders_bands_and_masks_nodata():
    arr = np.zeros((2, 2), dtype=[("B2", "f4"), ("B3", "f4")])
    arr["B2"], arr["B3"] = 1.0, np.nan
    out = to_chw(arr, ("B3", "B2"))
    assert out.shape == (2, 2, 2) and out.dtype == np.float32
    assert (out[1] == 1.0).all() and (out[0] == 0.0).all()  # NaN -> 0


def test_pick_windows_honours_window_size():
    from daiff.gee.review import pick_windows

    g = Grid.from_bounds("EPSG:32646", (300000, 2900000, 310000, 2910000), res=30)
    valid = np.ones(g.shape, bool)
    pts = pick_windows(valid, g, 3, 1, window_m=2560)
    half = 2560 / 2
    for x, _y in pts:
        assert g.bounds[0] + half <= x <= g.bounds[2] - half
