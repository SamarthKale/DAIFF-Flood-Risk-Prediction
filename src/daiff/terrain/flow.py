"""Depression filling, D8 flow directions, topological order and flow accumulation (spec §6.7).

D8 codes follow ESRI: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128; 0 = outlet/sink.
NaN elevations are nodata; cells next to nodata behave like grid edges.
"""

from __future__ import annotations

import heapq

import numba
import numpy as np

# (drow, dcol, code) in ESRI order
_OFFSETS = np.array(
    [
        [0, 1, 1],
        [1, 1, 2],
        [1, 0, 4],
        [1, -1, 8],
        [0, -1, 16],
        [-1, -1, 32],
        [-1, 0, 64],
        [-1, 1, 128],
    ],
    dtype=np.int64,
)


@numba.njit(cache=True)
def _fill(dem: np.ndarray, epsilon: float) -> np.ndarray:
    h, w = dem.shape
    filled = dem.copy()
    closed = np.zeros((h, w), dtype=np.bool_)
    heap = [(0.0, np.int64(0))]
    heap.pop()
    for r in range(h):
        for c in range(w):
            if np.isnan(dem[r, c]):
                closed[r, c] = True
    for r in range(h):
        for c in range(w):
            if closed[r, c]:
                continue
            border = r == 0 or c == 0 or r == h - 1 or c == w - 1
            if not border:
                for k in range(8):
                    rr, cc = r + _OFFSETS[k, 0], c + _OFFSETS[k, 1]
                    if np.isnan(dem[rr, cc]):
                        border = True
                        break
            if border:
                closed[r, c] = True
                heapq.heappush(heap, (filled[r, c], np.int64(r * w + c)))
    while len(heap) > 0:
        z, idx = heapq.heappop(heap)
        r, c = idx // w, idx % w
        for k in range(8):
            rr, cc = r + _OFFSETS[k, 0], c + _OFFSETS[k, 1]
            if rr < 0 or cc < 0 or rr >= h or cc >= w or closed[rr, cc]:
                continue
            closed[rr, cc] = True
            filled[rr, cc] = max(dem[rr, cc], z + epsilon)
            heapq.heappush(heap, (filled[rr, cc], np.int64(rr * w + cc)))
    return filled


def fill_depressions(dem: np.ndarray, epsilon: float = 1e-4) -> np.ndarray:
    """Priority-flood with epsilon (Barnes et al. 2014): every valid cell drains to an edge."""
    return _fill(np.asarray(dem, dtype=np.float64), float(epsilon))


@numba.njit(cache=True)
def _d8(z: np.ndarray, res: float) -> np.ndarray:
    h, w = z.shape
    out = np.zeros((h, w), dtype=np.uint8)
    diag = res * np.sqrt(2.0)
    for r in range(h):
        for c in range(w):
            if np.isnan(z[r, c]):
                continue
            best, code = 0.0, 0
            for k in range(8):
                rr, cc = r + _OFFSETS[k, 0], c + _OFFSETS[k, 1]
                if rr < 0 or cc < 0 or rr >= h or cc >= w or np.isnan(z[rr, cc]):
                    continue
                dist = diag if _OFFSETS[k, 0] != 0 and _OFFSETS[k, 1] != 0 else res
                drop = (z[r, c] - z[rr, cc]) / dist
                if drop > best:
                    best, code = drop, _OFFSETS[k, 2]
            out[r, c] = code
    return out


def d8_directions(filled: np.ndarray, res: float) -> np.ndarray:
    return _d8(np.asarray(filled, dtype=np.float64), float(res))


@numba.njit(cache=True)
def _downstream(dirs: np.ndarray) -> np.ndarray:
    h, w = dirs.shape
    out = np.full(h * w, -1, dtype=np.int64)
    for r in range(h):
        for c in range(w):
            code = dirs[r, c]
            if code == 0:
                continue
            for k in range(8):
                if _OFFSETS[k, 2] == code:
                    rr, cc = r + _OFFSETS[k, 0], c + _OFFSETS[k, 1]
                    if 0 <= rr < h and 0 <= cc < w:
                        out[r * w + c] = rr * w + cc
                    break
    return out


def downstream_index(dirs: np.ndarray) -> np.ndarray:
    """Flat index of each cell's receiver, -1 for outlets."""
    return _downstream(np.asarray(dirs, dtype=np.uint8))


@numba.njit(cache=True)
def _topo(recv: np.ndarray) -> np.ndarray:
    n = recv.size
    indeg = np.zeros(n, dtype=np.int64)
    for i in range(n):
        if recv[i] >= 0:
            indeg[recv[i]] += 1
    order = np.empty(n, dtype=np.int64)
    head, tail = 0, 0
    for i in range(n):
        if indeg[i] == 0:
            order[tail] = i
            tail += 1
    while head < tail:
        i = order[head]
        head += 1
        j = recv[i]
        if j >= 0:
            indeg[j] -= 1
            if indeg[j] == 0:
                order[tail] = j
                tail += 1
    return order[:tail]


def topological_order(dirs: np.ndarray) -> np.ndarray:
    """Flat cell indices, upstream cells before the cells they drain into."""
    return _topo(downstream_index(dirs))


@numba.njit(cache=True)
def _accumulate(recv: np.ndarray, order: np.ndarray, weights: np.ndarray) -> np.ndarray:
    acc = weights.copy()
    for i in range(acc.size):
        if np.isnan(acc[i]):
            acc[i] = 0.0
    for i in order:
        j = recv[i]
        if j >= 0:
            acc[j] += acc[i]
    return acc


def accumulate(
    dirs: np.ndarray, weights: np.ndarray, order: np.ndarray | None = None
) -> np.ndarray:
    """Sum of `weights` over each cell and everything upstream of it (NaN weights count 0)."""
    recv = downstream_index(dirs)
    if order is None:
        order = _topo(recv)
    flat = np.asarray(weights, dtype=np.float64).ravel().copy()
    return _accumulate(recv, order, flat).reshape(dirs.shape)
