from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

BASE_URL = "https://data.binance.vision"
LIST_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
_PERIOD_RE = re.compile(r"-(\d{4}-\d{2}(?:-\d{2})?)\.zip$")

@dataclass(frozen=True)
class DatasetSpec:
    name: str # server folder: aggTrades, trades, klines, fundingRate, bookTicker
    freq: str
    interval: str | None = None # 1m for example

    @property
    def label(self) -> str:
        return f"{self.name}-{self.interval}" if self.interval else self.name

    def folder(self, venue: str, symbol: str) -> str:
        parts = ["data", venue, self.freq, self.name, symbol] + ([self.interval] if self.interval else [])
        return "/".join(parts) + "/"

    def year_prefix(self, venue: str, symbol: str, year: int) -> str:
        return f"{self.folder(venue, symbol)}{symbol}-{self.interval or self.name}-{year}"

@dataclass(frozen=True)
class RemoteFile:
    key: str
    size: int
    period: str #"2024-08-05" (daily) or "2024-08" (monthly)

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.key}"


def _get(session: requests.Session, params: dict, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            r = session.get(LIST_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("Unreachable")

def list_keys(prefix: str, session: requests.Session) -> list[tuple[str, int]]:
    out, marker = [], ""
    while True:
        root = ET.fromstring(_get(session, {"prefix": prefix, "marker": marker}))
        for el in root.iter():
            el.tag = el.tag.rpartition("}")[2]
        page = [(c.findtext("Key"), int(c.findtext("Size"))) for c in root.iter("Contents")]
        out += page
        if root.findtext("IsTruncated") == "false" or not page:
            return out
        marker = page[-1][0]

def list_files(spec: DatasetSpec, venue: str, symbol: str, years: list[int],
               session: requests.Session | None = None) -> tuple[list[RemoteFile], set[str]]:
    session = session or requests.Session()
    zips, cksums = [], set()
    for y in years:
        for key, size in list_keys(spec.year_prefix(venue, symbol, y), session):
            m = _PERIOD_RE.search(key.removesuffix(".CHECKSUM"))
            if m is None:
                continue
            if key.endswith(".zip"):
                zips.append(RemoteFile(key, size, m.group(1)))
            elif key.endswith(".CHECKSUM"):
                cksums.add(m.group(1))
    return zips, cksums
