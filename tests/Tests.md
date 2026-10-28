# Step 2 — Testing Statistical Code (bad-print detector tests)

## Why it's different
On real data there is no "right answer" for which trades should be flagged.
→ Test on **synthetic data where the answer is known by construction** (one spike, one real move).

## Five kinds of tests
| kind | idea | in this step |
|---|---|---|
| known-answer | exact outputs predicted by the theory | spike → flag at `[700]`; real move → `range(700, 800)` (N/2 swamping) |
| metamorphic | relation between two runs, not the output itself | change prices after t ⇒ outputs before t unchanged (causality) |
| parameter logic | each condition really controls the decision | +5 bp: z ≈ 200 but not flagged; flagged with `min_dev_bp=1` |
| boundary | exact edges, where off-by-ones live | warm-up exactly 2N = 400; unsorted input raises |
| contract | function has no side effects | input DataFrame unchanged |
| 2026-10-28 | T000i | Outage threshold from dev-slice silence distribution (47.8M inter-trade gaps): p99 0.64 s, p99.9 1.33 s, p99.99 2.22 s, p99.999 3.31 s, max 7.64 s; 24 silences > 5 s, none > 10 s; smooth tail, longest silences on weekend evenings, no isolated outliers. Rule fixed before looking: T = first of 10/15/30/60 s that is at least 3 x the tail end. Decision: outage = silence > 30 s (none in the dev slice). To recheck on the full research period. Also: median gap 0 s, most consecutive aggTrades share a millisecond (sweeps across price levels). | dev_slice | — | — |

```
causality:  ∀t,  p_{>t} changes  ⇒  outputs_{<t} unchanged
```

## Rules
- **Fixed seed** (`default_rng(0)`): a flaky statistical test is worse than none.
- **Check positions, not counts** (`np.flatnonzero`): 100 wrong flags would pass a count check.
- **Assert the reason too**: check `z > 10` before checking "not flagged", or a broken detector that never flags would pass.
- **Exact equality is fine** on deterministic synthetic data when the numbers come from the math.
- **Known-answer tests encode parameters** (100 = N/2): changing a cleaning parameter breaks them on purpose → update test + research log.

## Mutation testing (testing the tests)
Introduce a plausible bug, confirm a test fails.

| mutation | meaning | caught by |
|---|---|---|
| `rolling(..., center=True)` | **lookahead** (uses trades i+1 … i+99) | causality, known-answer, warm-up |
| remove `.shift(1)` on reference | off-by-one, not lookahead (trade i is known at time i) | warm-up (399 instead of 400) |
| `np.fmax` instead of `np.maximum` | fake z-scores during warm-up | warm-up |

Each test catches different bugs; the exact warm-up length 2N is a fingerprint of the two `shift(1)`.

## Status
`tests/test_validation.py`: 16 tests (12 reconciliation + 4 bad prints).
Next: wire `summarize_flags` into `validate_raw.py`, save flagged trades, first run on 2024-08-05.