# this step of validation detects and measures data problems but edits nothing

from __future__ import annotations
from datetime import datetime, date, timezone
import numpy as np
import pandas as pd

TICK = {"BTCUSDT": 0.1}
STEP = {"BTCUSDT": 0.001}

def day_bounds_us(day:date) -> tuple[int, int]:
    start = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1e6)
    return start, start + 86400 * 1_000_000

def off_grid(x: np.ndarray, step: float) :
    k = x / step
    return int((np.abs(k - np.round(k)) > 1e-6).sum())

def check_aggtrades(df: pd.DataFrame, day: date, symbol: str, min_gap_s: float = 10.0) -> tuple[dict, pd.DataFrame]:

    start, end = day_bounds_us(day)
    r = {"day" : day.isoformat(), "rows": len(df)}
    r["unsorted_ids"] = int((np.diff(df.agg_id.to_numpy()) <= 0).sum())
    r["dup_ids"] = int(df.agg_id.duplicated().sum())
    r["conflicating_dups"] = int(df.drop_duplicates().agg_id.duplicated().sum())

    s = df.drop_duplicates().sort_values("agg_id", kind="stable")
    agg, first, last, ts = (s[c].tonumpy() for c in ("agg_id", "first_id", "last_id", "ts"))
    hole = first[1:] - last[:-1] - 1
    r["agg_id_jumps"] = int((np.diff(agg) != 1).sum())
    r["chain_breaks"] = int((hole != 0).sum())
    r["missing_fills"] = int(hole[hole > 0].sum())
    r["bad_ranges"] = int((first > last).sum())
    r["ts_backwards"] = int((np.diff(ts) < 0).sum())
    r["out_of_day"] = int(((ts < start) | (ts >= end)).sum())
    r["nonpositive"] = int(((s.price <= 0) | (s.qty <= 0)).sum())
    r["off_tick"]= off_grid(s.price.to_numpy(), TICK[symbol])
    r["off_step"]= off_grid(s.qty.to_numpy(), STEP[symbol])

    #Silence between Consecutive Trades
    dt_s = np.diff(ts) / 1e6
    r["p999_gap_s"] = float(np.quantile(dt_s, 0.999)) if dt_s.size else float("nan")
    r["max_gap_s"] = float(dt_s.max()) if dt_s.size else float("nan")

    idx_id = np.flatnonzero(hole > 0)
    idx_t = np.flatnonzero(dt_s > min_gap_s)
    r["id_gaps"], r["time_gaps"] = len(idx_id), len(idx_t)
    gaps = pd.DataFrame(
        {
            "day": day.isoformat(),
            "kind": ["id_gap"] * len(idx_id) + ["time_gap"] * len(idx_t),
            "start_us": np.r_[ts[idx_id], ts[idx_t]],
            "end_us": np.r_[ts[idx_id + 1], ts[idx_t + 1]],
            "missing_fills": np.r_[hole[idx_id], np.zeros(len(idx_t), dtype="int64")],
        }
    )
    gaps["seconds"] = (gaps.end_us - gaps.start_us) / 1e6
    return r, gaps

RECON_KEYS = ["uncovered_trades", "empty_aggs", "qty_mismatch", "price_mismatch", "ts_mismatch", "side_mismatch"]
MINUTE_US = 60 * 1_000_000

def reconcile_trade(agg:pd.DataFrame, trades: pd.DataFrame) -> dict:
    a = agg.sort_values("first_id", kind="stable").reset_index(drop=True)
    t = trades.sort_values("id", kind="stable").reset_index(drop=True)

    pos = np.searchsorted(a.first_id.to_numpy(), t.id.to_numpy(), side="right") - 1
    safe = pos.clip(0)
    covered = (pos >= 0) & (t.id.to_numpy() <= a.last_id.to_numpy()[safe])
    t = t[covered].assign(pos=pos[covered])
    g = t.groupby("pos").agg(
        qty = ("qty", "sum"),
        pmin = ("price", "min"), pmax = ("price", "max"),
        tmin = ("ts", "min"), tmax = ("ts", "max"),
        smin = ("is_buyer_maker", "min"), smax = ("is_buyer_maker", "max")
    )
    m = a.loc[g.index]
    return {
        "agg_rows": len(agg),
        "trade_rows": len(trades),
        "uncovered_trades": int((~covered).sum()),
        "empty_aggs": int(len(a) - len(g)),
        "qty_mismatch": int((~np.isclose(g.qty, m.qty, rtol=0, atol=1e-9)).sum()),
        "price_mismatch": int(((g.pmin != m.price) | (g.pmax != m.price)).sum()),
        "ts_mismatch": int(((g.tmin != m.ts) | (g.tmax != m.ts)).sum()),
        "side_mismatch": int(
            ((g.smin != m.is_buyer_maker) | (g.smax != m.is_buyer_maker)).sum()
        )
    }

def reconcile_klines(agg: pd.DataFrame, klines: pd.DataFrame) -> pd.DataFrame:
    a = agg.sort_values("agg_id", kind="stable")
    a = a.assign(
        minute = (a.ts // MINUTE_US) * MINUTE_US,
        fills = a.last_id - a.first_id + 1,
        buy_qty = a.qty.where(~a.is_buyer_maker, 0.0)
    )
    mine = a.groupby("minute", sort = True).agg(
        open = ("price", "first"), high = ("price", "max"), low = ("price", "min"),
        close = ("price", "last"), volume = ("qty", "sum"),
        taker_buy = ("buy_qty", "sum"), count = ("fills", "sum")
    )

    k = klines.set_index("open_time").reindex(mine.index)
    missing = k["open"].isna()
    cols = ["open", "high", "low", "close"]
    res = pd.DataFrame(
        {
            "ohlc_ok": (mine[cols] == k[cols]).all(axis=1),
            "volume_ok": np.isclose(mine.volume, k.volume, rtol=0, atol=1e-6),
            "taker_buy_ok": (mine["taker_buy"] - k["taker_buy_volume"]).abs() <= 1e-6,
            "count_ok": mine["count"] == k["count"]
        }
    )
    res.loc[missing] = False
    res["missing_kline"] = missing
    res.index.name = "open_time"
    return res
