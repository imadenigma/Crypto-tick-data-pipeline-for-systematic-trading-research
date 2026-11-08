from datetime import date

import numpy as np
import pandas as pd
import pytest

from orderflow.data.validate import (RECON_KEYS, STRUCTURAL_ISSUES, check_aggtrades, flag_bad_prints,
                                     reconcile_klines, reconcile_trade, reconcile_klines_daily)

T0 = 1_722_470_400_000_000   # 2024-08-01 00:00:00 UTC, in microseconds
MIN = 60_000_000
OK_COLS = ["ohlc_ok", "volume_ok", "taker_buy_ok", "count_ok"]


def _trades():
    return pd.DataFrame({
        "id": [10, 11, 12, 13, 14],
        "price": [60000.0, 60000.0, 59999.9, 60000.1, 60000.1],
        "qty": [0.5, 0.3, 0.2, 0.4, 0.1],
        "quote_qty": [30000.0, 18000.0, 11999.98, 24000.04, 6000.01],
        "ts": [T0 + 1_000_000] * 3 + [T0 + MIN + 1_000_000] * 2,
        "is_buyer_maker": [True, True, True, False, False],
    })


def _agg():
    return pd.DataFrame({
        "agg_id": [1, 2, 3],
        "price": [60000.0, 59999.9, 60000.1],
        "qty": [0.8, 0.2, 0.5],
        "first_id": [10, 12, 13],
        "last_id": [11, 12, 14],
        "ts": [T0 + 1_000_000, T0 + 1_000_000, T0 + MIN + 1_000_000],
        "is_buyer_maker": [True, True, False],
    })


def _klines():
    return pd.DataFrame({
        "open_time": [T0, T0 + MIN],
        "open": [60000.0, 60000.1], "high": [60000.0, 60000.1],
        "low": [59999.9, 60000.1], "close": [59999.9, 60000.1],
        "volume": [1.0, 0.5],
        "close_time": [T0 + MIN - 1000, T0 + 2 * MIN - 1000],
        "quote_volume": [59999.98, 30000.05], "count": [3, 2],
        "taker_buy_volume": [0.0, 0.5], "taker_buy_quote_volume": [0.0, 30000.05],
        "ignore": [0.0, 0.0],
    })


# ---------- reconcile_trades ----------

def test_reconcile_trades_clean():
    r =     reconcile_trade(_agg(), _trades())
    assert r["agg_rows"] == 3 and r["trade_rows"] == 5
    assert all(r[k] == 0 for k in RECON_KEYS), r


FAULTS = [
    ("missing fill", lambda t: t[t.id != 11], "qty_mismatch"),
    ("aggTrade with no fills", lambda t: t[t.id != 12], "empty_aggs"),
    ("fill outside every range", lambda t: pd.concat([t, t.iloc[[0]].assign(id=15)]), "uncovered_trades"),
    ("wrong price", lambda t: t.assign(price=np.where(t.id == 13, 60000.2, t.price)), "price_mismatch"),
    ("fill before its aggTrade", lambda t: t.assign(ts=np.where(t.id == 10, t.ts - 1, t.ts)), "ts_mismatch"),
    ("wrong side", lambda t: t.assign(is_buyer_maker=np.where(t.id == 14, True, t.is_buyer_maker)), "side_mismatch"),
]


@pytest.mark.parametrize("name, fault, key", FAULTS)
def test_reconcile_trades_detects_each_fault_alone(name, fault, key):
    r = reconcile_trade(_agg(), fault(_trades()))
    assert r[key] == 1, (name, r)
    assert all(r[k] == 0 for k in RECON_KEYS if k != key), (name, r)


def test_reconcile_trades_any_row_order_and_inputs_untouched():
    agg = _agg().iloc[::-1].copy()
    tr = _trades().iloc[[3, 0, 4, 2, 1]].copy()
    agg_before, tr_before = agg.copy(), tr.copy()
    r = reconcile_trade(agg, tr)
    assert all(r[k] == 0 for k in RECON_KEYS), r
    pd.testing.assert_frame_equal(agg, agg_before)
    pd.testing.assert_frame_equal(tr, tr_before)


# ---------- reconcile_klines ----------

def test_reconcile_klines_clean():
    res = reconcile_klines(_agg(), _klines())
    assert list(res.index) == [T0, T0 + MIN]
    assert res[OK_COLS].all().all() and not res.missing_kline.any()


def test_reconcile_klines_detects_wrong_fields():
    k = _klines()
    k.loc[0, "close"] = 60000.0      # wrong close in minute 0
    k.loc[1, "volume"] += 0.001      # wrong volume in minute 1
    k.loc[1, "count"] = 3            # wrong fill count in minute 1
    res = reconcile_klines(_agg(), k)
    assert res.ohlc_ok.tolist() == [False, True]
    assert res.volume_ok.tolist() == [True, False]
    assert res.count_ok.tolist() == [True, False]
    assert res.taker_buy_ok.all()


