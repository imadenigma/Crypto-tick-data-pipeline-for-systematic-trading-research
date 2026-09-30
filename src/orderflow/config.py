from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("ORDERFLOW_DATA", REPO_ROOT / "data")).expanduser()
DEFAULT_CONFIG = REPO_ROOT / "configs" / "dataset.yaml"

class LockboxError(RuntimeError):
    """Research code touched lockbox dates without an explicit unlock."""

def _to_date(x):
    return x if isinstance(x, date) else date.fromisoformat(str(x))

@dataclass(frozen=True)
class Period:
    start: date
    end: date

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError(f"Empty Period {self.start} .. {self.end}")

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end

    def days(self):
        return [self.start + timedelta(days= i) for i in range((self.end - self.start).days + 1)]

    def months(self):
        return sorted({d.strftime("%Y-%m") for d in self.days()})

    def years(self):
        return list(range(self.start.year, self.end.year + 1))

    def labels(self, freq: str):
        if freq == "daily":
            return [d.isoformat() for d in self.days()]
        if freq == "monthly":
            return self.months()
        raise ValueError(f"Invalid frequency {freq}")

@dataclass(frozen=True)
class ScopeItem:
    dataset: str
    freq: str
    symbols: tuple[str, ...]
    period: str
    interval: str | None = None

@dataclass(frozen=True)
class DatasetConfig:
    venue: str
    primary_symbol: str
    robustness_symbols: tuple[str, ...]
    research: Period
    lockbox: Period
    dev_slice: Period
    scope: tuple[ScopeItem, ...]
    def __post_init__(self):
        if not self.research.end < self.lockbox.start:
            raise LockboxError(f"Research period {self.research} overlaps lockbox {self.lockbox}")
        if not (self.research.contains(self.dev_slice.start) and self.research.contains(self.dev_slice.end)):
            raise ValueError(f"Dev slice {self.dev_slice} is not contained in research period {self.research}")

    def period(self, name:str) -> Period:
        if name == "full":
            return Period(self.research.start, self.lockbox.end)
        return {
            "research": self.research,
            "lockbox": self.lockbox,
            "dev_slice": self.dev_slice,
        }[name]

    def check_not_lockbox(self, start: date, end: date):
        if os.environ.get("ORDERFLOW_UNLOCK_LOCKBOX") == "1":
            return
        if start <= self.lockbox.end and end >= self.lockbox.start:
            raise LockboxError(f"Attempt to access lockbox period {self.lockbox} with {start} .. {end}")

def load_config(path: str | Path = DEFAULT_CONFIG) -> DatasetConfig:
    raw = yaml.safe_load(Path(path).read_text())
    def per(name: str) -> Period:
        return Period(_to_date(raw[name]["start"]), _to_date(raw[name]["end"]))
    return DatasetConfig(
        venue=raw["venue"],
        primary_symbol=raw["symbols"]["primary"],
        robustness_symbols=tuple(raw["symbols"]["robustness"]),
        research=per("research"),
        lockbox=per("lockbox"),
        dev_slice=per("dev_slice"),
        scope=tuple(ScopeItem(**{**s, "symbols": tuple(s["symbols"])}) for s in raw["scope"])
    )