# Step 2 — Data Validation & Cleaning (closed)

> Dev slice: BTCUSDT USD-M perp, Aug 2024, 31 days, **47,852,373 aggTrades**.
> Code: `src/orderflow/data/{validate,store}.py`, `scripts/{validate_raw,clean_data}.py`.
> Tests: `tests/test_{validation,cleaning,store}.py` (26 passing). Log rows: T000d to T000l.

## Principles
- **Validation ≠ cleaning**: validation measures and never modifies; cleaning decides, applies, logs.
- **Accounting identity**: `rows_in = rows_out + Σ rows_dropped(reason)`, checked per day and per period.
- **Cleaning rules are parameters**: fixed on the dev slice before any signal, from data properties only, logged.
- **Flag, don't delete.** Keep extreme but real data. **Stop** when a human must decide.
- **Causality test**: could a live system have computed this value at that moment?
- **A validator must encode what we learn**: a check that fires on normal data is noise.
- **Errors vs measurements**: `RECON_KEYS` must be 0; measurements may be nonzero and are reported.
- **One source of truth per fact**: constants and lists live next to the code that uses them.

## Pipeline
```
raw zip (SHA-256) → read_zip (lossless, ts in µs) → check_aggtrades (structural metrics)
→ clean_aggtrades (per day, with tail) → write_interim (Parquet + provenance)
```
- **Drop**: exact duplicate rows only (counted).
- **Stop** (`CleaningError`): conflicting duplicates, price/qty ≤ 0, first_id > last_id, qty off step, > 10% of a day's prices off tick.
- **Annotate**: `hole_before`, `gap_s`, `off_tick`. **Flag**: `dev_bp`, `z`, `bad_prints`.
- **Tail**: last 2N cleaned rows of the previous day, so day-by-day = all-at-once (tested).
- **Interim**: `data/interim/futures/um/BTCUSDT/aggTrades/YYYY-MM-DD.parquet`; metadata = source zip, params (read from code defaults), stats, git commit (`+dirty` if uncommitted). Size **1.84 × zip** (~57 GB for the BTC research period).

## Equations
```
hole_j  = first_id[j+1] − last_id[j] − 1           gap_j = (ts[j] − ts[j−1]) / 10⁶ s
mᵢ = median(log p, previous N)   rᵢ = log pᵢ − mᵢ   σᵢ = max(1.4826 · median(|r|, previous N), tick / pᵢ)
zᵢ = |rᵢ| / σᵢ      flag ⇔ zᵢ > 10 AND |rᵢ| > 10 bp      (N = 200; first 2N trades unscored)
trade-implied spread = last taker-buy price − last taker-sell price   (only when both within 3 trades)
Roll (1984): spread ≈ 2 · √(−Cov(Δpₜ, Δpₜ₋₁))
```

## Findings
| id | finding | rule |
|---|---|---|
| T000f | 12,408 off-tick trades (0.026%): one grid bot, geometric ladder 8.08 bp, 0.003 BTC | keep, `off_tick` column; stop only if > 10% of a day |
| T000g | 6,557 id gaps (14,005 ids) + 8,333 ids inside 2,680 aggTrade ranges whose qty still matches: off-book insurance-fund/ADL trades | not missing data; `hole_before` is annotation only; id-range fill counts overstate ~0.06% |
| T000h | aggTrade ts = first fill; 25–27% of fills later, by up to **exactly 100 ms** | aggTrade known at **ts + 100 ms**; reconcile rule: fills in [ts, ts + 100 ms] |
| T000i | silences: p99.9 1.33 s, max 7.64 s, smooth tail; median gap 0 s (sweeps) | outage = silence **> 30 s**; none in Aug 2024; recheck on full period |
| T000j | flag bursts at US macro releases (CPI 08-14, claims 08-08, ISM 08-05) | idea for a later event study, not a trial |
| T000k | 1,405 flags (0.0029%), 96% in runs; P1 wrong; R2 candidates = two-sided spread blowouts (42–162 bp) | keep defaults (N=200, k=10, 10 bp) |
| T000l | candles from raw fills = klines on all 1,440 minutes; klines count = fills, no off-book trades | minute agg-vs-klines is diagnostic only; full period: daily totals check |

## Binance USD-M data facts
- **aggTrade** = same price, same side, up to 100 ms; likely merges several taker orders.
- **Trade ids** are shared with off-book trades, which appear in **no** public dataset.
- **Klines** are built from individual fills at their own time; `count` = number of fills.
- **No bid/ask for Aug 2024** (bookTicker only 2023-05-16 → 2024-03-30). Use trade-implied quotes, calibrated on the bookTicker window.
- **Spread blowouts**: 10 minutes in Aug 2024 with two-sided spreads of 40–160 bp (normal ~0.02 bp).

## Bad-print detector: what it is and isn't
- Measures **surprise relative to the recent regime**, not volatility level (08-08: 984 flags, 08-05 crash: 9).
- Flags the **start** of a two-sided burst, then goes blind once its window splits between both sides.
- Trades alone can't separate a blowout from a jump. Reports may use hindsight; data and features never.

## Testing lessons
- Synthetic data valid by construction, fixed seeds; inject one fault per test.
- Test invariants (accounting, tail equivalence, no side effects), every stop, exact boundaries (100 ms).
- One regression test per real bug (`not tail`, off-tick stop, missing `conflicting_dups`).
- Mutation testing: plant a plausible bug, a test must fail. `match=` on a fragment naming the reason.
- File I/O tests use pytest's `tmp_path`.

## Leakage checklist additions
19. aggTrade ts = first fill → information known at ts + 100 ms.
20. Tick-to-tick returns explode in blowouts → realized vol on bars, not ticks.
21. Flags are blind inside two-sided bursts → step 9 fills use conservative rules, not flags.
22. Hindsight in reports (episodes, snap-backs) never feeds data or features.

## Code conventions
- Column name **`bad_prints`** (plural) everywhere. `tail is None`, never `not tail`.
- `AGG_WINDOW_US = 100_000` · `OUTAGE_GAP_S = 30.0` · `MAX_OFF_TICK_SHARE = 0.10` · `STRUCTURAL_ISSUES` (in validate.py).
- `reconcile_trades` measurements: `aggs_with_inner_gaps`, `inner_missing_ids` (not in `RECON_KEYS`).
