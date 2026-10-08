from __future__ import annotations

import argparse

import pandas as pd
from tqdm import tqdm

from orderflow.config import DEFAULT_CONFIG, REPO_ROOT, load_config
from orderflow.data.catalog import DatasetSpec
from orderflow.data.load import raw_zip, read_zip
from orderflow.data.validate import check_aggtrades

OUT = REPO_ROOT / "reports" / "data_quality"
ISSUES = ["unsorted_ids", "dup_ids", "conflicting_dups", "agg_id_jumps", "chain_breaks",
          "missing_fills", "bad_ranges", "ts_backwards", "out_of_day", "nonpositive",
          "off_tick", "off_step", "cross_day_hole"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--period", default="dev_slice")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--min-gap-s", type=float, default=10.0)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()

    cfg = load_config(args.config)
    symbol = args.symbol or cfg.primary_symbol
    spec = DatasetSpec("aggTrades", "daily")
    reports, gaps, prev_last = [], [], None

    for day in tqdm(cfg.period(args.period).days(), unit="day"):
        df = read_zip(raw_zip(spec, cfg.venue, symbol, day.isoformat()), "aggTrades")
        r, g = check_aggtrades(df, day, symbol, args.min_gap_s)
        # Continuity across files: the first fill of today must follow the last fill of yesterday
        r["cross_day_hole"] = 0 if prev_last is None else int(df.first_id.min() - prev_last - 1)
        prev_last = int(df.last_id.max())
        reports.append(r)
        gaps.append(g)

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
    print("reports written to", OUT)


if __name__ == "__main__":
    main()