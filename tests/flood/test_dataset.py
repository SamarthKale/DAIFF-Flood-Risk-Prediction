import numpy as np

from daiff.flood.dataset import FEATURES, sample_event


def test_sample_event_balances_and_respects_cap():
    rng = np.random.default_rng(0)
    flooded = np.zeros(1000, bool)
    flooded[:300] = True
    valid = np.ones(1000, bool)
    pos, neg = sample_event(flooded, valid, cap=100, rng=rng)
    assert len(pos) == len(neg) == 100
    assert flooded[pos].all() and not flooded[neg].any()


def test_sample_event_uses_all_positives_below_cap():
    flooded = np.zeros(100, bool)
    flooded[:7] = True
    pos, neg = sample_event(flooded, np.ones(100, bool), cap=50, rng=np.random.default_rng(0))
    assert len(pos) == len(neg) == 7


def test_sample_event_with_no_positives_returns_empty():
    pos, neg = sample_event(
        np.zeros(10, bool), np.ones(10, bool), cap=5, rng=np.random.default_rng(0)
    )
    assert pos.size == 0 and neg.size == 0


def test_dataset_has_features_blocks_and_splits(flood_ctx):
    df = flood_ctx.dataset
    assert list(df.columns[-len(FEATURES) :]) == list(FEATURES)
    assert set(df["split"]) == {"train", "test"}
    assert df["label"].isin([0, 1]).all()
    assert df.groupby("event_id")["label"].mean().between(0.49, 0.51).all()
    assert df[list(FEATURES)].notna().all().all()
