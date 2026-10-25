import numpy as np
import pytest

from daiff.validation.forest_accuracy import accuracy_report, cohens_kappa
from daiff.validation.report import write_test_log_entry
from daiff.validation.sampling import allocate, stratified_sample


def test_allocation_respects_total_and_minimum():
    n = allocate({1: 700_000, 2: 280_000, 3: 20_000}, n_total=600, min_per_stratum=150)
    assert n[3] >= 150 and sum(n.values()) >= 600
    assert n[1] == round(600 * 0.7)


def test_stratified_sample_draws_from_each_stratum(small_grid):
    fine = small_grid.nested(3)
    strata = np.ones(fine.shape, dtype="uint8")
    strata[:, :4] = 2
    strata[0, 11] = 3
    df = stratified_sample(strata, fine, n_total=20, min_per_stratum=1, seed=0)
    assert set(df["stratum"]) == {1, 2, 3}
    assert (df[df.stratum == 3][["row", "col"]].values == [[0, 11]]).all()
    assert df["point_id"].is_unique and df["lon"].between(80, 100).all()


def test_olofsson_hand_computed_two_strata():
    # stratum 1 (map loss, W=0.2): 8 ref loss, 2 ref no-loss; stratum 2 (W=0.8): 1 loss, 9 no-loss
    map_cls = np.array([1] * 10 + [2] * 10)
    ref_cls = np.array([1] * 8 + [2] * 2 + [1] * 1 + [2] * 9)
    r = accuracy_report(map_cls, ref_cls, {1: 0.2, 2: 0.8})
    assert r["overall_accuracy"] == pytest.approx(0.88)
    assert r["classes"][1]["users_accuracy"] == pytest.approx(0.8)
    assert r["classes"][1]["producers_accuracy"] == pytest.approx(0.16 / 0.24)
    assert r["classes"][1]["area_proportion"] == pytest.approx(0.24)
    assert r["classes"][1]["area_proportion_ci95"] == pytest.approx(1.96 * 0.0843274, abs=1e-6)
    u, p = 0.8, 0.16 / 0.24
    assert r["classes"][1]["f1"] == pytest.approx(2 * u * p / (u + p))


def test_cohens_kappa():
    assert cohens_kappa([1, 0, 1], [1, 0, 1]) == 1.0
    assert cohens_kappa([1, 1, 0, 0, 1, 0], [1, 0, 0, 0, 1, 1]) == pytest.approx(1 / 3)


def test_write_test_log_entry_appends_row(tmp_path):
    log = tmp_path / "test_log.md"
    log.write_text(
        "| Date | Requirement | Method | Config / run_id / commit | Result | Evidence | By |\n"
    )
    write_test_log_entry(
        log,
        requirement="FR-R2",
        method="A",
        run_ref="kopili / abc / def",
        result="PASS",
        evidence="metrics/flood.json",
        by="Claude",
    )
    last = log.read_text().strip().splitlines()[-1]
    cells = [c.strip() for c in last.strip("|").split("|")]
    assert len(cells) == 7 and cells[1:] == [
        "FR-R2",
        "A",
        "kopili / abc / def",
        "PASS",
        "metrics/flood.json",
        "Claude",
    ]
