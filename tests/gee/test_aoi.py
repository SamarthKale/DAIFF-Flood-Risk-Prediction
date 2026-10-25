import pytest

from daiff.gee.aoi import pfaf_range, utm_bounds


def test_pfaf_range_selects_children():
    assert pfaf_range(452580, parent_level=6, child_level=8) == (45258000, 45258100)


def test_utm_bounds_cover_lonlat_box():
    xmin, ymin, xmax, ymax = utm_bounds((91.58, 25.10, 93.69, 26.61), "EPSG:32646")
    assert xmin < ymin and xmax - xmin == pytest.approx(213_000, rel=0.03)
    assert ymax - ymin == pytest.approx(168_000, rel=0.03)


@pytest.mark.gee
def test_live_kopili_subbasins_cover_basin():
    from daiff.config import load_config
    from daiff.gee.aoi import subbasins_fc
    from daiff.gee.auth import init_ee
    from tests.conftest import REPO

    ee = init_ee(load_config(REPO / "configs" / "kopili.yaml"))
    fc = subbasins_fc(ee, 4060884570, 6, 8)
    assert fc.size().getInfo() == 41
