"""Step 1: lossless loader: raw zip -> typed DataFrame. Types change, rows never do."""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from orderflow.data.catalog import DatasetSpec, RemoteFile
from orderflow.data.download import RAW_ROOT, local_path

# Column names and dtypes, in file order. bookTicker is added in step 4, once its header is confirmed.
SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "aggTrades": [("agg_id", "int64"), ("price", "float64"), ("qty", "float64"),
                  ("first_id", "int64"), ("last_id", "int64"), ("ts", "int64"),
                  ("is_buyer_maker", "bool")],
    "trades": [("id", "int64"), ("price", "float64"), ("qty", "float64"),
               ("quote_qty", "float64"), ("ts", "int64"), ("is_buyer_maker", "bool")],
    "klines": [("open_time", "int64"), ("open", "float64"), ("high", "float64"),
               ("low", "float64"), ("close", "float64"), ("volume", "float64"),
               ("close_time", "int64"), ("quote_volume", "float64"), ("count", "int64"),
               ("taker_buy_volume", "float64"), ("taker_buy_quote_volume", "float64"),
               ("ignore", "float64")],
    "fundingRate": [("calc_time", "int64"), ("funding_interval_hours", "int64"),
                    ("last_funding_rate", "float64")],
}
TIME_COLS = {"aggTrades": ["ts"], "trades": ["ts"],
             "klines": ["open_time", "close_time"], "fundingRate": ["calc_time"]}

MS_RANGE = (10**12, 10**14)   # epoch milliseconds: years 2001 .. 5138
US_RANGE = (10**15, 10**17)   # epoch microseconds: same years


class SchemaError(ValueError):
    """File layout does not match the expected schema."""


class TimestampUnitError(ValueError):
    """Timestamp unit cannot be inferred unambiguously."""


def to_microseconds(t: np.ndarray) -> tuple[np.ndarray, str]:
    """Normalize epoch timestamps to int64 microseconds; the unit is inferred from magnitude."""
    if t.size == 0:
        return t.astype("int64"), "empty"
    lo, hi = int(t.min()), int(t.max())
    if MS_RANGE[0] <= lo and hi < MS_RANGE[1]:
        return t.astype("int64") * 1000, "ms"
    if US_RANGE[0] <= lo and hi < US_RANGE[1]:
        return t.astype("int64"), "us"
    raise TimestampUnitError(f"cannot infer unit: min={lo}, max={hi} (mixed units or seconds?)")


def _first_line(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != 1:
            raise SchemaError(f"{path.name}: expected exactly 1 CSV inside, found {names}")
        with z.open(names[0]) as f:
            return f.readline().decode().strip()


def _has_header(first_line: str) -> bool:
    return not first_line.split(",")[0].strip().lstrip("-").isdigit()


def read_zip(path: Path, dataset: str) -> pd.DataFrame:
    """Parse one raw zip. Raises on schema drift, unparseable values, or ambiguous timestamps."""
    schema = SCHEMAS[dataset]
    first = _first_line(path)
    n_fields = len(first.split(","))
    if n_fields != len(schema):
        raise SchemaError(f"{path.name}: {n_fields} columns, expected {len(schema)} for {dataset}")

    df = pd.read_csv(
        path,
        header=0 if _has_header(first) else None,
        names=[c for c, _ in schema],
        dtype=dict(schema),
        true_values=["true", "True", "TRUE"],
        false_values=["false", "False", "FALSE"],
        on_bad_lines="error",   # a malformed row stops everything instead of being skipped
    )
    units = {}
    for col in TIME_COLS[dataset]:
        values, unit = to_microseconds(df[col].to_numpy())
        df[col] = values
        units[col] = unit
    df.attrs.update(source=str(path), dataset=dataset, ts_units_in_file=units)
    return df


def raw_zip(spec: DatasetSpec, venue: str, symbol: str, period: str, root: Path = RAW_ROOT) -> Path:
    """Local path of a raw zip, e.g. raw_zip(DatasetSpec('aggTrades', 'daily'), 'futures/um', 'BTCUSDT', '2024-08-05')."""
    key = f"{spec.folder(venue, symbol)}{symbol}-{spec.interval or spec.name}-{period}.zip"
    return local_path(RemoteFile(key, 0, period), root)