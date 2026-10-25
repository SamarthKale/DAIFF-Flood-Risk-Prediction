import numpy as np

from daiff.coupling.compute import coupling_for_year, forest_for_year, mmu_pixels
from daiff.flood.dataset import FEATURES, year_features
from daiff.flood.predict import assemble_features, delta_s, predict_grid, risk_classes
from daiff.store.cog import read_raster
from daiff.terrain.flow import downstream_index


def _features(ctx, year, forest10m=None, dw_year=None):
    cfg = ctx.cfg
    yf = forest_for_year(
        ctx.raw, ctx.grid, cfg.years.t0, year, mmu_pixels(cfg.forest.mmu_ha), forest10m=forest10m
    )
    dw = read_raster(ctx.raw.dw_class(dw_year or year), ctx.grid)
    cf = coupling_for_year(ctx.raw, ctx.grid, ctx.terrain, ctx.rain["rain_p10y_1d"], yf, year, dw)
    return year_features(ctx.terrain, ctx.rain, cf)


def test_risk_classes_breaks():
    s = np.array([0.1, 0.2, 0.39, 0.4, 0.79, 0.8, np.nan])
    assert risk_classes(s, [0.2, 0.4, 0.6, 0.8]).tolist() == [1, 2, 2, 3, 4, 5, 255]


def test_predict_matches_model_predict_proba(flood_ctx, trained):
    feats = flood_ctx.features_for_year(2022)
    S = predict_grid(trained, feats, FEATURES, flood_ctx.grid.shape, tile_rows=37)
    stack, valid = assemble_features(feats, FEATURES)
    idx = np.flatnonzero(valid)[:: max(1, valid.sum() // 100)][:100]
    direct = trained.predict_proba(stack[idx])[:, 1]
    assert np.allclose(S.ravel()[idx], direct, atol=1e-7)
    assert np.isnan(S.ravel()[~valid]).all()


def test_fr_c3_same_forest_map_gives_zero_delta_s(flood_ctx, trained):
    t0 = flood_ctx.cfg.years.t0
    fine = flood_ctx.grid.nested(3)
    base = read_raster(flood_ctx.raw.forest10m(t0), fine)
    shape = flood_ctx.grid.shape
    s0 = predict_grid(trained, _features(flood_ctx, t0), FEATURES, shape)
    s_same = predict_grid(
        trained, _features(flood_ctx, 2024, forest10m=base, dw_year=t0), FEATURES, shape
    )
    d = delta_s(s_same, s0)
    assert np.nanmax(np.abs(d)) <= 1e-6


def test_fr_c4_removing_upstream_forest_never_lowers_s(flood_ctx, trained):
    year = 2022
    fine = flood_ctx.grid.nested(3)
    forest = read_raster(flood_ctx.raw.forest10m(year), fine).copy()
    shape = flood_ctx.grid.shape
    before = predict_grid(trained, _features(flood_ctx, year, forest10m=forest), FEATURES, shape)
    cleared = forest.copy()
    cleared[20 * 3 : 30 * 3, 110 * 3 : 120 * 3] = 0  # 100 upstream 30 m cells
    after = predict_grid(trained, _features(flood_ctx, year, forest10m=cleared), FEATURES, shape)
    ok = ~np.isnan(before)
    assert (after[ok] >= before[ok] - 1e-7).all()
    # Outlet of the cleared block: last land cell on its D8 path (the channel itself is water).
    recv = downstream_index(flood_ctx.terrain.dirs)
    k = 25 * shape[1] + 115
    while recv[k] >= 0 and not np.isnan(before.ravel()[recv[k]]):
        k = recv[k]
    outlet = np.unravel_index(k, shape)
    assert outlet[0] >= 30 or outlet[1] < 110  # really downstream of the block
    assert after[outlet] > before[outlet]
