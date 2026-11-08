from __future__ import annotations
from collections import Counter

import argparse

import pandas as pd
from tqdm import tqdm

from orderflow.config import DEFAULT_CONFIG, REPO_ROOT, load_config
from orderflow.data.catalog import DatasetSpec
from orderflow.data.load import raw_zip, read_zip
from orderflow.data.validate import check_aggtrades, STRUCTURAL_ISSUES, OUTAGE_GAP_S, reconcile_klines_daily
from functools import lru_cache

OUT = REPO_ROOT / "reports" / "data_quality"
ISSUES = ISSUES = STRUCTURAL_ISSUES + ["cross_day_hole"]



def diagnose_chain_breaks(agg: pd.DataFrame) -> dict:
    ordered = agg.sort_values("agg_id", kind="stable")
    previous_last = ordered["last_id"].to_numpy()[:-1]
    following_first = ordered["first_id"].to_numpy()[1:]
    gaps = pd.Series(following_first - previous_last - 1)
    holes = gaps[gaps > 0]
    overlaps = gaps[gaps < 0]
    distribution = holes.value_counts().sort_index()
    distribution.index.name = "skipped_ids_per_break"
    distribution.name = "break_count"
    return {
        "chain_breaks": int(gaps.ne(0).sum()),
        "forward_holes": int(holes.size),
        "overlaps_or_reversals": int(overlaps.size),
        "skipped_ids": int(holes.sum()),
        "largest_hole": int(holes.max()) if not holes.empty else 0,
        "hole_distribution": distribution,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--period", default="dev_slice")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--min-gap-s", type=float, default=OUTAGE_GAP_S)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()

    cfg = load_config(args.config)
    symbol = args.symbol or cfg.primary_symbol
    spec = DatasetSpec("aggTrades", "daily")
    reports, gaps, prev_last = [], [], None

    chain_reports = []
    hole_counts = Counter()
    for day in tqdm(cfg.period(args.period).days(), unit="day"):
        df = read_zip(raw_zip(spec, cfg.venue, symbol, day.isoformat()), "aggTrades")
        chain = diagnose_chain_breaks(df)
        distribution = chain.pop("hole_distribution")
        hole_counts.update(distribution.to_dict())
        chain["day"] = day.isoformat()
        chain_reports.append(chain)
        r, g = check_aggtrades(df, day, symbol, args.min_gap_s)
        r.update(reconcile_klines_daily(df.drop_duplicates(), month_klines(cfg.venue, symbol, day.strftime("%Y-%m")), day))
        # Continuity across files: the first fill of today must follow the last fill of yesterday
        r["cross_day_hole"] = 0 if prev_last is None else int(df.first_id.min() - prev_last - 1)
        prev_last = int(df.last_id.max())
        reports.append(r)
        gaps.append(g)

    chain_summary = pd.DataFrame(chain_reports)
    total_columns = ["chain_breaks", "forward_holes", "overlaps_or_reversals", "skipped_ids"]
    print("\nWithin-day raw ID connections:")
    print(chain_summary[total_columns].sum().to_string())
    print("largest hole:", int(chain_summary["largest_hole"].max()))

    distribution = pd.Series(hole_counts, dtype = "int64").sort_index()
    distribution.index.name = "skipped_ids_per_break"
    distribution.name = "break_count"
    print("\nForward-hole size distribution:")
    print(distribution.to_string())
    rep = pd.DataFrame(reports)
    gap = pd.concat(gaps, ignore_index=True)

    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"aggTrades_{symbol}_{args.period}"
    rep.to_csv(OUT / f"{stem}_days.csv", index=False)
    gap.to_csv(OUT / f"{stem}_gaps.csv", index=False)

    print(f"{len(rep)} days, {rep.rows.sum():,} aggTrades\n")
    print(rep[ISSUES].sum().to_string())
    worst = rep.loc[rep.max_gap_s.idxmax()]
    print(f"\nsilence between trades: worst daily p99.9 {rep.p999_gap_s.max():.2f}s | "
          f"longest {worst.max_gap_s:.2f}s on {worst.day}")
    print(f"time gaps > {args.min_gap_s}s: {int((gap.kind == 'time_gap').sum())} | "
          f"id gaps: {int((gap.kind == 'id_gap').sum())}")
    kl = ["volume_ok", "taker_buy_ok", "high_ok", "low_ok"]
    print(
        f"\nklines, daily: {int(rep[kl].all(axis=1).sum())}/{len(rep)} days ok | max |diff| volume {rep.volume_diff_btc.abs().max():.3f} BTC, "
        f"taker buy {rep.taker_buy_diff_btc.abs().max():.3f} BTC | kline minutes {rep.kline_minutes.min()}-{rep.kline_minutes.max()} | "
        f"off-book ids inside ranges {rep.ids_minus_fills.sum():,}"
    )
    print("reports written to", OUT)


@lru_cache(maxsize=2)
def month_klines(venue: str, symbol: str, month: str) -> pd.DataFrame:
    return read_zip(raw_zip(DatasetSpec("klines", "monthly", "1m"), venue, symbol, month), "klines")


if __name__ == "__main__":
    main()