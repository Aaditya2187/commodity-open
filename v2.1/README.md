# Commodity Open 2026 dataset pack v2.1

Four MCX commodity futures (gold, silver, copper, crude oil) with the production feed's captured
quotes, comparator venues, news, feed receipts, and hourly market-state features. Every row carries
the instant it became available to us, or an honest statement that we do not know (see clock quality).

## Terms

The pack, and the second data file that adds the sessions after it, are licensed to registered Commodity Open 2026 teams for use in the challenge only. Until the verdicts are sent they may not be shared outside the team or redistributed in any form. The data comes from the sources named below and in each file's sidecar, and those sources keep their own terms.

## Changes since v2.0.1

- The data now runs to 2026-10-23 (v2.0.1: 2026-09-25), 19 MCX sessions more.

- Tables that gained rows or changed:

| table | rows in v2.0.1 | rows now | rows added |
|---|---:|---:|---:|
| `calendar/release_schedule` | 3,613 | 3,632 | 19 |
| `calendar/release_surprises` | 1,849 | 1,879 | corrected, see Corrections |
| `calendar/release_vintages` | 12,147 | 100,121 | 87,974 |
| `labels/chain_daily` | 202,615 | 205,275 | 2,660 |
| `labels/designations` | 17,496 | 17,724 | 228 |
| `labels/return_targets` | 17,323 | 17,551 | 228 |
| `labels/swing_labels` | 51,969 | 52,653 | 684 |
| `macro/alfred_vintages` | 122,318 | 122,782 | 464 |
| `macro/cot` | 3,492 | 3,508 | 16 |
| `macro/cot_legacy` | 3,492 | 3,508 | 16 |
| `macro/hl_candles_1d` | 1,066 | 1,178 | 112 |
| `macro/hl_candles_1h` | 21,005 | 23,693 | 2,688 |
| `macro/hl_funding` | 25,624 | 28,312 | 2,688 |
| `macro/usdinr` | 1,381 | 1,400 | 19 |
| `mcx/mcx_daily` | 156,409 | 159,529 | 3,120 |
| `mcx/mcx_sessions` | 2,191 | 2,191 | corrected, see Corrections |
| `pack/news/news_clusters` | 89,858 | 166,570 | 76,712 |
| `pack/news/news_memberships` | 177,671 | 436,303 | 258,632 |
| `pack/news/news_rows` | 131,584 | 173,381 | 41,797 |
| `pack/quotes/brent_quotes` | 1,311,278 | 1,724,529 | 413,251 |
| `pack/quotes/comex_delayed_quotes` | 60,957 | 80,825 | 19,868 |
| `pack/quotes/hl_quotes` | 5,139,823 | 6,696,056 | 1,556,233 |
| `pack/quotes/mcx_quotes` | 1,168,993 | 1,532,825 | corrected, see Corrections |
| `pack/quotes/moneyplant_quotes` | 1,247,640 | 1,940,091 | 692,451 |
| `pack/quotes/reference_quotes` | 5,354,590 | 7,110,177 | 1,755,587 |
| `pack/quotes/te_quotes` | 4,171,599 | 5,013,533 | 841,934 |
| `pack/receipts/cot_record_receipts` | 36 | 52 | 16 |
| `pack/receipts/fx_rate_receipts` | 1,300,950 | 1,872,796 | 571,846 |
| `pack/receipts/reference_closes` | 3,066 | 4,126 | 1,060 |
| `pack/state/mcx_hourly_state` | 4,608 | 5,792 | 1,184 |
| `swings/swing_sessions` | 5,832 | 5,908 | corrected, see Corrections |
| `swings/swings` | 2,107 | 2,150 | 43 |

## Rows kept as published

Except the rows the Corrections section names, every row of v2.0.1 is in this release as v2.0.1 published it. Where the build behind this release writes a different row for the same key, the published row stays. These tables hold such rows:

