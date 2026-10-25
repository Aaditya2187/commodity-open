# Frozen model specification: gap-v1 (Task 2)

Code: `submission/model.py` (this spec and that file are frozen together; their sha256 hashes are
in `PREREGISTRATION.sha256`). `submission/run.py` is a byte-identical copy of the template's run.py.

| Item | Specification |
|---|---|
| Decision instant | 08:30 IST pre-open of every MCX session (loop default; no `instants`) |
| Assets | gold, silver, copper, crude; each asset the loop designates at that pre-open |
| Entry anchor | `PriceSeries.price_at` on the horizon-5 designated contract, built by `loop.price_view(pit, as_of, lookback_sessions=10, quotes=True)`: the scorer's own code and convention. `anchor` = that price's availability instant (the tick capture or settlement publication) |
| Overseas series | `macro/hl_candles_1h`, gold→`xyz:GOLD`, silver→`xyz:SILVER`, copper→`xyz:COPPER`, crude→`xyz:CL`. A candle is usable only if `close_utc` and `available_utc` are before the signal instant (read through PointInTime at the signal instant) |
| Gap | ref0 = close of last candle with close ≤ anchor; ref1 = close of last candle with close < signal; gap = ref1/ref0 − 1 |
| Direction | up if gap > 0, down if gap < 0 |
| Horizons issued | 3 and 5, both, on every signalling instant, regardless of run.py's `--horizons` (default 5,10). A Task 2 horizon need not be one run.py asked for; the model issues both on its first call at each instant |
| expected_pct | 2 × asset threshold (fixed placeholder, not fitted) |
| Band | p10 = 0.999 × threshold, p90 = p10 + 12 × threshold × (1 − 1e-9), just inside `BAND_WIDTH_CAP` |
| invalidation_pct | asset threshold (recorded; does not affect Task 2 scoring) |
| No signal | `{"reason": ...}` when there is no designated contract, entry price or candle, no candle closed between the anchor and the signal, or a zero gap. One `no_signal` row per asset and session (loop convention) |
| fit | stores the client; fits nothing (`TRAINING_DATA_CUTOFF`: none). Unaffected by the unresolved forward cutoff question (CO-0039) |
| update | counts rows and changes nothing. **Consequently learning ≡ frozen, and "learning beats frozen" and the improvement score are expected to fail.** This is deliberate: experiment 03 found no adaptable relationship, and the pre-declared rule forbids proposing one without evidence |
| Randomness | none; `SEED = 20261025` recorded only |

Known limitations: perpetual-vs-futures basis (copper: COMEX-linked perp vs LME-linked MCX), USDINR
overnight move ignored, settlement-as-anchor timing, and weekend gaps. In forward provisional rows
the 02:00–02:59 UTC candle is not yet in the 08:00 IST pack; the final scored file is built from a
complete pack.
