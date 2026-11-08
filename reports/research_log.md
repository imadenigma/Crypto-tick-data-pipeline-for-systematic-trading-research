    # Research log
Every idea tried goes here, failures included. 

| date | id | hypothesis / change | period used | result (IC, SR, ...) | kept? |
|------|----|---------------------|-------------|----------------------|-------|
| 2026-09-29 | T000 | Scope fixed in configs/dataset.yaml | — | — | — |
| 2026-09-29 | T000b | Lockbox exposure: scope output ranked 2026-02-05/06 as highest-activity days (file sizes only, no prices/returns). Script now ranks research days only. | lockbox | — | — |
| 2026-10-09 | T000d | Pre-registration, bad-print flags on dev slice. Spec: reference = median of log price over previous N=200 trades; scale = 1.4826 x median of abs(residual) over previous N, floored at one tick; flag if z > 10 and deviation > 10 bp; first 2N trades unscored. Predictions: (1) most flags on 2024-08-05; (2) that day mostly down episodes; (3) flags < 0.5% of scored trades; (4) most flags in runs, not isolated spikes. Decision rule: raise min_dev_bp if calm days show runs on moves < 20 bp; lower k if a clear snap-back wick >= 30 bp is missed; otherwise keep defaults; at most one change. | dev_slice | — | — |
| 2026-10-09 | T000e | Dev slice downloaded for BTCUSDT 2024-08: 31 aggTrades, 31 raw trades, 1 klines (1m), 1 fundingRate = 64 zips, all SHA-256 verified against Binance checksums. | dev_slice | — | — |
| 2026-10-17 | T000g | Dev-slice cleaning run: 47,852,373 rows in = out, 0 exact duplicates, 12,408 off-tick kept; interim Parquet = 1.84 x zip (projected ~57 GB for BTC research period). Finding: 6,557 id gaps (14,005 ids) in aggTrades, 63% on 08-05; rank corr with daily range 0.59 vs trade count 0.39; on 08-05, 98% of gaps fall in 4 hours. Raw trades lack the same ids, plus 8,333 ids inside 2,680 aggTrade ranges whose quantities still match the raw fills exactly, so those ids were never fills of these aggTrades. Interpretation: ids used by trades neither archive publishes, consistent with Binance's documented exclusion of insurance-fund and ADL trades; not missing market data. Decision: keep hole_before as annotation, no unknown-interval masking; fill counts from id ranges overstate by ~0.06% on stress days. 2 raw fills (0.092 BTC, 08-05 02:41:39) absent from aggTrades, unexplained, negligible. | dev_slice | — | — |
| 2026-10-17 | T000h | Finding: an aggTrade's timestamp is its first fill; 25-27% of fills are stamped later, by up to exactly 100 ms (08-05: p50 8 ms; 08-22: p50 15 ms; p99.9 = max = 100 ms on both). Aggregation spans a window of up to 100 ms, so one aggTrade likely merges several taker orders at the same price and side. Decision: treat aggTrade information as known at ts + 100 ms in all features and labels. Corrects the step-0 rationale "one aggTrade = one aggressor decision". | dev_slice | — | — |
| 2026-11-08 | T000c | bookTicker BTCUSDT only covers 2023-05-16 to 2024-03-30 (320 contiguous days, 52.6 GB): inside the research period, not covering the dev slice. Decision: main features from trades only (all 1,704 days); true OFI as a sub-study on that window; spread calibration for step 9 costs from it. Limitation: the window covers only quiet 2023 and the early-2024 rally. (Decided 2026-09-29, logged late.) | research | — | — |
| 2026-11-08 | T000f | Finding: 12,408 of 47,852,373 aggTrades in Aug 2024 (0.026%) printed off the 0.1 tick, all between 08-04 and 08-16 (max daily share 0.12% on 08-06). Pattern: 110 levels on a geometric ladder (ratio 1.000808, ~8.08 bp), mostly 0.003 BTC and 1 fill, resting side (price falling through a level: taker sold 99.7%; rising: taker bought 99.2%), 98.9% priced between neighbouring trades. Interpretation: genuine executions of one automated grid strategy whose prices were not rounded to the tick; how such orders reached the book is unknown. Decision: keep rows, annotate off_tick column, stop only if more than 10% of a day's prices are off-tick (a real 0.01 tick would give ~90%). Evidence: reports/data_quality/aggTrades_BTCUSDT_dev_slice_off_tick.csv. (Decided 2026-10-10, logged late.) | dev_slice | — | — |
| 2026-11-08 | T000i | Outage threshold from dev-slice silence distribution (47.8M inter-trade gaps): p99 0.64 s, p99.9 1.33 s, p99.99 2.22 s, p99.999 3.31 s, max 7.64 s; 24 silences > 5 s, none > 10 s; smooth tail, longest silences on weekend evenings, no isolated outliers. Rule fixed before looking: T = first of 10/15/30/60 s that is at least 3 x the tail end. Decision: outage = silence > 30 s (none in the dev slice); recheck on the full research period. Also: median gap 0 s, most consecutive aggTrades share a millisecond (sweeps across price levels). (Decided 2026-10-28, logged late.) | dev_slice | — | — |
| 2026-11-08 | T000j | Idea, not a trial (nothing tested): in Aug 2024, bad-print flags and snap-back bursts concentrate in 23 minutes; three match scheduled US macro releases: 08-14 12:30 UTC (July CPI, 08:30 ET), 08-08 12:31 (weekly jobless claims, 08:30 ET), 08-05 14:00 (ISM services, 10:00 ET); 08-05 13:37 is 7 min after the US equity open. Hypothesis for a later event study: spreads, trade imbalance and flags around scheduled releases. Release times known in advance, so conditioning on them is causal. Requires an official release calendar for 2022-2025 and a pre-registration before any test. | dev_slice | — | — |
| 2026-11-08 | T000k | Outcome of T000d (bad-print pre-registration, dev slice). P1 wrong: most flags on 08-08 (984), 08-05 only 9; the detector measures surprise relative to the recent regime, not volatility level. P2 right but weak (08-05: 2 down / 1 up episodes). P3 right but uninformative (0.0029% vs < 0.5%; threshold taken from the suggested template). P4 right (96.3% of flags in runs of 20+; 1 isolated spike in 20 episodes). Rule R1 not triggered (0 runs on the 5 calmest days). Rule R2 apparently triggered (1,467 unflagged snap-back candidates >= 30 bp), but 87% sit in 10 minutes that are all two-sided spread blowouts (fresh trade-implied spread 42-162 bp, normal ~0.02 bp): bid-ask bounce, not missed one-sided wicks (classification at minute level). Decision: keep defaults (N=200, k=10, min_dev 10 bp), no change. Limitation: the median/MAD detector flags the start of a two-sided burst, then goes blind once its window splits between both sides; trades alone cannot separate a blowout from a jump, and no quotes exist for Aug 2024. Consequences: realized vol on bars, not ticks ; conservative fill rules . | dev_slice | — | — |
# Typical Signature of a *sweep* (one big market order or liquidation eating several price levels):
    - Many aggTrades with the same timestamp (same ms)
    - Prices walking in one direction (one or several ticks per row)
    - is_buyer_maker = True for all trades (aggressor is the same side as the order book imbalance)
    - Then the price snaps back within a few trades or it stays at the new level (a real move, a run of abt 100 flags)

after this: 
100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 31/31 [01:05<00:00,  2.12s/day]
31 days, 47,852,373 aggTrades

unsorted_ids            0
dup_ids                 0
conflicting_dups        0
agg_id_jumps            0
chain_breaks         6557
missing_fills       14005
bad_ranges              0
ts_backwards            0
out_of_day              0
nonpositive             0
off_tick            12408
off_step                0
cross_day_hole          0

silence between trades: worst daily p99.9 2.49s | longest 7.64s on 2024-08-31
time gaps > 10.0s: 0 | id gaps: 6557

# Interpretation of the results
Binance gave every consecutive aggTrade record, but inside the underlying raw-trade-ID sequence, there appear to be gaps. (CHECKSUM verification is done already so the data is not corrupted)

