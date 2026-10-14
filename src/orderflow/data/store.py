from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from orderflow.config import REPO_ROOT

INTERIM_ROOT = REPO_ROOT / "data" / "interim"

def interim_path(venue: str, symbol: str, dataset: str, day: str, root: Path = INTERIM_ROOT) -> Path:
    """e.g. data/interim/futures/um/BTCUSDT/aggTrades/2024-08-05.parquet"""
    return root / venue / symbol / dataset / f"{day}.parquet"

def write_interim(df: pd.DataFrame, path: Path, meta: dict) -> int: #write df to parquet file with metadata
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), b"orderflow": json.dumps(meta).encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.part")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)
    return path.stat().st_size

def read_meta(path: Path) -> dict:
    return json.loads(pq.read_schema(path).metadata[b"orderflow"])

def code_version() -> str:

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()

    return git("rev-parse", "--short", "HEAD") + (
        "+dirty" if git("status", "--porcelain", "--untracked-files=no") else "")