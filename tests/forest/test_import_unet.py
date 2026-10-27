import numpy as np
import pytest
import rasterio

from daiff.forest.import_unet import import_unet
from daiff.grid import Grid
from daiff.store.cog import read_tags, write_cog


def _write(path, grid, arr):
    write_cog(path, arr, grid, nodata=255, tags={})


def test_fr_f1_import_unet_aligns_and_tags_class_maps(tmp_path):
    g10 = Grid.from_bounds("EPSG:32646", (300000, 2900000, 300300, 2900300), res=10)
    src = tmp_path / "drive"
    _write(src / "forest10m_2020.tif", g10, np.ones(g10.shape, np.uint8))
    out = import_unet(g10, src, tmp_path / "raw")
    assert [p.name for p in out] == ["forest10m_2020.tif"]
    assert out[0].parent.name == "forest10m_unet"
    assert read_tags(out[0])["DAIFF_SOURCE"].startswith("forest:unet")
    with rasterio.open(out[0]) as r:
        assert r.read(1).max() == 1


def test_fr_f1_import_unet_rejects_misaligned_map(tmp_path):
    g10 = Grid.from_bounds("EPSG:32646", (300000, 2900000, 300300, 2900300), res=10)
    bad = Grid.from_bounds("EPSG:32646", (300010, 2900000, 300310, 2900300), res=10)
    _write(tmp_path / "d" / "forest10m_2020.tif", bad, np.ones(bad.shape, np.uint8))
    with pytest.raises(ValueError, match="2020"):
        import_unet(g10, tmp_path / "d", tmp_path / "raw")