- `calendar/release_schedule.parquet`: 2,727 rows kept as published, differing in source_url (102), capture_path (2,727), notes (617). `capture_path`, `source_url` and `notes` name the capture of the authority's page the row was read from, its address and the wording of its note, which a re-capture replaces.
- `calendar/release_vintages.parquet`: 5,034 rows kept as published, differing in captured_utc (5,034), capture_path (5,034), notes (28). `captured_utc`, `capture_path` and `notes` name the capture the row was parsed from, which a re-capture of the source replaces.
- `labels/designations.parquet`: 128 rows kept as published, differing in horizon_complete (128). `horizon_complete` is false on the last 4, 9 and 19 cutoffs of each asset (horizons of 5, 10 and 20 sessions) when a row is published, and true in a later build once the Bhav Copy of the horizon's last session exists; the label and target rows of those cutoffs are in the release beside the old flag, and nothing in the kit or the scorer reads the flag.
- `macro/alfred_vintages.parquet`: 15 rows kept as published, differing in realtime_end (15); 42 rows kept that the build behind this release does not hold. `realtime_end` is open ended (9999-12-31) when a vintage is published and closed in a later build once a newer vintage of the observation exists; the newer vintage is its own row.
- `macro/cot.parquet`: 3,452 rows kept as published, differing in release_source (3,452), available_source (2,584). `release_source` and `available_source` name the capture of the CFTC release schedule the release instant was read from, which a re-capture replaces.
- `macro/cot_legacy.parquet`: 3,452 rows kept as published, differing in release_source (3,452), available_source (2,608). `release_source` and `available_source` name the capture of the CFTC release schedule the release instant was read from, which a re-capture replaces.

## Corrections

These tables changed or lost rows that the previous release held. Each was declared when this release was assembled and is listed under `corrections` in `MANIFEST.json`.

- `calendar/release_surprises.parquet`: two rows of v2.0.1 carry capture clocks the merged calendar roots correct: eia_wpsr crude_stocks_change for 2026-09-18 moves release_utc, consensus_captured_utc and available_utc from 25 Sep 21:46 to 23 Sep 14:32, two minutes after the 14:30 release the capture records, so the row becomes readable 55 hours earlier than v2.0.1 had it; us_jobless_claims initial_claims for 2026-09-12 moves consensus_captured_utc from 16 Sep 15:02 to 17 Sep 12:02 with release_utc and available_utc unchanged. Both stamps are the clock of the machine that took the capture, which was not checked against a reference
- `mcx/mcx_sessions.parquet`: 43 rows 2026-11-02..2026-12-31 carried the 23:30 IST evening close, clock_quality unvintaged and a note reading the winter close as 23:30; they now carry 23:55 IST, published, because US daylight time ends on 1 Nov 2026. No trading-hours circular covers those dates, so 23:55 is an upper bound and the sidecar records hours_notified false
- `pack/quotes/mcx_quotes.parquet`: three rows were published twice by v2.0.1, two on 2026-09-10 (CRUDEOIL19OCT26FUT, CRUDEOIL19NOV26FUT) and one on 2026-09-16 (SILVER05MAY27FUT); each identical copy is now published once
- `swings/swing_sessions.parquet`: four leg-count columns (turn_count, extreme_count, has_turn, has_extreme) are no longer written: has_turn was stamped at the session close, when the leg it counts was not yet confirmed, and it was true on 2,086 rows

## Layout

```text
pack/v2.1/
  MANIFEST.json      version, build identity, lane status, every file with sha256/bytes/rows/clock quality
  SCHEMA.md          every file and column with meaning and units (generated from the meta sidecars)
  <lane>/<file>.parquet + <file>.meta.json   one sidecar per parquet (its fields are listed in SCHEMA.md)
```

Lanes present: `calendar` (3 files), `labels` (4 files), `macro` (7 files), `mcx` (2 files), `pack` (14 files), `swings` (2 files).

### pack lane files

- `pack/quotes/`: one parquet per raw source family: `mcx_quotes` (Angel SmartAPI MCX front month plus the 2nd/3rd dated contracts captured from 2026-09-04 and available from 2026-09-07, depth, OI, volume), `hl_quotes` (Hyperliquid xyz perpetuals), `moneyplant_quotes` (MT5 COMEX/NYMEX dated futures and XAU/XAG spot), `te_quotes` (Trading Economics live spot/front-month), `comex_delayed_quotes` (Yahoo delayed continuous futures), `brent_quotes` (ICE Brent via TE, yfinance fallback), `reference_quotes` (LBMA fixes, LME cash via westmetall, SHFE/INE via Sina, gold-api, Investing.com).
- `pack/news/`: `news_rows` (every captured headline with fetch clock), `news_clusters` (one row per cluster version), `news_memberships` (which headline sat in which version). Raw captured news only: the organizers' own per-story scores and per-asset news index are not in the pack and will not be, because reading the news is part of the task.
- `pack/receipts/`: `reference_closes` (venue closes the feed captured), `fx_rate_receipts` (USD/INR, USD/CNY the feed applied), `cot_record_receipts`.
- `pack/state/`: `mcx_hourly_state` (one row per asset per asof point: 08:30 IST and every session hour boundary) with `definitions.md` giving every formula, window and mask rule.

