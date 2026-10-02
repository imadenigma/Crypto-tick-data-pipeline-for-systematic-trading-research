from __future__ import annotations

import argparse

from orderflow.config import DEFAULT_CONFIG, load_config
from orderflow.data.catalog import DatasetSpec, list_files
from orderflow.data.download import RAW_ROOT, download_many


def main():
    ap = argparse.ArgumentParser(description="Download data")
    ap.add_argument("--dataset", required=True, help="aggTrades | trades | klines | fundingRate | bookTicker")
    ap.add_argument("--symbol", default=None, help="symbol")
    ap.add_argument("--period", default="dev_slice", help="dev_slice | research | lockbox | full")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()

    config = load_config(args.config)
    item = next((s for s in config.scope if s.dataset == args.dataset), None)
    if item is None:
        raise SystemExit(f"{args.dataset!r} is not in the scope of {args.config}")

    symbol = args.symbol or config.primary_symbol
    spec = DatasetSpec(item.dataset, item.freq, item.interval)
    period = config.period(args.period)
    wanted = set(period.labels(item.freq))

    files, _ = list_files(spec, config.venue, symbol, period.years())
    remotes = sorted((f for f in files if f.period in wanted), key=lambda f: f.period)
    missing = wanted - {f.period for f in remotes}
    print(
        f"{spec.label} {symbol} {args.period}: {len(remotes)} files, "
        f"{sum(f.size for f in remotes) / 1e9:.2f} GB -> {RAW_ROOT}"
    )
    if missing:
        print(
            f"WARNING: {len(missing)} periods not on the server, e.g. {sorted(missing)[:3]}"
        )
    print(download_many(remotes, workers=args.workers))

if __name__ == "__main__":
    main()
