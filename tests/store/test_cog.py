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
    g = Grid.from_bounds("EPSG:32646", (300000, 2900010, 330720, 2930730), res=30)
    assert g.shape == (1024, 1024)
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
