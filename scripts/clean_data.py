from __future__ import annotations

import argparse
from inspect import signature

import pandas as pd
from tqdm import tqdm

from orderflow.config import DEFAULT_CONFIG, REPO_ROOT, load_config
from orderflow.data.catalog import DatasetSpec
from orderflow.data.load import raw_zip, read_zip
from orderflow.data.store import code_version, interim_path, write_interim
from orderflow.data.validate import MAX_OFF_TICK_SHARE, clean_aggtrades, flag_bad_prints

OUT = REPO_ROOT / "reports" / "data_quality"

def used_params() -> dict:
    p = {n: v.default for n, v in signature(flag_bad_prints).parameters.items() if v.default is not v.empty}
    return {**p, "max_off_tick_share": f"{MAX_OFF_TICK_SHARE:.2f}"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="dev_slice")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()
    cfg = load_config(args.config)
    symbol = args.symbol or cfg.primary_symbol
    spec, params = DatasetSpec("aggTrades", "daily"), used_params()
    base = {"dataset": "aggTrades", "symbol": symbol, "params": params, "code": code_version()}
    rows, tail = [], None
    for day in tqdm(cfg.period(args.period).days(), unit="day"):
        d_iso = day.isoformat()
        src = raw_zip(spec, cfg.venue, symbol, d_iso)
        out, stats = clean_aggtrades(read_zip(src, "aggTrades"), symbol, tail, window=params["window"])
        size = write_interim(out, interim_path(cfg.venue, symbol, "aggTrades", d_iso), {**base, "day": d_iso, "raw_zip": src.name, "stats": stats})
        rows.append({"day": d_iso, **stats, "zip_bytes": src.stat().st_size, "parquet_bytes": size})
        tail = out.tail(2 * params["window"])
    rep = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    rep.to_csv(OUT / f"aggTrades_{symbol}_{args.period}_cleaning.csv", index=False)
    t = rep.drop(columns=["day", "max_gap_s"]).sum()
    if t.rows_in != t.rows_out + t.dropped_exact_dups:
        raise RuntimeError("accounting identity broken over the period")
    print(f"{len(rep)} days | rows in {t.rows_in:,} = out {t.rows_out:,} + exact duplicates {t.dropped_exact_dups:,}")
    print(f"id gaps {t.id_gaps:,} | missing fills {t.missing_fills:,} | off-tick {t.off_tick:,} | "
          f"unscored {t.unscored:,} | code {base['code']}")
    print(f"zip {t.zip_bytes / 1e9:.2f} GB -> parquet {t.parquet_bytes / 1e9:.2f} GB "
          f"(x{t.parquet_bytes / t.zip_bytes:.2f})")
if __name__ == "__main__":
    main()