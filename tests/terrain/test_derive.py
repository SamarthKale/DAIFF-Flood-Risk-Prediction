import numpy as np
import pytest

from daiff.terrain.derive import distance_to_stream, hand, slope_degrees, streams, twi
from daiff.terrain.flow import accumulate, d8_directions, topological_order


def east_plane(h, w, step=1.0):
    return 100 - step * np.tile(np.arange(w, dtype="float64"), (h, 1))


def test_slope_of_plane():
    dem = east_plane(5, 5, step=3.0)  # dz/dx = 3 m per 30 m = 0.1
    s = slope_degrees(dem, res=30.0)
    assert s[2, 2] == pytest.approx(np.degrees(np.arctan(0.1)), abs=0.01)


def test_hand_zero_on_streams_and_height_above_downstream_stream():
    dem = east_plane(3, 5)
    d = d8_directions(dem, 30.0)
    mask = np.zeros((3, 5), bool)
    mask[:, -1] = True
    out = hand(dem, d, mask, topological_order(d))
    assert (out[:, -1] == 0).all()
    assert out[0].tolist() == [4.0, 3.0, 2.0, 1.0, 0.0]


def test_hand_nan_when_no_stream_downstream():
    dem = east_plane(2, 3)
    d = d8_directions(dem, 30.0)
    out = hand(dem, d, np.zeros((2, 3), bool), topological_order(d))
    assert np.isnan(out).all()


def test_distance_to_stream_in_metres():
    mask = np.zeros((1, 3), bool)
    mask[0, 0] = True
    assert distance_to_stream(mask, 30.0).tolist() == [[0.0, 30.0, 60.0]]


def test_streams_threshold_in_km2():
    acc = np.array([[1.0, 1111.0, 1112.0]])
    assert streams(acc, 900.0, 1.0).tolist() == [[False, False, True]]


def test_twi_increases_with_accumulation():
    dem = east_plane(1, 6)
    d = d8_directions(dem, 30.0)
    acc = accumulate(d, np.ones((1, 6)))
    t = twi(acc, slope_degrees(dem, 30.0), 30.0)
    assert (np.diff(t[0]) > 0).all()
