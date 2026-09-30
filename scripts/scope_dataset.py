from __future__ import annotations

import argparse
import shutil

import requests

from orderflow.config import DATA_ROOT, DEFAULT_CONFIG, load_config
from orderflow.data.catalog import DatasetSpec, list_files

GB = 1e9

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    cfg = load_config(ap.parse_args().config)
    session, total = requests.Session(), 0
    research_days = set(cfg.research.labels("daily"))
    for item in cfg.scope:
        spec = DatasetSpec(item.dataset, item.freq, item.interval)
        period = cfg.period(item.period)
        expected = set(period.labels(item.freq))
        for symbol in item.symbols:
            files, csums = list_files(spec, cfg.venue, symbol, period.years(), session)
            found = {f.period: f for f in files if f.period in expected}
            missing = sorted(expected - found.keys())
            no_ck = sorted(found.keys() - csums)
            size = sum(f.size for f in found.values())
            total += size
            print(f"{spec.label:<12} {symbol:<8} {item.period:<9} {len(found):>5}/{len(expected):<5} "
                  f"{size / GB:7.2f} GB {size / max(len(found), 1) / 1e6:7.1f} MB/file  "
                  f"missing={len(missing)} no_checksum={len(no_ck)}")
            if missing:
                print(f"    missing: {missing[:4]}{' ...' if len(missing) > 4 else ''} (last: {missing[-1]})")
            if item.freq == "daily":
                visible = [f for f in found.values() if f.period in research_days]
                top = sorted(visible, key=lambda f: f.size, reverse=True)[:3]
                if top:
                    print("    largest research files: " + ", ".join(f"{f.period}={f.size / 1e6:.1f} MB" for f in top))

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(DATA_ROOT).free
    print(f"\nzipped total {total / GB:.1f} GB | budget x2 {2 * total / GB:.1f} GB | "
           f"free at {DATA_ROOT}: {free / GB:.1f} GB")
    if 2 * total > free:
        print("WARNING: not enough disk for the full scope; point ORDERFLOW_DATA at a bigger drive.")
if __name__ == "__main__":
    main()


