# this step of validation detects and measures data problems but edits nothing

from __future__ import annotations
from datetime import datetime, date, timezone
import numpy as np
import pandas as pd

TICK = {"BTCUSDT": 0.1}
STEP = {"BTCUSDT": 0.001}
MAX_OFF_TICK_SHARE = 0.10


def day_bounds_us(day:date) -> tuple[int, int]:
    start = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1e6)
    return start, start + 86400 * 1_000_000

def off_grid_mask(x: np.ndarray, step: float) -> np.ndarray:
    k = x / step
    return np.abs(k - np.round(k)) > 1e-6


def off_grid(x: np.ndarray, step: float) -> int:
    return int(off_grid_mask(x, step).sum())

def check_aggtrades(df: pd.DataFrame, day: date, symbol: str, min_gap_s: float = 10.0) -> tuple[dict, pd.DataFrame]:  # pyright: ignore[reportMissingTypeArgument]

    start, end = day_bounds_us(day)
    r = {"day" : day.isoformat(), "rows": len(df)}
    r["unsorted_ids"] = int((np.diff(df.agg_id.to_numpy()) <= 0).sum())
    r["dup_ids"] = int(df.agg_id.duplicated().sum())
    r["conflicting_dups"] = int(df.drop_duplicates().agg_id.duplicated().sum())

    s = df.drop_duplicates().sort_values("agg_id", kind="stable")
    agg, first, last, ts = (s[c].to_numpy() for c in ("agg_id", "first_id", "last_id", "ts"))
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
AGG_WINDOW_US = 100_000
OUTAGE_GAP_S = 30.0   # a silence longer than this is an outage, not quiet trading (T000i)
STRUCTURAL_ISSUES = ["unsorted_ids", "dup_ids", "conflicting_dups", "agg_id_jumps", "chain_breaks",
                     "missing_fills", "bad_ranges", "ts_backwards", "out_of_day", "nonpositive",
                     "off_tick", "off_step"]

