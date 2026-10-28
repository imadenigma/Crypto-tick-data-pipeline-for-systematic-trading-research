import numpy as np
import pandas as pd
import pytest

from orderflow.data.validate import CleaningError, clean_aggtrades

T0 = 1_722_470_400_000_000   # 2024-08-01 00:00:00 UTC, in microseconds

def _day(n=1500, seed=0, agg0=0, fill0=1000, t0=T0):

    rng = np.random.default_rng(seed)
    fills = rng.integers(1, 4, n)
    last = fill0 + np.cumsum(fills) - 1
    return pd.DataFrame({
        "agg_id": agg0 + np.arange(n),
        "price": np.round(60000 + 0.1 * np.cumsum(rng.choice([-1, 0, 0, 1], n)), 1),
        "qty": np.round(0.001 * rng.integers(1, 500, n), 3),
        "first_id": last - fills + 1,
        "last_id": last,
        "ts": t0 + np.cumsum(rng.integers(0, 2_000_000, n)),
        "is_buyer_maker": rng.random(n) < 0.5,
    })


def _two_days():
    d1 = _day(seed=1)
    d2 = _day(
        seed=2,
        agg0=len(d1),
        fill0=int(d1.last_id.iloc[-1]) + 1,
        t0=int(d1.ts.iloc[-1]) + 1,
    )
    return d1, d2

def test_clean_drops_only_exact_duplicates_and_balances():
    d = _day()
    dirty = pd.concat([d, d.iloc[[5, 6, 7]]]).sample(frac=1, random_state=0)
    before = dirty.copy()
    out, s = clean_aggtrades(dirty, "BTCUSDT")
    assert (s["rows_in"], s["rows_out"], s["dropped_exact_dups"]) == (1503, 1500, 3)
    assert out.agg_id.is_monotonic_increasing and out.agg_id.is_unique
    assert s["id_gaps"] == 0 and s["unscored"] == 400
    pd.testing.assert_frame_equal(dirty, before)

def test_clean_stops_on_conflicting_duplicates_and_systemic_off_tick():
    d = _day()
    conflicting = pd.concat([d, d.iloc[[5]].assign(price=d.price[5] + 0.1)])
    with pytest.raises(CleaningError, match="duplicate agg_ids"):
        clean_aggtrades(conflicting, "BTCUSDT")
    with pytest.raises(CleaningError, match="off the 0.1 tick"):
        clean_aggtrades(d.assign(price=d.price + 0.03), "BTCUSDT")

def test_clean_keeps_and_annotates_isolated_off_tick_prices():
    d = _day()
    d.loc[[100, 900], "price"] += 0.03
    out, s = clean_aggtrades(d, "BTCUSDT")
    assert s["off_tick"] == 2 and s["rows_out"] == len(d)
    assert np.flatnonzero(out.off_tick).tolist() == [100, 900]


def test_clean_day_by_day_with_tail_equals_both_days_at_once():
    d1, d2 = _two_days()
    o1, _ = clean_aggtrades(d1, "BTCUSDT")
    o2, s2 = clean_aggtrades(d2, "BTCUSDT", tail=o1.tail(400))
    both, _ = clean_aggtrades(pd.concat([d1, d2]), "BTCUSDT")
    pd.testing.assert_frame_equal(o2, both.iloc[len(o1):].reset_index(drop=True))
    assert s2["unscored"] == 0


def test_clean_sees_an_id_hole_at_the_day_boundary():
    d1, d2 = _two_days()
    d2[["first_id", "last_id"]] += 7          # 7 trade ids vanish exactly at midnight
    o1, _ = clean_aggtrades(d1, "BTCUSDT")
    o2, s2 = clean_aggtrades(d2, "BTCUSDT", tail=o1.tail(400))
    assert o2.hole_before.iloc[0] == 7
    assert (s2["id_gaps"], s2["missing_fills"]) == (1, 7)