def test_reconcile_klines_missing_minute_and_extra_rows():
    k = _klines()
    extra = k.iloc[[1]].assign(open_time=T0 + 2 * MIN)    # a minute with no trades: must be ignored
    res = reconcile_klines(_agg(), pd.concat([k.iloc[[0]], extra]))
    assert list(res.index) == [T0, T0 + MIN]
    assert res.missing_kline.tolist() == [False, True]
    assert not res.loc[T0 + MIN, OK_COLS].any()


def test_reconcile_klines_inputs_untouched():
    agg, k = _agg(), _klines()
    agg_before, k_before = agg.copy(), k.copy()
    reconcile_klines(agg, k)
    pd.testing.assert_frame_equal(agg, agg_before)
    pd.testing.assert_frame_equal(k, k_before)


# --------- flag bad prints ----------

def _quiet(n = 1000, seed = 0):
    rng = np.random.default_rng(seed)
    return 60000.0 + rng.integers(0,2, n) * 0.1

def _flags(p, **kw):
    return flag_bad_prints(pd.DataFrame({"agg_id": np.arange(len(p)), "price": p}), "BTCUSDT", **kw)

def test_bad_prints_spike_vs_real_move():
    spike, step = _quiet(), _quiet()
    spike[700] *= 1.02          # one isolated +2% print
    step[700:] *= 1.02          # a real, permanent +2% move
    assert np.flatnonzero(_flags(spike).bad_prints).tolist() == [700]
    assert np.flatnonzero(_flags(step).bad_prints).tolist() == list(range(700, 800))   # N/2 swamping


def test_bad_prints_are_causal():
    p = _quiet()
    p[700] *= 1.02
    q = p.copy()
    q[800:] *= 1.05             # rewrite the future from trade 800 on
    pd.testing.assert_frame_equal(_flags(p).iloc[:800], _flags(q).iloc[:800])

def test_bad_prints_need_both_conditions():
    p = _quiet()
    p[700] *= 1.0005  # +5 bp: statistically huge in a quiet market but economically small
    f = _flags(p)
    assert f.z[700] > 10 and not f.bad_prints[700]
    assert _flags(p, min_dev_bp = 1.0).bad_prints[700]

def test_bad_prints_warmup_unsorted_untouched():
    df = pd.DataFrame({"agg_id": np.arange(1000), "price": _quiet()})
    before = df.copy()
    f = flag_bad_prints(df, "BTCUSDT")
    assert f.z.iloc[:400].isna().all() and not f.bad_prints.iloc[:400].any()
    pd.testing.assert_frame_equal(df, before)
    with pytest.raises(ValueError):
        flag_bad_prints(df.iloc[::-1], "BTCUSDT")


def test_reconcile_trades_accepts_fills_within_the_100ms_window_only():
    def late(dt):
        return _trades().assign(ts=lambda t: np.where(t.id == 11, t.ts + dt, t.ts))
    assert reconcile_trade(_agg(), late(100_000))["ts_mismatch"] == 0
    assert reconcile_trade(_agg(), late(100_001))["ts_mismatch"] == 1


def test_reconcile_trades_measures_ids_missing_inside_ranges():
    tr = _trades()[lambda t: t.id != 14]
    agg = _agg().assign(qty=[0.8, 0.2, 0.4])
    r = reconcile_trade(agg, tr)
    assert all(r[k] == 0 for k in RECON_KEYS), r
    assert (r["aggs_with_inner_gaps"], r["inner_missing_ids"]) == (1, 1)


def test_check_aggtrades_reports_every_structural_issue():
    r, _ = check_aggtrades(_agg(), date(2024, 8, 1), "BTCUSDT")
    missing = [k for k in STRUCTURAL_ISSUES if k not in r]
    assert not missing, missing

DAY = date(2024, 8, 1)
EXACT = 1e-9

def test_reconcile_klines_daily_matches_and_ignores_other_days():
    nextday = _klines().assign(open_time= lambda d: d.open_time + 24 * 60 * 60 * 1_000_000, volume=9.9)
    r = reconcile_klines_daily(_agg(), pd.concat([_klines(), nextday]), DAY, tol_btc=EXACT)
    assert r["kline_minutes"] == 2
    assert all(r[f] for f in ["volume_ok", "taker_buy_ok", "high_ok", "low_ok"]), r
    assert r["ids_minus_fills"] == 0

def test_reconcile_klines_daily_detects_differences_and_measures_offbook_ids():
    k = _klines().assign(volume=[1.0, 0.6], high=[60000.0, 60000.2])
    agg = _agg().assign(last_id=[11, 12, 15])
    r = reconcile_klines_daily(agg, k, DAY, tol_btc=EXACT)
    assert round(r["volume_diff_btc"], 9) == 0.1
    assert not r["volume_ok"] and not r["high_ok"] and r["taker_buy_ok"] and r["low_ok"]
    assert r["ids_minus_fills"] == 1