### swings lane files

- `swings/swings.parquet`: the organizers' realized swing inventory. One row per completed leg of the percent-threshold zigzag, per asset, with the turn and extreme instants and prices, the signed move, the designated contract, whether the designation rolled inside the leg, and the availability clock of the leg and of the bar that confirmed it. `swings/swing_sessions.parquet` is one row per (asset, session) with the session's own highs and lows and the coverage denominator; `stats.json` and `check.json` are the inventory's descriptive statistics and its invariant checks.
- Task 1's catch rate is scored against these rows, so score yourself against this file rather than against your own re-derivation. The zigzag is documented well enough to rebuild, but a rebuild that differs by a single leg gives a self-score that will not match the official one.

## Clock quality

| class | meaning | PIT clock |
|---|---|---|
| `exact` | we recorded the capture time ourselves, availability known to the second | the table's exact clock: `fetched_utc` unless listed below |
| `published` | the source states an instant; we captured later with unknown latency | the table's published clock: `available_utc` unless listed below |
| `unvintaged` | no credible availability instant | excluded by default; with `include_unvintaged=True` admitted from `raw_file_date + 1 day` where the table has that column, otherwise at every as-of (see Notes on the data) |

Each file's sidecar names its clock columns (`clock_quality.clocks`), and SCHEMA.md repeats them. These tables use others:

- `calendar/release_schedule`: published `release_utc`
- `calendar/release_vintages`: exact `captured_utc`
- `swings/swings`: published `confirm_available_utc`

Every quotes row also carries `raw_file_date`, the UTC day the feed appended it, which bounds availability from above.
The `ts` column of the feed's raw CSVs is the observation clock (`Reading.ts`), which is a capture clock only for some sources and eras; each file's meta `clock_quality.rule` states the mapping used.

## Identifiers and units

- Assets: `gold`, `silver`, `copper`, `crude`. MCX contracts: `mcx:<SYMBOL><DD><MON><YY>FUT` (e.g. `mcx:GOLD05OCT26FUT`). Hyperliquid: `xyz:GOLD`, `xyz:SILVER`, `xyz:COPPER`, `xyz:CL`.
- MCX prices are INR per exchange unit (gold 10 g, silver 1 kg, copper 1 kg, crude 1 bbl); Hyperliquid and comparators are USD; SHFE/INE are CNY per stated unit; LME is USD per tonne.
- Provider identifiers (token, tradingsymbol, expiry, native symbols) are kept exactly as received.

## Point-in-time access

```python
from datetime import datetime, UTC
from swing_dataset.pack.pit import PointInTime

pit = PointInTime('path/to/v2.1')   # the directory the archive extracts to
asof = datetime(2026, 9, 11, 4, 30, tzinfo=UTC)
frames = pit.available(asof)   # strictly-before filter per file
mcx = frames['pack/quotes/mcx_quotes'].collect(columns=['asset', 'contract_id', 'ltp', 'fetched_utc'])
state = frames['pack/state/mcx_hourly_state'].collect()
loose = pit.available(asof, include_unvintaged=True)   # opt-in for unvintaged rows
```

`available(asof)` returns rows whose clock is strictly before `asof`; a state row stamped `asof_utc = T` is therefore returned for any query later than `T`.

## Notes on the data

Unvintaged rows. With `include_unvintaged=True`, a row of an unvintaged table is admitted from `raw_file_date + 1 day` where the table has a `raw_file_date` column (the quote tables). Tables without that column (`release_schedule`, `release_vintages`, `alfred_vintages`, `news_memberships`) admit their unvintaged rows at every as-of, whatever their own `available_utc` says, so an opt-in read can return rows whose clock is after the as-of or empty. Drop such rows before use. The default read never returns them.

`release_surprises` needs no opt-in because its rows are classed by the availability of the actual. Its consensus values were captured later: 1,846 of its 1,879 rows have `consensus_quality = unvintaged` and were captured on 2026-09-15, whatever the release date. Reading the consensus columns reads a value captured after the event.