def reconcile_trade(agg:pd.DataFrame, trades: pd.DataFrame) -> dict:
    a = agg.sort_values("first_id", kind="stable").reset_index(drop=True)
    t = trades.sort_values("id", kind="stable").reset_index(drop=True)

    pos = np.searchsorted(a.first_id.to_numpy(), t.id.to_numpy(), side="right") - 1
    safe = pos.clip(0)
    covered = (pos >= 0) & (t.id.to_numpy() <= a.last_id.to_numpy()[safe])
    t = t[covered].assign(pos=pos[covered])
    g = t.groupby("pos").agg(
        n=("id", "size"),
        qty=("qty", "sum"),
        pmin=("price", "min"),
        pmax=("price", "max"),
        tmin=("ts", "min"),
        tmax=("ts", "max"),
        smin=("is_buyer_maker", "min"),
        smax=("is_buyer_maker", "max"),
    )
    m = a.loc[g.index]
    span = (m.last_id - m.first_id + 1).to_numpy()

    return {
        "agg_rows": len(agg),
        "trade_rows": len(trades),
        "uncovered_trades": int((~covered).sum()),
        "empty_aggs": int(len(a) - len(g)),
        "qty_mismatch": int((~np.isclose(g.qty, m.qty, rtol=0, atol=1e-9)).sum()),
        "price_mismatch": int(((g.pmin != m.price) | (g.pmax != m.price)).sum()),
        "ts_mismatch": int(((g.tmin < m.ts) | (g.tmax > m.ts + AGG_WINDOW_US)).sum()),
        "side_mismatch": int(
            ((g.smin != m.is_buyer_maker) | (g.smax != m.is_buyer_maker)).sum()
        ),
        "aggs_with_inner_gaps": int((span > g.n.to_numpy()).sum()),
        "inner_missing_ids": int((span - g.n.to_numpy()).sum()),
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

def flag_bad_prints(agg: pd.DataFrame, symbol: str, window: int = 200, k : float = 10.0, min_dev_bp: float = 10.0):
    if not agg.agg_id.is_monotonic_increasing:
        raise ValueError("sort by agg_id first: trade order is defined by the id, not the timestamp")
    price = agg.price.to_numpy()
    lp = pd.Series(np.log(price))
    ref = lp.rolling(window=window, min_periods=window).median().shift(1)
    resid = lp - ref
    mad = resid.abs().rolling(window, min_periods=window).median().shift(1)
    scale = np.maximum(1.4826 * mad.to_numpy(), TICK[symbol] / price) #bp
    z = np.abs(resid.to_numpy()) / scale
    dev_bp = resid.to_numpy() * 1e4
    bad = (z > k) & (np.abs(dev_bp) > min_dev_bp)
    return pd.DataFrame({"dev_bp": dev_bp, "z": z, "bad_prints" : bad}, index=agg.index)

def summarize_flags(flags: pd.DataFrame) -> dict:
    scored = flags.z.notna()
    return {
        "bp_scored": int(scored.sum()),
        "bp_unscored": int((~scored).sum()),
        "bp_flagged": int(flags.bad_prints.sum()),
        "bp_max_abs_dev": float(flags.dev_bp.abs().max()),
        "bp_max_z": float(flags.z.max()),
    }

def flag_episodes(agg: pd.DataFrame, flags: pd.DataFrame, gap: int = 200) -> pd.DataFrame:
    f = agg.loc[flags.bad_prints, ["agg_id", "ts"]].join(flags.loc[flags.bad_prints, ["dev_bp", "z"]])
    f = f.assign(abs_dev=f.dev_bp.abs())
    episode = (f.agg_id.diff() > gap).cumsum()
    out = f.groupby(episode).agg(
        start_us=("ts", "first"), end_us=("ts", "last"),
        first_agg_id=("agg_id", "first"), last_agg_id=("agg_id", "last"),
        n_flags=("agg_id", "size"), mean_dev_bp=("dev_bp", "mean"),
        max_abs_dev_bp=("abs_dev", "max"), max_z=("z", "max"),
    )
    out["span_trades"] = out.last_agg_id - out.first_agg_id + 1
    out["side"] = np.sign(out.mean_dev_bp).astype(int)      # -1 down-wick, +1 up-wick
    return out.reset_index(drop=True)

class CleaningError(RuntimeError):
    "A data problem that needs a human decision"

def clean_aggTrades(df: pd.DataFrame, symbol: str, tail : pd.DataFrame | None = None, window: int = 200):
    rows_in = len(df)
    s = df.drop_duplicates()
    dropped = rows_in - len(s)
    if s.agg_id.duplicated().any():
        raise CleaningError(f"{int(s.agg_id.duplicated().sum())} agg_ids repeat with different contents")
    s = s.sort_values("agg_id", kind="stable")
    if ((s.price <= 0) | (s.qty <= 0)).any() or (s.first_id > s.last_id).any():
        raise CleaningError("non-positive price or quantity, or first_id > last_id")
    if off_grid(s.price.to_numpy(), TICK[symbol]) or off_grid(s.qty.to_numpy(), STEP[symbol]):
        raise CleaningError("price or quantity off the exchange grid: contract spec change?")


class CleaningError(RuntimeError):
    """Data is too corrupted to be cleaned automatically."""

def clean_aggtrades(df: pd.DataFrame, symbol: str, tail: pd.DataFrame | None = None, window: int = 200) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    s = df.drop_duplicates()
    dropped = rows_in - len(s)
    if s.agg_id.duplicated().any():
        raise CleaningError(f"{dropped} duplicate rows dropped, but still {s.agg_id.duplicated().sum()} duplicate agg_ids remain")
    s = s.sort_values("agg_id", kind="stable").reset_index(drop=True)
    if ((s.price <= 0) | (s.qty <= 0)).any() or (s.first_id > s.last_id).any():
        raise CleaningError("non-positive price or quantity, or first_id > last_id")
    off_tick = off_grid_mask(s.price.to_numpy(), TICK[symbol])
    off_q = off_grid(s.qty.to_numpy(), STEP[symbol])
    if off_q or off_tick.mean() > MAX_OFF_TICK_SHARE:
        raise CleaningError(
            f"{int(off_tick.sum()):,} of {len(s):,} prices off the {TICK[symbol]} tick, "
            f"{off_q:,} quantities off the {STEP[symbol]} step: contract spec change?"
        )
    n_tail = 0 if tail is None else len(tail)
    ext = s if tail is None else pd.concat([tail[list(df.columns)], s],  ignore_index=True)
    ext["hole_before"] = (ext.first_id - ext.last_id.shift(1) - 1).fillna(0).astype("int64")
    ext["gap_s"] = (ext.ts.diff() / 1e6).fillna(0.0)
    if (ext.hole_before.iloc[n_tail:] < 0).any():
        raise CleaningError("overlapping id ranges between consecutive aggTrades")
    ext = ext.join(flag_bad_prints(ext, symbol, window))
    out = ext.iloc[n_tail:].reset_index(drop=True)
    out["off_tick"] = off_tick
    stats = {
        "rows_in": rows_in,
        "rows_out": len(out),
        "dropped_exact_dups": dropped,
        "id_gaps": int((out.hole_before > 0).sum()),
        "missing_fills" : int(out.hole_before.sum()),
        "max_gap_s": float(out.gap_s.max()), "flagged": int(out.bad_prints.sum()),
        "unscored": int(out.z.isna().sum()), "off_tick": int(off_tick.sum())
    }
    if stats["rows_in"] != stats["rows_out"] + stats["dropped_exact_dups"]:
        raise CleaningError(f"accounting identity broken: {stats}")
    return out, stats