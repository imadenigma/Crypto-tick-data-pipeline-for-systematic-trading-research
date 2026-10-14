    # Research log
Every idea tried goes here, failures included. Step 8 counts these rows as N for the Deflated Sharpe Ratio.

| date | id | hypothesis / change | period used | result (IC, SR, ...) | kept? |
|------|----|---------------------|-------------|----------------------|-------|
| 2026-09-29 | T000 | Scope fixed in configs/dataset.yaml | — | — | — |
| 2026-09-29 | T000b | Lockbox exposure: scope output ranked 2026-02-05/06 as highest-activity days (file sizes only, no prices/returns). Script now ranks research days only. | lockbox | — | — |
| 2026-10-09 | T000d | Pre-registration, bad-print flags on dev slice. Spec: reference = median of log price over previous N=200 trades; scale = 1.4826 x median of abs(residual) over previous N, floored at one tick; flag if z > 10 and deviation > 10 bp; first 2N trades unscored. Predictions: (1) most flags on 2024-08-05; (2) that day mostly down episodes; (3) flags < 0.5% of scored trades; (4) most flags in runs, not isolated spikes. Decision rule: raise min_dev_bp if calm days show runs on moves < 20 bp; lower k if a clear snap-back wick >= 30 bp is missed; otherwise keep defaults; at most one change. | dev_slice | — | — |
| 2026-10-09 | T000e | Dev slice downloaded for BTCUSDT 2024-08: 31 aggTrades, 31 raw trades, 1 klines (1m), 1 fundingRate = 64 zips, all SHA-256 verified against Binance checksums. | dev_slice | — | — |

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