News `asset` is a retrieval label, not a classification of the story. It is the first of gold, silver, copper and crude whose words appear in the title, in that order (gold: gold, xau, bullion; silver: silver, xag; copper: copper; crude: crude, wti, brent, opec, petroleum, 'oil '), otherwise the asset of the search that returned the row; 15.5 percent of rows have none. Judge relevance from `query` and the title.

News `published_utc` is the publisher's stamp as received and can be old: 195 rows are dated before 2020 and one is 1970-01-01, because Google News returns old pages for searches without a recency bound. The availability clock is `available_utc`, which equals `fetched_utc`.

News capture gap. No news row was fetched between 2026-08-09T20:58:26Z and 2026-08-11T06:23:54Z (33 h 25 m). The gap cannot be filled. No item stamped inside the gap was fetched during it: 1,711 such items were fetched afterwards, 1,252 of them within six hours of the gap's end and the rest up to 60 days later.

Quote capture gap. The Brent, Hyperliquid, TradingEconomics and reference quote tables have no row between 2026-08-09T21:04Z and 2026-08-10T07:24Z (10 h 19 m), during planned maintenance of the feed. The gap cannot be filled.

News `identity_key` is the provider's item id and is not unique: 34.58 percent of rows repeat an earlier key (the same item seen again, a Google News item under another source label, an edited item fetched again, and TradingEconomics section paths that cover many headlines). `raw_id` is unique and every sighting is kept. `independent_source_count` counts publisher names, and a name and its domain variant count twice, so it overstates the number of independent sources.

Calendar. The release schedule was last refreshed on 2026-10-23. endpoints.investing.com (2026-09-15), www.bls.gov (2026-09-15), www.nyse.com (2026-09-15), www.opec.org (2026-09-15), www.pmi.spglobal.com (2026-09-15), www.stats.gov.cn (2026-09-15), www.treasurydirect.gov (2026-09-25) were not captured again then; their schedules are as captured on the dates shown.

## Incidents and repairs

Facts about this release that its corrections list cannot carry: that list names rows of the previous release that changed, and the gap gate judges whole hours.

- 2026-10-18, 13:42 to 13:49 UTC: the feed restarted and two writers appended to one capture file. Every collector has a gap of about six minutes. hyperliquid copper and silver have no reading from 13:42:35 to 13:48:39, ICE Brent from 13:42:34 to 13:48:38, and Trading Economics gold and silver from 13:42:28 to 13:48:38. Each of the five torn rows still held one complete reading after the damaged bytes, and those five readings are in this release; the damaged halves lost their fields to the other write and cannot be reconstructed. The five capture files were edited to drop the torn rows and put the readings back, so the sha256 a sidecar records is of each file as this release read it, not as it was first captured.

- 2026-10-02 to 2026-10-14: 33,286 moneyplant_quotes rows rebuilt from the bridge's spool. The capture files lost these rows before the pack was built. They carry regeneratedFrom and regeneratedAt in extra_json, and their fetched_utc equals available_utc at the spool's capture time, because a row written after the fact has no fetch clock of its own.

- swings/swings.parquet is read at confirm_available_utc. v2.0.1 read it at available_utc, under which 2,054 of 2,107 legs were readable before the leg was confirmed, a median of 1 day and at most 13 days early. Kit 2.6.2 promised this correction.

## Not included, and why

- The broker account object of the raw rows (account balances and collateral). Removed before any typing; assembly scans every string column of every table for it and refuses to build if it appears.
- Raw captures (bytes plus an index): they stay with the organizers; the meta sidecars carry their sha256 and source labels.
- Synthetic rows, interpolation, forward fill: never. Missing is missing, and the state file masks what it cannot compute.
- Feed raw keys that duplicate typed columns or are constant (listed per file in the meta notes), and opaque session ids.
- The organizers' own news model output: per-story, per-asset impact, confidence and rationale, and the aggregated per-asset sentiment index with its bullish and bearish counts, dispersion and weights. A challenge about predicting direction cannot hand over a pre-computed directional view on all four assets. The news lane does not build either table and assembly refuses both by name.
- Baseline predictions. The pack carries data; the baselines are code, they live in the participant kit, and you rebuild them by running it.
- Directories named `raw`, `parts`, `tmp` or `cache` inside a lane are build intermediates and are never assembled.

Files: 32. See `MANIFEST.json` for checksums.
