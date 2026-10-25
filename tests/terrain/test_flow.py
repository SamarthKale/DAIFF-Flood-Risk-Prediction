import numpy as np

from daiff.terrain.flow import (
    accumulate,
    d8_directions,
    downstream_index,
    fill_depressions,
    topological_order,
)


def east_plane(h, w):
    return -np.tile(np.arange(w, dtype="float64"), (h, 1))


def test_d8_codes_on_plane_tilted_east():
    d = d8_directions(east_plane(5, 5), res=30.0)
    assert (d[:, :-1] == 1).all()
    assert (d[:, -1] == 0).all()


def test_d8_prefers_steepest_including_diagonal():
    dem = np.full((3, 3), 9.5)
    dem[1, 1] = 10.0
    dem[2, 2] = 0.0
    assert d8_directions(dem, res=30.0)[1, 1] == 2


def test_fill_raises_pit_to_spill_level():
    dem = np.full((5, 5), 5.0)
    dem[1:4, 1:4] = 2.0
    dem[2, 2] = 1.0
    dem[0, 2] = 3.0  # rim gap
    filled = fill_depressions(dem)
    assert filled[2, 2] >= 3.0
    d = d8_directions(filled, res=30.0)
    idx = downstream_index(d)
    flat = filled.ravel()
    for i in range(1, 4):
        for j in range(1, 4):
            k = i * 5 + j
            assert idx[k] >= 0 and flat[k] > flat[idx[k]]


def test_every_cell_reaches_outlet_after_fill():
    rng = np.random.default_rng(1)
    dem = rng.random((50, 50)) * 10
    dem[10:20, 10:20] = 3.0  # flat plateau
    d = d8_directions(fill_depressions(dem), res=30.0)
    idx = downstream_index(d)
    n = idx.size
    for start in range(n):
        k, steps = start, 0
        while idx[k] >= 0:
            k = idx[k]
            steps += 1
            assert steps <= n


def test_accumulate_counts_upstream_cells():
    d = d8_directions(east_plane(3, 4), res=30.0)
    acc = accumulate(d, np.ones((3, 4)))
    assert (acc == np.array([[1, 2, 3, 4]] * 3)).all()


def test_topological_order_is_upstream_first():
    d = d8_directions(east_plane(2, 3), res=30.0)
    order = topological_order(d)
    pos = {int(c): i for i, c in enumerate(order)}
    idx = downstream_index(d)
    for c in range(6):
        if idx[c] >= 0:
            assert pos[c] < pos[int(idx[c])]


def test_accumulate_treats_nan_weight_as_zero():
    d = d8_directions(east_plane(1, 3), res=30.0)
    acc = accumulate(d, np.array([[np.nan, 1.0, 1.0]]))
    assert acc.tolist() == [[0.0, 1.0, 2.0]]
