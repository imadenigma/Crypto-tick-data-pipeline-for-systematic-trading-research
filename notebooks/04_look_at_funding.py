import zipfile

import numpy as np
import pandas as pd

path = "/home/imad/PycharmProjects/orderflow/data/raw/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2024-08.zip"

# 1. Raw text: confirm the header and column order before trusting any positions below
with zipfile.ZipFile(path) as z:
    with z.open(z.namelist()[0]) as f:
        for _ in range(4):
            print(f.readline().decode().strip())

first = pd.read_csv(path, nrows=1, header=None).iloc[0, 0]
has_header = not str(first).isdigit()
df = pd.read_csv(path, header=0 if has_header else None)
print("header:", has_header, "| columns:", df.columns.tolist())

t = df.iloc[:, 0].astype("int64")        # first column: funding time, ms UTC
rate = df.iloc[:, -1].astype(float)      # last column: the funding rate

# 2. Timing: derive the interval from the data instead of assuming 8h
ts = pd.to_datetime(t, unit="ms", utc=True)
gap_h = float(np.median(np.diff(t.values))) / 3.6e6
print(len(df), "events | median gap", gap_h, "h | expected", int(31 * 24 / gap_h))
print("hours of day:", sorted(ts.dt.hour.unique()))
print("offsets from the exact hour (ms):", sorted((t % 3_600_000).unique())[:5])

# 3. Size of the cost
print(f"per event: mean {rate.mean():.5%} | min {rate.min():.5%} | max {rate.max():.5%}")
print("share of negative events:", round(float((rate < 0).mean()), 3))
print(f"August total paid by a 1x long: {rate.sum():.4%} of notional")
print(f"annualized at the August mean: {rate.mean() * 365 * 24 / gap_h:.2%}")
print(f"one taker round trip (0.10%) = {0.001 / rate.abs().mean():.1f} average funding events")