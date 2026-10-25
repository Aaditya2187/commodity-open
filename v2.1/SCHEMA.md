# Pack schema

Generated from the `.meta.json` sidecars. Types are Arrow types; `timestamp[us, tz=UTC]` columns end in `_utc`, `date32` columns in `_date`.

## `calendar/release_schedule.parquet`

- rows: 3,632; bytes: 104,554; sha256: `80866e112cfe0a4fe8652924fd0e2dcbb615c6f189a0b8473b59cb94a6a8d880`
- date range: 2021-01-01 to 2027-12-31
- clock quality: mixed; per-row column `clock_quality` with counts {'unvintaged': 554, 'published': 3078}; clocks {'published': 'release_utc'}
- rule: published rows carry the authority's stated release instant in release_utc (converted from local_tz); unvintaged rows (holidays, OPEC meetings, one EIA slip, and the central-bank and Indian releases whose authority states no clock) carry only a civil date in release_date with release_utc null and are excluded from point-in-time reads; rows built from a standing rule for future weeks say so in notes
- note: conventions
- note: coverage_per_event_type_per_year
- note: secondary_authorities

| column | type | meaning |
|---|---|---|
| `event_type` | `string` | release identifier (us_nfp, us_cpi, ..., us_holiday, uk_holiday) |
| `event_family` | `string` | coarse grouping: labor, inflation, growth, fed, central_bank, rates, energy, positioning, china, activity, holiday |
| `release_date` | `date32[day]` | civil date of the release in local_tz |
| `release_utc` | `timestamp[us, tz=UTC]` | scheduled release instant in UTC; null when the authority states no clock |
| `release_local` | `timestamp[us]` | the same instant as a naive wall-clock time in local_tz |
| `local_tz` | `string` | IANA zone of the authority (America/New_York, Asia/Shanghai, Asia/Tokyo, Asia/Kolkata, Europe/London, Europe/Berlin, Europe/Vienna) |
| `authority` | `string` | who states the schedule; 'secondary' marks rows taken from a calendar provider instead |
| `period_ref` | `string` | period the release covers: YYYY-MM, YYYY-Qn, a week-ending date, an FOMC meeting label |
| `source_url` | `string` | page or file the row was parsed from (Wayback URLs for archived years) |
| `capture_path` | `string` | raw capture of that source under build/calendar/, listed in raw/INDEX.csv |
| `clock_quality` | `string` | published: release_utc is the source's stated instant; unvintaged: civil date only, release_utc null |
| `notes` | `string` | how the date and clock were established, plus any caveat |

## `calendar/release_surprises.parquet`

- rows: 1,879; bytes: 59,517; sha256: `144efeff2bbb38bdd6c8f250273f083247de6ccceab9c1724e925395a256e276`
- date range: 2021-01-05 to 2026-10-22
- clock quality: published; clocks {'published': 'available_utc'}
- rule: row availability is the actual's availability; consensus_quality names the consensus provenance (exact only for consensus captured by our timer before the release, unvintaged otherwise)
- note: consensus_quality_per_event_type
- note: derived_from
- note: surprise_z
- note: units

| column | type | meaning |
|---|---|---|
| `event_type` | `string` | release identifier |
| `measure` | `string` | figure of the release (nfp_change, cpi_mom, ism_mfg_pmi, ...) |
| `period_ref` | `string` | period the figure covers |
| `release_utc` | `timestamp[us, tz=UTC]` | scheduled release instant (the actual's available_utc when published, else the schedule) |
| `actual` | `double` | value as first published |
| `actual_source` | `string` | alfred \| fed_statement \| investing_history \| investing_live \| forexfactory_live |
| `consensus` | `double` | latest exact consensus captured before release_utc, else latest unvintaged consensus |
| `consensus_quality` | `string` | exact \| unvintaged |
| `consensus_captured_utc` | `timestamp[us, tz=UTC]` | when that consensus row was captured |
| `previous` | `double` | prior-period figure shown at the release (same source as the actual when available) |
| `surprise` | `double` | actual - consensus, in unit |
| `surprise_z` | `double` | (surprise - median) / (1.4826 * MAD) over the trailing 36 earlier surprises of the same measure; null when fewer than 8 or MAD is 0 |
| `n_trailing` | `int32` | number of earlier surprises used for surprise_z |
| `available_utc` | `timestamp[us, tz=UTC]` | when the actual became available (from the vintage row); null when only the day is known |
| `unit` | `string` | unit of actual, consensus, previous and surprise |

## `calendar/release_vintages.parquet`

- rows: 100,121; bytes: 865,913; sha256: `a97c948dbebc9e683d35134d1b6a1763e588ef2bc53d58b0da8d58e33f56201c`
- date range: 2021-01-05 to 2026-10-23
- clock quality: mixed; per-row column `clock_quality` with counts {'published': 9793, 'unvintaged': 1893, 'exact': 88435}; clocks {'exact': 'captured_utc', 'published': 'available_utc'}
- rule: exact: our own live capture, available_utc equals captured_utc; published: an agency vintage (ALFRED, FOMC statement) or provider actual/previous/revision whose availability is the scheduled release instant in available_utc, null when only the day (available_date) is known; unvintaged: a consensus read from a calendar after the event, available_utc set to the capture time, never before the release
- note: rows_per_event_type_and_kind
- note: unit_per_measure
- note: units

| column | type | meaning |
|---|---|---|
| `event_type` | `string` | release identifier, as in release_schedule |
| `measure` | `string` | which figure of the release: nfp_change, cpi_mom, ism_mfg_pmi, fed_funds_upper, ... |
| `period_ref` | `string` | period the figure covers (YYYY-MM, YYYY-Qn, week-ending date, FOMC meeting label) |
| `kind` | `string` | consensus \| previous \| actual \| revision |
| `value` | `double` | numeric value in unit |
| `unit` | `string` | K thousands, M millions, % percent, index points |
| `source` | `string` | alfred \| investing_history \| investing_live \| forexfactory_live \| fed_statement |
| `source_url` | `string` | endpoint or page the row came from (credentials redacted) |
| `captured_utc` | `timestamp[us, tz=UTC]` | when we fetched the bytes the row was parsed from |
| `available_utc` | `timestamp[us, tz=UTC]` | when the value became available: exact = captured_utc; published = the scheduled release instant; null when only the day is known |
| `available_date` | `date32[day]` | civil day the value became available (always set) |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `capture_path` | `string` | raw capture under build/calendar/ listed in raw/INDEX.csv |
| `notes` | `string` | derivation and caveats |

## `labels/chain_daily.parquet`

- rows: 205,275; bytes: 6,307,100; sha256: `e20a6295ae9b09dfab86c65bb1fec78dbd0ef365a81acf4182137a78b11e41b9`
- date range (available_utc): 2021-02-04T18:25:00+00:00 to 2026-10-23T18:00:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 205275}; clocks {'published': 'available_utc'}
- rule: Every input row is a Bhav Copy row whose availability is the session close instant from mcx_sessions (class published: the exchange publishes after the close and we did not capture live). Each output row carries the close instant of the latest session it depends on.
- note: one row per (asset, cutoff_utc, horizon, k) for eligible designations, k up to the horizon or the last Bhav Copy, stopping at a missing settlement
- note: labels and targets are reproducible from these rows: log(w_high) and log(w_low) against the barrier in k order, y_ret = log(w_close at k = h)
- note: cutoffs: 08:30 Asia/Kolkata on every MCX trading session per mcx_sessions from 2021-02-01 to 2026-10-23 (the last Bhav Copy); horizons [5, 10, 20] sessions, k = 1 is the cutoff's own session
- note: designation: highest volume_lots summed over the two completed sessions before the cutoff among contracts listed on those sessions, excluding contracts whose staggered tender period has begun by the cutoff session and contracts whose expiry session is at or before session h; ties by earlier expiry then contract id; the winner must have traded (volume > 0)
- note: expiry session: for compulsory-delivery products (gold, silver, copper) the last full open non-holiday session at or before the printed expiry (Bhav Copy rows of GOLD05OCT22FUT, COPPER31MAR25FUT and COPPER31MAR26FUT end there); for cash-settled crude the last trading session at or before it (three crude contracts expired on evening-only holiday sessions). The rule reproduces the last Bhav Copy row of all 199 finished contracts
- note: tender period: the last N trading sessions including the expiry session, N per mcx_contract_specs.json (gold 5 through the June 2026 expiry then 3; silver 5 through July 2026 then 3; copper 5 through December 2024 then 3; crude none). Every non-closed mcx_sessions date counts as a trading session
- note: roll plan: when the designated contract's last eligible session is before session h, the chain moves on the next session to the highest-volume contract (same two-session volumes) not in delivery on that transition session and not expiring within the horizon, the rolling contract excluded; applied recursively
- note: sigma_c: sample standard deviation (ddof 1) of the 20 most recent daily log settlement returns of the historical chain before the cutoff, where session s uses the contract designated at cutoff s for the same horizon and log(settle_s / settle_(s-1)) on that contract; a session whose designation differs from the previous session's, or has none, is skipped and the window extends backwards
- note: wealth chain: W_0 = 1 at P_ref; W_k^q = W_(k-1)^close * D_k^q / D_(k-1)^close for q in open, high, low, close (close = settlement); on a transition to B the denominator is B_(k-1)^close. A missing settlement stops the chain and makes labels from that session on ungradable
- note: no synthetic rows: a session where the chain contract printed no trade keeps its settlement-based w_close and has null open/high/low
- note: build identity: {'commit': '103e51076f54ba35f5f80527095f90432cf2fdc7', 'command': 'python -m swing_dataset.labels build', 'built_utc': '2026-10-23T21:58:02.172242+00:00'}

| column | type | meaning |
|---|---|---|
| `asset` | `string` | gold \| silver \| copper \| crude |
| `cutoff_utc` | `timestamp[us, tz=UTC]` | 08:30 Asia/Kolkata on the cutoff's MCX trading day, in UTC |
| `horizon` | `int64` | sessions in the horizon: 5 \| 10 \| 20 |
| `k` | `int64` | session index inside the horizon, 1..h |
| `session_date` | `date32[day]` | MCX session of this chain row |
| `contract_id` | `string` | contract the chain sits on this session |
| `roll` | `bool` | true on a transition session (the contract differs from the previous row's) |
| `open` | `double` | contract open, INR; null when it did not trade |
| `high` | `double` | contract high, INR; null when it did not trade |
| `low` | `double` | contract low, INR; null when it did not trade |
| `settlement` | `double` | contract settlement (Bhav Copy Close), INR |
| `denominator` | `double` | this contract's settlement on the previous session: D_{k-1}^close, or B_{k-1}^close on a transition |
| `w_open` | `double` | W_{k-1}^close * open / denominator; null when open is null |
| `w_high` | `double` | W_{k-1}^close * high / denominator; null when high is null |
| `w_low` | `double` | W_{k-1}^close * low / denominator; null when low is null |
| `w_close` | `double` | W_{k-1}^close * settlement / denominator, with W_0^close = 1 at P_ref |
| `available_utc` | `timestamp[us, tz=UTC]` | close instant of this session (Bhav Copy publication is at or after it) |
| `clock_quality` | `string` | published |

## `labels/designations.parquet`

- rows: 17,724; bytes: 243,835; sha256: `3d2d2d54a2382e5db98db4c02a36637323159c8a40dc6b30d8a3e55d53db4811`
- date range (cutoff_utc): 2021-02-01T03:00:00+00:00 to 2026-10-23T03:00:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 17724}; clocks {'published': 'available_utc'}
- rule: Every input row is a Bhav Copy row whose availability is the session close instant from mcx_sessions (class published: the exchange publishes after the close and we did not capture live). Each output row carries the close instant of the latest session it depends on.
- note: one row per (asset, cutoff_utc, horizon) for every cutoff, eligible or not; ineligible rows keep the contract choice where one exists and name the reason
- note: available_utc is the close of the last completed session before the cutoff and is always before cutoff_utc
- note: cutoffs: 08:30 Asia/Kolkata on every MCX trading session per mcx_sessions from 2021-02-01 to 2026-10-23 (the last Bhav Copy); horizons [5, 10, 20] sessions, k = 1 is the cutoff's own session
- note: designation: highest volume_lots summed over the two completed sessions before the cutoff among contracts listed on those sessions, excluding contracts whose staggered tender period has begun by the cutoff session and contracts whose expiry session is at or before session h; ties by earlier expiry then contract id; the winner must have traded (volume > 0)
- note: expiry session: for compulsory-delivery products (gold, silver, copper) the last full open non-holiday session at or before the printed expiry (Bhav Copy rows of GOLD05OCT22FUT, COPPER31MAR25FUT and COPPER31MAR26FUT end there); for cash-settled crude the last trading session at or before it (three crude contracts expired on evening-only holiday sessions). The rule reproduces the last Bhav Copy row of all 199 finished contracts
- note: tender period: the last N trading sessions including the expiry session, N per mcx_contract_specs.json (gold 5 through the June 2026 expiry then 3; silver 5 through July 2026 then 3; copper 5 through December 2024 then 3; crude none). Every non-closed mcx_sessions date counts as a trading session
- note: roll plan: when the designated contract's last eligible session is before session h, the chain moves on the next session to the highest-volume contract (same two-session volumes) not in delivery on that transition session and not expiring within the horizon, the rolling contract excluded; applied recursively
- note: sigma_c: sample standard deviation (ddof 1) of the 20 most recent daily log settlement returns of the historical chain before the cutoff, where session s uses the contract designated at cutoff s for the same horizon and log(settle_s / settle_(s-1)) on that contract; a session whose designation differs from the previous session's, or has none, is skipped and the window extends backwards
- note: wealth chain: W_0 = 1 at P_ref; W_k^q = W_(k-1)^close * D_k^q / D_(k-1)^close for q in open, high, low, close (close = settlement); on a transition to B the denominator is B_(k-1)^close. A missing settlement stops the chain and makes labels from that session on ungradable
- note: no synthetic rows: a session where the chain contract printed no trade keeps its settlement-based w_close and has null open/high/low
- note: build identity: {'commit': '103e51076f54ba35f5f80527095f90432cf2fdc7', 'command': 'python -m swing_dataset.labels build', 'built_utc': '2026-10-23T21:58:02.172242+00:00'}

| column | type | meaning |
|---|---|---|
| `asset` | `string` | gold \| silver \| copper \| crude |
| `cutoff_utc` | `timestamp[us, tz=UTC]` | 08:30 Asia/Kolkata on the cutoff's MCX trading day, in UTC |
| `horizon` | `int64` | sessions in the horizon: 5 \| 10 \| 20 |
| `cutoff_date` | `date32[day]` | Asia/Kolkata civil date of the cutoff (session k = 1) |
| `eligible` | `bool` | true when a contract, P_ref, roll plan and sigma_c could all be frozen at the cutoff |
| `ineligible_reason` | `string` | insufficient_sessions \| no_eligible_contract \| no_traded_contract \| missing_p_ref \| no_roll_contract \| insufficient_vol_history \| degenerate_sigma; null when eligible |
| `contract_id` | `string` | designated contract (highest two-session volume before the cutoff among contracts not in delivery and not expiring within the horizon; ties by earlier expiry); null when no contract qualifies |
| `expiry_date` | `date32[day]` | printed expiry of the designated contract |
| `expiry_session_date` | `date32[day]` | last trading session of the designated contract by the product's expiry rule |
| `last_eligible_date` | `date32[day]` | last session the designated contract may sit in a chain: the session before its staggered tender period, or the expiry session for cash-settled crude |
| `volume_2s` | `double` | designated contract's volume in lots over the two completed sessions before the cutoff |
| `p_ref` | `double` | designated contract's settlement on the last completed session before the cutoff, INR per quotation unit; anchors W_0 = 1 |
| `sigma_c` | `double` | sample standard deviation (ddof 1) of the 20 most recent daily log settlement returns of the historical designated-contract chain before the cutoff, roll transitions skipped |
| `sigma_start_date` | `date32[day]` | oldest session whose return is inside the sigma window |
| `sigma_returns` | `int64` | returns collected for sigma_c (20 when eligible) |
| `roll_k` | `int64` | k index of the first transition session in the frozen roll plan; null when the designated contract stays eligible through the horizon |
| `roll_date` | `date32[day]` | session date of that transition |
| `roll_contract_id` | `string` | contract the chain moves to at the transition, chosen by the same rule with the rolling contract excluded |
| `roll_count` | `int64` | transitions in the plan (0 or 1 in this data) |
| `horizon_end_date` | `date32[day]` | session date at k = h |
| `horizon_complete` | `bool` | true when session h has a Bhav Copy in mcx_daily; labels and targets exist only then |
| `available_utc` | `timestamp[us, tz=UTC]` | close instant of the last completed session before the cutoff: the newest Bhav Copy the designation and sigma_c depend on |
| `clock_quality` | `string` | published |

## `labels/return_targets.parquet`

- rows: 17,551; bytes: 492,728; sha256: `87ca73bd3792e7d218e6a1e941ebe8f2e17cd39003507bdbd412de918fa37490`
- date range (available_utc): 2021-02-10T18:25:00+00:00 to 2026-10-23T18:00:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 17551}; clocks {'published': 'available_utc'}
- rule: Every input row is a Bhav Copy row whose availability is the session close instant from mcx_sessions (class published: the exchange publishes after the close and we did not capture live). Each output row carries the close instant of the latest session it depends on.
- note: one row per (asset, cutoff_utc, horizon) for eligible designations whose session h has a Bhav Copy
- note: available_utc is the close instant of session h and is always after cutoff_utc
- note: cutoffs: 08:30 Asia/Kolkata on every MCX trading session per mcx_sessions from 2021-02-01 to 2026-10-23 (the last Bhav Copy); horizons [5, 10, 20] sessions, k = 1 is the cutoff's own session
- note: designation: highest volume_lots summed over the two completed sessions before the cutoff among contracts listed on those sessions, excluding contracts whose staggered tender period has begun by the cutoff session and contracts whose expiry session is at or before session h; ties by earlier expiry then contract id; the winner must have traded (volume > 0)
- note: expiry session: for compulsory-delivery products (gold, silver, copper) the last full open non-holiday session at or before the printed expiry (Bhav Copy rows of GOLD05OCT22FUT, COPPER31MAR25FUT and COPPER31MAR26FUT end there); for cash-settled crude the last trading session at or before it (three crude contracts expired on evening-only holiday sessions). The rule reproduces the last Bhav Copy row of all 199 finished contracts
- note: tender period: the last N trading sessions including the expiry session, N per mcx_contract_specs.json (gold 5 through the June 2026 expiry then 3; silver 5 through July 2026 then 3; copper 5 through December 2024 then 3; crude none). Every non-closed mcx_sessions date counts as a trading session
- note: roll plan: when the designated contract's last eligible session is before session h, the chain moves on the next session to the highest-volume contract (same two-session volumes) not in delivery on that transition session and not expiring within the horizon, the rolling contract excluded; applied recursively
- note: sigma_c: sample standard deviation (ddof 1) of the 20 most recent daily log settlement returns of the historical chain before the cutoff, where session s uses the contract designated at cutoff s for the same horizon and log(settle_s / settle_(s-1)) on that contract; a session whose designation differs from the previous session's, or has none, is skipped and the window extends backwards
- note: wealth chain: W_0 = 1 at P_ref; W_k^q = W_(k-1)^close * D_k^q / D_(k-1)^close for q in open, high, low, close (close = settlement); on a transition to B the denominator is B_(k-1)^close. A missing settlement stops the chain and makes labels from that session on ungradable
- note: no synthetic rows: a session where the chain contract printed no trade keeps its settlement-based w_close and has null open/high/low
- note: build identity: {'commit': '103e51076f54ba35f5f80527095f90432cf2fdc7', 'command': 'python -m swing_dataset.labels build', 'built_utc': '2026-10-23T21:58:02.172242+00:00'}

| column | type | meaning |
|---|---|---|
| `asset` | `string` | gold \| silver \| copper \| crude |
| `cutoff_utc` | `timestamp[us, tz=UTC]` | 08:30 Asia/Kolkata on the cutoff's MCX trading day, in UTC |
| `horizon` | `int64` | sessions in the horizon: 5 \| 10 \| 20 |
| `y_ret` | `double` | log W_h^close |
| `y_mfe` | `double` | max_k log W_k^high over the horizon; null when no session traded |
| `y_mae` | `double` | min_k log W_k^low over the horizon; null when no session traded |
| `y_range` | `double` | y_mfe - y_mae |
| `p_ref` | `double` | designated contract's settlement on the last completed session before the cutoff, INR |
| `terminal_contract_id` | `string` | contract the chain sits on at session h |
| `terminal_settlement` | `double` | that contract's settlement at session h, INR |
| `terminal_date` | `date32[day]` | session date at k = h |
| `no_trade_sessions` | `int64` | horizon sessions where the chain contract printed no trade (high and low null) |
| `available_utc` | `timestamp[us, tz=UTC]` | close instant of session h |
| `clock_quality` | `string` | published |
| `ungradable_reason` | `string` | missing_settlement \| missing_incoming_settlement; null when graded |

## `labels/swing_labels.parquet`

- rows: 52,653; bytes: 537,769; sha256: `e85d41220d69f09f47e8cb71e939c20ce739d94cd389b8d35516a1679c7a6e85`
- date range (available_utc): 2021-02-05T18:25:00+00:00 to 2026-10-23T18:00:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 52653}; clocks {'published': 'available_utc'}
- rule: Every input row is a Bhav Copy row whose availability is the session close instant from mcx_sessions (class published: the exchange publishes after the close and we did not capture live). Each output row carries the close instant of the latest session it depends on.
- note: one row per (asset, cutoff_utc, horizon, k_multiplier) for eligible designations whose session h has a Bhav Copy; cutoffs whose horizon runs past the last Bhav Copy have no row, even when a barrier was already touched
- note: both = both barriers breached in the same session before either alone; stored, excluded from scoring
- note: available_utc is the close instant of the deciding session and is always after cutoff_utc
- note: cutoffs: 08:30 Asia/Kolkata on every MCX trading session per mcx_sessions from 2021-02-01 to 2026-10-23 (the last Bhav Copy); horizons [5, 10, 20] sessions, k = 1 is the cutoff's own session
- note: designation: highest volume_lots summed over the two completed sessions before the cutoff among contracts listed on those sessions, excluding contracts whose staggered tender period has begun by the cutoff session and contracts whose expiry session is at or before session h; ties by earlier expiry then contract id; the winner must have traded (volume > 0)
- note: expiry session: for compulsory-delivery products (gold, silver, copper) the last full open non-holiday session at or before the printed expiry (Bhav Copy rows of GOLD05OCT22FUT, COPPER31MAR25FUT and COPPER31MAR26FUT end there); for cash-settled crude the last trading session at or before it (three crude contracts expired on evening-only holiday sessions). The rule reproduces the last Bhav Copy row of all 199 finished contracts
- note: tender period: the last N trading sessions including the expiry session, N per mcx_contract_specs.json (gold 5 through the June 2026 expiry then 3; silver 5 through July 2026 then 3; copper 5 through December 2024 then 3; crude none). Every non-closed mcx_sessions date counts as a trading session
- note: roll plan: when the designated contract's last eligible session is before session h, the chain moves on the next session to the highest-volume contract (same two-session volumes) not in delivery on that transition session and not expiring within the horizon, the rolling contract excluded; applied recursively
- note: sigma_c: sample standard deviation (ddof 1) of the 20 most recent daily log settlement returns of the historical chain before the cutoff, where session s uses the contract designated at cutoff s for the same horizon and log(settle_s / settle_(s-1)) on that contract; a session whose designation differs from the previous session's, or has none, is skipped and the window extends backwards
- note: wealth chain: W_0 = 1 at P_ref; W_k^q = W_(k-1)^close * D_k^q / D_(k-1)^close for q in open, high, low, close (close = settlement); on a transition to B the denominator is B_(k-1)^close. A missing settlement stops the chain and makes labels from that session on ungradable
- note: no synthetic rows: a session where the chain contract printed no trade keeps its settlement-based w_close and has null open/high/low
- note: build identity: {'commit': '103e51076f54ba35f5f80527095f90432cf2fdc7', 'command': 'python -m swing_dataset.labels build', 'built_utc': '2026-10-23T21:58:02.172242+00:00'}

| column | type | meaning |
|---|---|---|
| `asset` | `string` | gold \| silver \| copper \| crude |
| `cutoff_utc` | `timestamp[us, tz=UTC]` | 08:30 Asia/Kolkata on the cutoff's MCX trading day, in UTC |
| `horizon` | `int64` | sessions in the horizon: 5 \| 10 \| 20 |
| `k_multiplier` | `double` | barrier multiplier: 0.75 \| 1.0 \| 1.25 (the scored task uses 1.0) |
| `barrier` | `double` | b = k_multiplier * sigma_c * sqrt(h), in log wealth |
| `label` | `string` | up_swing \| down_swing \| no_swing \| both; null when ungradable |
| `hit_session` | `int64` | k of the session that touched the deciding barrier; null for no_swing and ungradable |
| `hit_date` | `date32[day]` | session date of hit_session |
| `available_utc` | `timestamp[us, tz=UTC]` | close instant of the deciding session (barrier session, or session h for no_swing) |
| `clock_quality` | `string` | published |
| `ungradable_reason` | `string` | missing_settlement \| missing_incoming_settlement; null when graded |

## `macro/alfred_vintages.parquet`

- rows: 122,782; bytes: 939,852; sha256: `ebaeb59358be8e508dc3198fb4bd754d642fc31f489f4528639ad28cf3d8f717`
- date range (observation_date): 2009-01-01 to 2026-10-23
- date range (realtime_start): 2005-06-28 to 2026-10-23
- clock quality: mixed; per-row column `clock_quality` with counts {'published': 122743, 'unvintaged': 39}; clocks {'published': 'available_utc'}
- rule: Per-row clock_quality. published rows: available_utc is realtime_start + 1 day 00:00 UTC (available_rule next_day_00utc), or the series' first ALFRED vintage + 1 day for pre-tracking history (first_vintage_next_day_00utc; a lower bound, not a publication instant). unvintaged rows (available_rule vintage_precedes_observation): FRED's vintage date precedes the observation period, no credible availability instant, available_utc null.
- note: Method: FRED series/observations with output_type=1 (observations by real-time period) over the full real-time range 1776-07-04..9999-12-31, split into windows of at most 1500 vintage dates (API limit 2000) at series/vintagedates boundaries; periods clipped at a window edge are merged with their continuation (same date, same value, adjacent days). Verified live 2026-09-15 that FRED clips periods at the requested window and never emits adjacent equal-valued periods in an unwindowed response.
- note: observation_start=2009-01-01 (one year before the 2010 target so 2010 year-over-year rates are computable); every vintage since the first ALFRED vintage is included.
- note: Rows whose FRED value is '.' (no observation, e.g. market holidays for daily series) are dropped; per-series counts are in series_stats.
- note: available_utc: FRED states no release time-of-day for any of these series (series notes checked live 2026-09-15). Rule next_day_00utc: realtime_start + 1 day at 00:00 UTC, the conservative end of the vintage's civil day (ALFRED vintage dates are US civil dates; these publishers release during US business hours). Rule first_vintage_next_day_00utc: observations whose period ended before the series' first ALFRED vintage are reported by FRED with realtime_start at that first vintage (DEXCHUS: at the series' 2005-06-28 FRED inception), which proves the value current then but says nothing about first publication; available_utc = first vintage + 1 day, a safe lower bound. Rule vintage_precedes_observation: FRED's realtime_start lies before the observation period end although the series was tracked (e.g. VIXCLS values dated a US holiday carried in the prior business day's vintage; DCOILWTICO/DCOILBRENTEU 2012-12-27 in the 2012-12-26 vintage); FRED's own as-of query confirms this and no credible availability time exists, so clock_quality = unvintaged and available_utc = null. FRED fields are never altered.
- note: Vintage semantics proof: PAYEMS observation 2026-08-01 first appears with realtime_start 2026-09-04 (the BLS Employment Situation release for August 2026); the proof-PAYEMS-asof-* captures show the observation absent as of 2026-09-03 and present as of 2026-09-04.
- note: All 32 requested series exist in ALFRED; none skipped.

| column | type | meaning |
|---|---|---|
| `series_id` | `string` | FRED/ALFRED series id |
| `observation_date` | `date32[day]` | observation period start as dated by FRED (monthly = first of month) |
| `period_end_date` | `date32[day]` | last civil day of the observation period (daily/weekly: the date itself) |
| `value` | `double` | value as published during [realtime_start, realtime_end]; native units |
| `realtime_start` | `date32[day]` | first ALFRED vintage date on which this value was current |
| `realtime_end` | `date32[day]` | last vintage date on which this value was current; 9999-12-31 = still current |
| `available_utc` | `timestamp[us, tz=UTC]` | earliest instant the vintage record proves the value available; null when unvintaged |
| `available_rule` | `string` | next_day_00utc \| first_vintage_next_day_00utc \| vintage_precedes_observation; see notes |
| `clock_quality` | `string` | published, or unvintaged when FRED's vintage date precedes the observation period |
| `units` | `string` | FRED units_short at the latest series record |
| `frequency` | `string` | FRED frequency_short (D, W, M, ...) |

## `macro/cot.parquet`

- rows: 3,508; bytes: 1,207,376; sha256: `bbc5247a526f4bf32dc856ddb87b1789f1b00776383e9ab18e07788bda051a7b`
- date range (report_date): 2010-01-05 to 2026-10-20
- clock quality: published; per-row column `clock_quality` with counts {'published': 3508}; clocks {'published': 'available_utc'}
- rule: Every row is published. available_utc = loaded_utc (Socrata :created_at, the row's API load instant, 15:30 ET on the actual publication day) when the row was loaded one report at a time, else release_utc (15:30 ET on the scheduled release day from the captured CFTC schedule pages or press release 7864-19); available_source says which. release_caveat marks report weeks whose scheduled day is documented as wrong or uncertain (2013 and 2018-19 lapses in appropriations, Juneteenth 2021, 2023 ION incident, 2025-01-09 day of mourning, 2025 lapse).
- note: Socrata dataset 72hh-3qpy (Disaggregated - Futures Only), all provider columns, market codes {'gold': '088691', 'silver': '084691', 'copper': '085692', 'crude': '067651'}, report dates from 2010-01-01.
- note: release_utc = 15:30 US/Eastern on the scheduled release day, converted to UTC. The day comes from the captured CFTC release-schedule pages (release_source = cftc_schedule:...) and otherwise from the rule 'Friday after the Tuesday report date; a federal holiday on Wednesday-Friday of that week moves the release to the following Monday' (release_source = rule:...). The captured schedules are tentative: publication was suspended during the 2013, 2018-19 and 2025 lapses in appropriations and delayed in Feb-Mar 2023 (ION cyber incident); see the captured Historical Special Announcements page.
- note: loaded_utc = Socrata :created_at for rows loaded one report at a time (15:30 ET on the actual publication day, matching the CFTC's 2025 catch-up table); null for rows that came in with a bulk load (days with >= 50 rows for one market: ['2022-08-01']). Where loaded_utc exists it is the better clock.
- note: available_utc is the best availability evidence per row: loaded_utc where the row was loaded one report at a time, else release_utc. release_caveat marks report weeks whose scheduled day is known to be wrong or uncertain (2013 and 2018-19 lapses, 2023 ION incident, 2025-01-09 day of mourning, 2025 lapse); for 2018-19 release_utc follows the Tuesday/Friday catch-up rule stated in CFTC press release 7864-19 (captured).
- note: TFF (gpe5-46if) skipped: zero rows for all four market codes (captures in parts/cot/tff_evidence.json).
- note: Numbers are float64 as Socrata serves them as strings; provider field names are kept verbatim.

| column | type | meaning |
|---|---|---|
| `asset` | `string` | dataset asset key (gold/silver/copper/crude) |
| `report_date` | `date32[day]` | CFTC report date (positions as of close; Tuesday, or Monday when Tuesday is a holiday) |
| `release_utc` | `timestamp[us, tz=UTC]` | scheduled release instant: 15:30 US/Eastern on the CFTC release day, see release_source |
| `release_source` | `string` | cftc_schedule:<capture> when a captured schedule page covers the week, else rule:* |
| `release_caveat` | `string` | documented disruption affecting the scheduled day (shutdowns, ION incident, day of mourning); null otherwise |
| `loaded_utc` | `timestamp[us, tz=UTC]` | Socrata :created_at for per-week loads (the row's actual API load instant); null for bulk-loaded history |
| `available_utc` | `timestamp[us, tz=UTC]` | best availability evidence: loaded_utc when present, else release_utc |
| `available_source` | `string` | socrata_created_at, or the release_source used |
| `clock_quality` | `string` | published |
| `socrata_row_id` | `string` | Socrata :id |
| `socrata_created_at_utc` | `timestamp[us, tz=UTC]` | Socrata :created_at, raw |
| `socrata_updated_at_utc` | `timestamp[us, tz=UTC]` | Socrata :updated_at, raw |
| `socrata_version` | `string` | Socrata :version, raw |
| `id` | `string` | ID (text) |
| `market_and_exchange_names` | `string` | Market_and_Exchange_Names (text) |
| `report_date_as_yyyy_mm_dd` | `date32[day]` | Report_Date_as_YYYY_MM_DD (calendar_date) |
| `yyyy_report_week_ww` | `string` | YYYY Report Week WW (text) |
| `contract_market_name` | `string` | Contract_Market_Name (text) |
| `cftc_contract_market_code` | `string` | CFTC_Contract_Market_Code (text) |
| `cftc_market_code` | `string` | CFTC_Market_Code (text) |
| `cftc_region_code` | `string` | CFTC_Region_Code (text) |
| `cftc_commodity_code` | `string` | CFTC_Commodity_Code (text) |
| `commodity_name` | `string` | Commodity Name (text) |
| `open_interest_all` | `double` | Open_Interest_All (number) |
| `prod_merc_positions_long` | `double` | Prod_Merc_Positions_Long_All (number) |
| `prod_merc_positions_short` | `double` | Prod_Merc_Positions_Short_All (number) |
| `swap_positions_long_all` | `double` | Swap_Positions_Long_All (number) |
| `swap__positions_short_all` | `double` | Swap__Positions_Short_All (number) |
| `swap__positions_spread_all` | `double` | Swap__Positions_Spread_All (number) |
| `m_money_positions_long_all` | `double` | M_Money_Positions_Long_All (number) |
| `m_money_positions_short_all` | `double` | M_Money_Positions_Short_All (number) |
| `m_money_positions_spread` | `double` | M_Money_Positions_Spread_All (number) |
| `other_rept_positions_long` | `double` | Other_Rept_Positions_Long_All (number) |
| `other_rept_positions_short` | `double` | Other_Rept_Positions_Short_All (number) |
| `other_rept_positions_spread` | `double` | Other_Rept_Positions_Spread_All (number) |
| `tot_rept_positions_long_all` | `double` | Tot_Rept_Positions_Long_All (number) |
| `tot_rept_positions_short` | `double` | Tot_Rept_Positions_Short_All (number) |
| `nonrept_positions_long_all` | `double` | NonRept_Positions_Long_All (number) |
| `nonrept_positions_short_all` | `double` | NonRept_Positions_Short_All (number) |
| `open_interest_old` | `double` | Open_Interest_Old (number) |
| `prod_merc_positions_long_1` | `double` | Prod_Merc_Positions_Long_Old (number) |
| `prod_merc_positions_short_1` | `double` | Prod_Merc_Positions_Short_Old (number) |
| `swap_positions_long_old` | `double` | Swap_Positions_Long_Old (number) |
| `swap__positions_short_old` | `double` | Swap__Positions_Short_Old (number) |
| `swap__positions_spread_old` | `double` | Swap__Positions_Spread_Old (number) |
| `m_money_positions_long_old` | `double` | M_Money_Positions_Long_Old (number) |
| `m_money_positions_short_old` | `double` | M_Money_Positions_Short_Old (number) |
| `m_money_positions_spread_1` | `double` | M_Money_Positions_Spread_Old (number) |
| `other_rept_positions_long_1` | `double` | Other_Rept_Positions_Long_Old (number) |
| `other_rept_positions_short_1` | `double` | Other_Rept_Positions_Short_Old (number) |
| `other_rept_positions_spread_1` | `double` | Other_Rept_Positions_Spread_Old (number) |
| `tot_rept_positions_long_old` | `double` | Tot_Rept_Positions_Long_Old (number) |
| `tot_rept_positions_short_1` | `double` | Tot_Rept_Positions_Short_Old (number) |
| `nonrept_positions_long_old` | `double` | NonRept_Positions_Long_Old (number) |
| `nonrept_positions_short_old` | `double` | NonRept_Positions_Short_Old (number) |
| `open_interest_other` | `double` | Open_Interest_Other (number) |
| `prod_merc_positions_long_2` | `double` | Prod_Merc_Positions_Long_Other (number) |
| `prod_merc_positions_short_2` | `double` | Prod_Merc_Positions_Short_Other (number) |
| `swap_positions_long_other` | `double` | Swap_Positions_Long_Other (number) |
| `swap__positions_short_other` | `double` | Swap__Positions_Short_Other (number) |
| `swap__positions_spread_other` | `double` | Swap__Positions_Spread_Other (number) |
| `m_money_positions_long_other` | `double` | M_Money_Positions_Long_Other (number) |
| `m_money_positions_short_other` | `double` | M_Money_Positions_Short_Other (number) |
| `m_money_positions_spread_2` | `double` | M_Money_Positions_Spread_Other (number) |
| `other_rept_positions_long_2` | `double` | Other_Rept_Positions_Long_Other (number) |
| `other_rept_positions_short_2` | `double` | Other_Rept_Positions_Short_Other (number) |
| `other_rept_positions_spread_2` | `double` | Other_Rept_Positions_Spread_Other (number) |
| `tot_rept_positions_long_other` | `double` | Tot_Rept_Positions_Long_Other (number) |
| `tot_rept_positions_short_2` | `double` | Tot_Rept_Positions_Short_Other (number) |
| `nonrept_positions_long_other` | `double` | NonRept_Positions_Long_Other (number) |
| `nonrept_positions_short_other` | `double` | NonRept_Positions_Short_Other (number) |
| `change_in_open_interest_all` | `double` | Change_in_Open_Interest_All (number) |
| `change_in_prod_merc_long` | `double` | Change_in_Prod_Merc_Long_All (number) |
| `change_in_prod_merc_short` | `double` | Change_in_Prod_Merc_Short_All (number) |
| `change_in_swap_long_all` | `double` | Change_in_Swap_Long_All (number) |
| `change_in_swap_short_all` | `double` | Change_in_Swap_Short_All (number) |
| `change_in_swap_spread_all` | `double` | Change_in_Swap_Spread_All (number) |
| `change_in_m_money_long_all` | `double` | Change_in_M_Money_Long_All (number) |
| `change_in_m_money_short_all` | `double` | Change_in_M_Money_Short_All (number) |
| `change_in_m_money_spread` | `double` | Change_in_M_Money_Spread_All (number) |
| `change_in_other_rept_long` | `double` | Change_in_Other_Rept_Long_All (number) |
| `change_in_other_rept_short` | `double` | Change_in_Other_Rept_Short_All (number) |
| `change_in_other_rept_spread` | `double` | Change_in_Other_Rept_Spread_All (number) |
| `change_in_tot_rept_long_all` | `double` | Change_in_Tot_Rept_Long_All (number) |
| `change_in_tot_rept_short` | `double` | Change_in_Tot_Rept_Short_All (number) |
| `change_in_nonrept_long_all` | `double` | Change_in_NonRept_Long_All (number) |
| `change_in_nonrept_short_all` | `double` | Change_in_NonRept_Short_All (number) |
| `pct_of_open_interest_all` | `double` | Pct_of_Open_Interest_All (number) |
| `pct_of_oi_prod_merc_long` | `double` | Pct_of_OI_Prod_Merc_Long_All (number) |
| `pct_of_oi_prod_merc_short` | `double` | Pct_of_OI_Prod_Merc_Short_All (number) |
| `pct_of_oi_swap_long_all` | `double` | Pct_of_OI_Swap_Long_All (number) |
| `pct_of_oi_swap_short_all` | `double` | Pct_of_OI_Swap_Short_All (number) |
| `pct_of_oi_swap_spread_all` | `double` | Pct_of_OI_Swap_Spread_All (number) |
| `pct_of_oi_m_money_long_all` | `double` | Pct_of_OI_M_Money_Long_All (number) |
| `pct_of_oi_m_money_short_all` | `double` | Pct_of_OI_M_Money_Short_All (number) |
| `pct_of_oi_m_money_spread` | `double` | Pct_of_OI_M_Money_Spread_All (number) |
| `pct_of_oi_other_rept_long` | `double` | Pct_of_OI_Other_Rept_Long_All (number) |
| `pct_of_oi_other_rept_short` | `double` | Pct_of_OI_Other_Rept_Short_All (number) |
| `pct_of_oi_other_rept_spread` | `double` | Pct_of_OI_Other_Rept_Spread_All (number) |
| `pct_of_oi_tot_rept_long_all` | `double` | Pct_of_OI_Tot_Rept_Long_All (number) |
| `pct_of_oi_tot_rept_short` | `double` | Pct_of_OI_Tot_Rept_Short_All (number) |
| `pct_of_oi_nonrept_long_all` | `double` | Pct_of_OI_NonRept_Long_All (number) |
| `pct_of_oi_nonrept_short_all` | `double` | Pct_of_OI_NonRept_Short_All (number) |
| `pct_of_open_interest_old` | `double` | Pct_of_Open_Interest_Old (number) |
| `pct_of_oi_prod_merc_long_1` | `double` | Pct_of_OI_Prod_Merc_Long_Old (number) |
| `pct_of_oi_prod_merc_short_1` | `double` | Pct_of_OI_Prod_Merc_Short_Old (number) |
| `pct_of_oi_swap_long_old` | `double` | Pct_of_OI_Swap_Long_Old (number) |
| `pct_of_oi_swap_short_old` | `double` | Pct_of_OI_Swap_Short_Old (number) |
| `pct_of_oi_swap_spread_old` | `double` | Pct_of_OI_Swap_Spread_Old (number) |
| `pct_of_oi_m_money_long_old` | `double` | Pct_of_OI_M_Money_Long_Old (number) |
| `pct_of_oi_m_money_short_old` | `double` | Pct_of_OI_M_Money_Short_Old (number) |
| `pct_of_oi_m_money_spread_1` | `double` | Pct_of_OI_M_Money_Spread_Old (number) |
| `pct_of_oi_other_rept_long_1` | `double` | Pct_of_OI_Other_Rept_Long_Old (number) |
| `pct_of_oi_other_rept_short_1` | `double` | Pct_of_OI_Other_Rept_Short_Old (number) |
| `pct_of_oi_other_rept_spread_1` | `double` | Pct_of_OI_Other_Rept_Spread_Old (number) |
| `pct_of_oi_tot_rept_long_old` | `double` | Pct_of_OI_Tot_Rept_Long_Old (number) |
| `pct_of_oi_tot_rept_short_1` | `double` | Pct_of_OI_Tot_Rept_Short_Old (number) |
| `pct_of_oi_nonrept_long_old` | `double` | Pct_of_OI_NonRept_Long_Old (number) |
| `pct_of_oi_nonrept_short_old` | `double` | Pct_of_OI_NonRept_Short_Old (number) |
| `pct_of_open_interest_other` | `double` | Pct_of_Open_Interest_Other (number) |
| `pct_of_oi_prod_merc_long_2` | `double` | Pct_of_OI_Prod_Merc_Long_Other (number) |
| `pct_of_oi_prod_merc_short_2` | `double` | Pct_of_OI_Prod_Merc_Short_Other (number) |
| `pct_of_oi_swap_long_other` | `double` | Pct_of_OI_Swap_Long_Other (number) |
| `pct_of_oi_swap_short_other` | `double` | Pct_of_OI_Swap_Short_Other (number) |
| `pct_of_oi_swap_spread_other` | `double` | Pct_of_OI_Swap_Spread_Other (number) |
| `pct_of_oi_m_money_long_other` | `double` | Pct_of_OI_M_Money_Long_Other (number) |
| `pct_of_oi_m_money_short_other` | `double` | Pct_of_OI_M_Money_Short_Other (number) |
| `pct_of_oi_m_money_spread_2` | `double` | Pct_of_OI_M_Money_Spread_Other (number) |
| `pct_of_oi_other_rept_long_2` | `double` | Pct_of_OI_Other_Rept_Long_Other (number) |
| `pct_of_oi_other_rept_short_2` | `double` | Pct_of_OI_Other_Rept_Short_Other (number) |
| `pct_of_oi_other_rept_spread_2` | `double` | Pct_of_OI_Other_Rept_Spread_Other (number) |
| `pct_of_oi_tot_rept_long_other` | `double` | Pct_of_OI_Tot_Rept_Long_Other (number) |
| `pct_of_oi_tot_rept_short_2` | `double` | Pct_of_OI_Tot_Rept_Short_Other (number) |
| `pct_of_oi_nonrept_long_other` | `double` | Pct_of_OI_NonRept_Long_Other (number) |
| `pct_of_oi_nonrept_short_other` | `double` | Pct_of_OI_NonRept_Short_Other (number) |
| `traders_tot_all` | `double` | Traders_Tot_All (number) |
| `traders_prod_merc_long_all` | `double` | Traders_Prod_Merc_Long_All (number) |
| `traders_prod_merc_short_all` | `double` | Traders_Prod_Merc_Short_All (number) |
| `traders_swap_long_all` | `double` | Traders_Swap_Long_All (number) |
| `traders_swap_short_all` | `double` | Traders_Swap_Short_All (number) |
| `traders_swap_spread_all` | `double` | Traders_Swap_Spread_All (number) |
| `traders_m_money_long_all` | `double` | Traders_M_Money_Long_All (number) |
| `traders_m_money_short_all` | `double` | Traders_M_Money_Short_All (number) |
| `traders_m_money_spread_all` | `double` | Traders_M_Money_Spread_All (number) |
| `traders_other_rept_long_all` | `double` | Traders_Other_Rept_Long_All (number) |
| `traders_other_rept_short` | `double` | Traders_Other_Rept_Short_All (number) |
| `traders_other_rept_spread` | `double` | Traders_Other_Rept_Spread_All (number) |
| `traders_tot_rept_long_all` | `double` | Traders_Tot_Rept_Long_All (number) |
| `traders_tot_rept_short_all` | `double` | Traders_Tot_Rept_Short_All (number) |
| `traders_tot_old` | `double` | Traders_Tot_Old (number) |
| `traders_prod_merc_long_old` | `double` | Traders_Prod_Merc_Long_Old (number) |
| `traders_prod_merc_short_old` | `double` | Traders_Prod_Merc_Short_Old (number) |
| `traders_swap_long_old` | `double` | Traders_Swap_Long_Old (number) |
| `traders_swap_short_old` | `double` | Traders_Swap_Short_Old (number) |
| `traders_swap_spread_old` | `double` | Traders_Swap_Spread_Old (number) |
| `traders_m_money_long_old` | `double` | Traders_M_Money_Long_Old (number) |
| `traders_m_money_short_old` | `double` | Traders_M_Money_Short_Old (number) |
| `traders_m_money_spread_old` | `double` | Traders_M_Money_Spread_Old (number) |
| `traders_other_rept_long_old` | `double` | Traders_Other_Rept_Long_Old (number) |
| `traders_other_rept_short_1` | `double` | Traders_Other_Rept_Short_Old (number) |
| `traders_other_rept_spread_1` | `double` | Traders_Other_Rept_Spread_Old (number) |
| `traders_tot_rept_long_old` | `double` | Traders_Tot_Rept_Long_Old (number) |
| `traders_tot_rept_short_old` | `double` | Traders_Tot_Rept_Short_Old (number) |
| `traders_tot_other` | `double` | Traders_Tot_Other (number) |
| `traders_prod_merc_long_other` | `double` | Traders_Prod_Merc_Long_Other (number) |
| `traders_prod_merc_short_other` | `double` | Traders_Prod_Merc_Short_Other (number) |
| `traders_swap_long_other` | `double` | Traders_Swap_Long_Other (number) |
| `traders_swap_short_other` | `double` | Traders_Swap_Short_Other (number) |
| `traders_swap_spread_other` | `double` | Traders_Swap_Spread_Other (number) |
| `traders_m_money_long_other` | `double` | Traders_M_Money_Long_Other (number) |
| `traders_m_money_short_other` | `double` | Traders_M_Money_Short_Other (number) |
| `traders_m_money_spread_other` | `double` | Traders_M_Money_Spread_Other (number) |
| `traders_other_rept_long_other` | `double` | Traders_Other_Rept_Long_Other (number) |
| `traders_other_rept_short_2` | `double` | Traders_Other_Rept_Short_Other (number) |
| `traders_other_rept_spread_2` | `double` | Traders_Other_Rept_Spread_Other (number) |
| `traders_tot_rept_long_other` | `double` | Traders_Tot_Rept_Long_Other (number) |
| `traders_tot_rept_short_other` | `double` | Traders_Tot_Rept_Short_Other (number) |
| `conc_gross_le_4_tdr_long` | `double` | Conc_Gross_LE_4_TDR_Long_All (number) |
| `conc_gross_le_4_tdr_short` | `double` | Conc_Gross_LE_4_TDR_Short_All (number) |
| `conc_gross_le_8_tdr_long` | `double` | Conc_Gross_LE_8_TDR_Long_All (number) |
| `conc_gross_le_8_tdr_short` | `double` | Conc_Gross_LE_8_TDR_Short_All (number) |
| `conc_net_le_4_tdr_long_all` | `double` | Conc_Net_LE_4_TDR_Long_All (number) |
| `conc_net_le_4_tdr_short_all` | `double` | Conc_Net_LE_4_TDR_Short_All (number) |
| `conc_net_le_8_tdr_long_all` | `double` | Conc_Net_LE_8_TDR_Long_All (number) |
| `conc_net_le_8_tdr_short_all` | `double` | Conc_Net_LE_8_TDR_Short_All (number) |
| `conc_gross_le_4_tdr_long_1` | `double` | Conc_Gross_LE_4_TDR_Long_Old (number) |
| `conc_gross_le_4_tdr_short_1` | `double` | Conc_Gross_LE_4_TDR_Short_Old (number) |
| `conc_gross_le_8_tdr_long_1` | `double` | Conc_Gross_LE_8_TDR_Long_Old (number) |
| `conc_gross_le_8_tdr_short_1` | `double` | Conc_Gross_LE_8_TDR_Short_Old (number) |
| `conc_net_le_4_tdr_long_old` | `double` | Conc_Net_LE_4_TDR_Long_Old (number) |
| `conc_net_le_4_tdr_short_old` | `double` | Conc_Net_LE_4_TDR_Short_Old (number) |
| `conc_net_le_8_tdr_long_old` | `double` | Conc_Net_LE_8_TDR_Long_Old (number) |
| `conc_net_le_8_tdr_short_old` | `double` | Conc_Net_LE_8_TDR_Short_Old (number) |
| `conc_gross_le_4_tdr_long_2` | `double` | Conc_Gross_LE_4_TDR_Long_Other (number) |
| `conc_gross_le_4_tdr_short_2` | `double` | Conc_Gross_LE_4_TDR_Short_Other (number) |
| `conc_gross_le_8_tdr_long_2` | `double` | Conc_Gross_LE_8_TDR_Long_Other (number) |
| `conc_gross_le_8_tdr_short_2` | `double` | Conc_Gross_LE_8_TDR_Short_Other (number) |
| `conc_net_le_4_tdr_long_other` | `double` | Conc_Net_LE_4_TDR_Long_Other (number) |
| `conc_net_le_4_tdr_short_other` | `double` | Conc_Net_LE_4_TDR_Short_Other (number) |
| `conc_net_le_8_tdr_long_other` | `double` | Conc_Net_LE_8_TDR_Long_Other (number) |
| `conc_net_le_8_tdr_short_other` | `double` | Conc_Net_LE_8_TDR_Short_Other (number) |
| `contract_units` | `string` | Contract_Units (text) |
| `cftc_subgroup_code` | `string` | CFTC_SubGroup_Code (text) |
| `commodity` | `string` | COMMODITY_NAME (text) |
| `commodity_subgroup_name` | `string` | COMMODITY_SUBGROUP_NAME (text) |
| `commodity_group_name` | `string` | COMMODITY_GROUP_NAME (text) |
| `futonly_or_combined` | `string` | FutOnly_or_Combined (text) |

## `macro/cot_legacy.parquet`

- rows: 3,508; bytes: 851,054; sha256: `6b84a2ce04965451dd1421fee6475582f0739571849a7798a4476d6cb22453b3`
- date range (report_date): 2010-01-05 to 2026-10-20
- clock quality: published; per-row column `clock_quality` with counts {'published': 3508}; clocks {'published': 'available_utc'}
- rule: Every row is published. available_utc = loaded_utc (Socrata :created_at, the row's API load instant, 15:30 ET on the actual publication day) when the row was loaded one report at a time, else release_utc (15:30 ET on the scheduled release day from the captured CFTC schedule pages or press release 7864-19); available_source says which. release_caveat marks report weeks whose scheduled day is documented as wrong or uncertain (2013 and 2018-19 lapses in appropriations, Juneteenth 2021, 2023 ION incident, 2025-01-09 day of mourning, 2025 lapse).
- note: Socrata dataset 6dca-aqww (Legacy - Futures Only), all provider columns, market codes {'gold': '088691', 'silver': '084691', 'copper': '085692', 'crude': '067651'}, report dates from 2010-01-01.
- note: release_utc = 15:30 US/Eastern on the scheduled release day, converted to UTC. The day comes from the captured CFTC release-schedule pages (release_source = cftc_schedule:...) and otherwise from the rule 'Friday after the Tuesday report date; a federal holiday on Wednesday-Friday of that week moves the release to the following Monday' (release_source = rule:...). The captured schedules are tentative: publication was suspended during the 2013, 2018-19 and 2025 lapses in appropriations and delayed in Feb-Mar 2023 (ION cyber incident); see the captured Historical Special Announcements page.
- note: loaded_utc = Socrata :created_at for rows loaded one report at a time (15:30 ET on the actual publication day, matching the CFTC's 2025 catch-up table); null for rows that came in with a bulk load (days with >= 50 rows for one market: ['2022-09-13']). Where loaded_utc exists it is the better clock.
- note: available_utc is the best availability evidence per row: loaded_utc where the row was loaded one report at a time, else release_utc. release_caveat marks report weeks whose scheduled day is known to be wrong or uncertain (2013 and 2018-19 lapses, 2023 ION incident, 2025-01-09 day of mourning, 2025 lapse); for 2018-19 release_utc follows the Tuesday/Friday catch-up rule stated in CFTC press release 7864-19 (captured).
- note: TFF (gpe5-46if) skipped: zero rows for all four market codes (captures in parts/cot/tff_evidence.json).
- note: Numbers are float64 as Socrata serves them as strings; provider field names are kept verbatim.

| column | type | meaning |
|---|---|---|
| `asset` | `string` | dataset asset key (gold/silver/copper/crude) |
| `report_date` | `date32[day]` | CFTC report date (positions as of close; Tuesday, or Monday when Tuesday is a holiday) |
| `release_utc` | `timestamp[us, tz=UTC]` | scheduled release instant: 15:30 US/Eastern on the CFTC release day, see release_source |
| `release_source` | `string` | cftc_schedule:<capture> when a captured schedule page covers the week, else rule:* |
| `release_caveat` | `string` | documented disruption affecting the scheduled day (shutdowns, ION incident, day of mourning); null otherwise |
| `loaded_utc` | `timestamp[us, tz=UTC]` | Socrata :created_at for per-week loads (the row's actual API load instant); null for bulk-loaded history |
| `available_utc` | `timestamp[us, tz=UTC]` | best availability evidence: loaded_utc when present, else release_utc |
| `available_source` | `string` | socrata_created_at, or the release_source used |
| `clock_quality` | `string` | published |
| `socrata_row_id` | `string` | Socrata :id |
| `socrata_created_at_utc` | `timestamp[us, tz=UTC]` | Socrata :created_at, raw |
| `socrata_updated_at_utc` | `timestamp[us, tz=UTC]` | Socrata :updated_at, raw |
| `socrata_version` | `string` | Socrata :version, raw |
| `id` | `string` | ID (text) |
| `market_and_exchange_names` | `string` | Market_and_Exchange_Names (text) |
| `report_date_as_yyyy_mm_dd` | `date32[day]` | Report_Date_as_YYYY_MM_DD (calendar_date) |
| `yyyy_report_week_ww` | `string` | YYYY Report Week WW (text) |
| `contract_market_name` | `string` | CONTRACT_MARKET_NAME (text) |
| `cftc_contract_market_code` | `string` | CFTC_Contract_Market_Code (text) |
| `cftc_market_code` | `string` | CFTC_Market_Code (text) |
| `cftc_region_code` | `string` | CFTC_Region_Code (text) |
| `cftc_commodity_code` | `string` | CFTC_Commodity_Code (text) |
| `commodity_name` | `string` | Commodity Name (text) |
| `open_interest_all` | `double` | Open_Interest_All (number) |
| `noncomm_positions_long_all` | `double` | NonComm_Positions_Long_All (number) |
| `noncomm_positions_short_all` | `double` | NonComm_Positions_Short_All (number) |
| `noncomm_postions_spread_all` | `double` | NonComm_Postions_Spread_All (number) |
| `comm_positions_long_all` | `double` | Comm_Positions_Long_All (number) |
| `comm_positions_short_all` | `double` | Comm_Positions_Short_All (number) |
| `tot_rept_positions_long_all` | `double` | Tot_Rept_Positions_Long_All (number) |
| `tot_rept_positions_short` | `double` | Tot_Rept_Positions_Short_All (number) |
| `nonrept_positions_long_all` | `double` | NonRept_Positions_Long_All (number) |
| `nonrept_positions_short_all` | `double` | NonRept_Positions_Short_All (number) |
| `open_interest_old` | `double` | Open_Interest_Old (number) |
| `noncomm_positions_long_old` | `double` | NonComm_Positions_Long_Old (number) |
| `noncomm_positions_short_old` | `double` | NonComm_Positions_Short_Old (number) |
| `noncomm_positions_spread` | `double` | NonComm_Positions_Spread_Old (number) |
| `comm_positions_long_old` | `double` | Comm_Positions_Long_Old (number) |
| `comm_positions_short_old` | `double` | Comm_Positions_Short_Old (number) |
| `tot_rept_positions_long_old` | `double` | Tot_Rept_Positions_Long_Old (number) |
| `tot_rept_positions_short_1` | `double` | Tot_Rept_Positions_Short_Old (number) |
| `nonrept_positions_long_old` | `double` | NonRept_Positions_Long_Old (number) |
| `nonrept_positions_short_old` | `double` | NonRept_Positions_Short_Old (number) |
| `open_interest_other` | `double` | Open_Interest_Other (number) |
| `noncomm_positions_long_other` | `double` | NonComm_Positions_Long_Other (number) |
| `noncomm_positions_short_other` | `double` | NonComm_Positions_Short_Other (number) |
| `noncomm_positions_spread_1` | `double` | NonComm_Positions_Spread_Other (number) |
| `comm_positions_long_other` | `double` | Comm_Positions_Long_Other (number) |
| `comm_positions_short_other` | `double` | Comm_Positions_Short_Other (number) |
| `tot_rept_positions_long_other` | `double` | Tot_Rept_Positions_Long_Other (number) |
| `tot_rept_positions_short_2` | `double` | Tot_Rept_Positions_Short_Other (number) |
| `nonrept_positions_long_other` | `double` | NonRept_Positions_Long_Other (number) |
| `nonrept_positions_short_other` | `double` | NonRept_Positions_Short_Other (number) |
| `change_in_open_interest_all` | `double` | Change_in_Open_Interest_All (number) |
| `change_in_noncomm_long_all` | `double` | Change_in_NonComm_Long_All (number) |
| `change_in_noncomm_short_all` | `double` | Change_in_NonComm_Short_All (number) |
| `change_in_noncomm_spead_all` | `double` | Change_in_NonComm_Spead_All (number) |
| `change_in_comm_long_all` | `double` | Change_in_Comm_Long_All (number) |
| `change_in_comm_short_all` | `double` | Change_in_Comm_Short_All (number) |
| `change_in_tot_rept_long_all` | `double` | Change_in_Tot_Rept_Long_All (number) |
| `change_in_tot_rept_short` | `double` | Change_in_Tot_Rept_Short_All (number) |
| `change_in_nonrept_long_all` | `double` | Change_in_NonRept_Long_All (number) |
| `change_in_nonrept_short_all` | `double` | Change_in_NonRept_Short_All (number) |
| `pct_of_open_interest_all` | `double` | Pct_of_Open_Interest_All (number) |
| `pct_of_oi_noncomm_long_all` | `double` | Pct_of_OI_NonComm_Long_All (number) |
| `pct_of_oi_noncomm_short_all` | `double` | Pct_of_OI_NonComm_Short_All (number) |
| `pct_of_oi_noncomm_spread` | `double` | Pct_of_OI_NonComm_Spread_All (number) |
| `pct_of_oi_comm_long_all` | `double` | Pct_of_OI_Comm_Long_All (number) |
| `pct_of_oi_comm_short_all` | `double` | Pct_of_OI_Comm_Short_All (number) |
| `pct_of_oi_tot_rept_long_all` | `double` | Pct_of_OI_Tot_Rept_Long_All (number) |
| `pct_of_oi_tot_rept_short` | `double` | Pct_of_OI_Tot_Rept_Short_All (number) |
| `pct_of_oi_nonrept_long_all` | `double` | Pct_of_OI_NonRept_Long_All (number) |
| `pct_of_oi_nonrept_short_all` | `double` | Pct_of_OI_NonRept_Short_All (number) |
| `pct_of_open_interest_old` | `double` | Pct_of_Open_Interest_Old (number) |
| `pct_of_oi_noncomm_long_old` | `double` | Pct_of_OI_NonComm_Long_Old (number) |
| `pct_of_oi_noncomm_short_old` | `double` | Pct_of_OI_NonComm_Short_Old (number) |
| `pct_of_oi_noncomm_spread_1` | `double` | Pct_of_OI_NonComm_Spread_Old (number) |
| `pct_of_oi_comm_long_old` | `double` | Pct_of_OI_Comm_Long_Old (number) |
| `pct_of_oi_comm_short_old` | `double` | Pct_of_OI_Comm_Short_Old (number) |
| `pct_of_oi_tot_rept_long_old` | `double` | Pct_of_OI_Tot_Rept_Long_Old (number) |
| `pct_of_oi_tot_rept_short_1` | `double` | Pct_of_OI_Tot_Rept_Short_Old (number) |
| `pct_of_oi_nonrept_long_old` | `double` | Pct_of_OI_NonRept_Long_Old (number) |
| `pct_of_oi_nonrept_short_old` | `double` | Pct_of_OI_NonRept_Short_Old (number) |
| `pct_of_open_interest_other` | `double` | Pct_of_Open_Interest_Other (number) |
| `pct_of_oi_noncomm_long_other` | `double` | Pct_of_OI_NonComm_Long_Other (number) |
| `pct_of_oi_noncomm_short_other` | `double` | Pct_of_OI_NonComm_Short_Other (number) |
| `pct_of_oi_noncomm_spread_2` | `double` | Pct_of_OI_NonComm_Spread_Other (number) |
| `pct_of_oi_comm_long_other` | `double` | Pct_of_OI_Comm_Long_Other (number) |
| `pct_of_oi_comm_short_other` | `double` | Pct_of_OI_Comm_Short_Other (number) |
| `pct_of_oi_tot_rept_long_other` | `double` | Pct_of_OI_Tot_Rept_Long_Other (number) |
| `pct_of_oi_tot_rept_short_2` | `double` | Pct_of_OI_Tot_Rept_Short_Other (number) |
| `pct_of_oi_nonrept_long_other` | `double` | Pct_of_OI_NonRept_Long_Other (number) |
| `pct_of_oi_nonrept_short_other` | `double` | Pct_of_OI_NonRept_Short_Other (number) |
| `traders_tot_all` | `double` | Traders_Tot_All (number) |
| `traders_noncomm_long_all` | `double` | Traders_NonComm_Long_All (number) |
| `traders_noncomm_short_all` | `double` | Traders_NonComm_Short_All (number) |
| `traders_noncomm_spread_all` | `double` | Traders_NonComm_Spread_All (number) |
| `traders_comm_long_all` | `double` | Traders_Comm_Long_All (number) |
| `traders_comm_short_all` | `double` | Traders_Comm_Short_All (number) |
| `traders_tot_rept_long_all` | `double` | Traders_Tot_Rept_Long_All (number) |
| `traders_tot_rept_short_all` | `double` | Traders_Tot_Rept_Short_All (number) |
| `traders_tot_old` | `double` | Traders_Tot_Old (number) |
| `traders_noncomm_long_old` | `double` | Traders_NonComm_Long_Old (number) |
| `traders_noncomm_short_old` | `double` | Traders_NonComm_Short_Old (number) |
| `traders_noncomm_spead_old` | `double` | Traders_NonComm_Spead_Old (number) |
| `traders_comm_long_old` | `double` | Traders_Comm_Long_Old (number) |
| `traders_comm_short_old` | `double` | Traders_Comm_Short_Old (number) |
| `traders_tot_rept_long_old` | `double` | Traders_Tot_Rept_Long_Old (number) |
| `traders_tot_rept_short_old` | `double` | Traders_Tot_Rept_Short_Old (number) |
| `traders_tot_other` | `double` | Traders_Tot_Other (number) |
| `traders_noncomm_long_other` | `double` | Traders_NonComm_Long_Other (number) |
| `traders_noncomm_short_other` | `double` | Traders_NonComm_Short_Other (number) |
| `traders_noncomm_spread_other` | `double` | Traders_NonComm_Spread_Other (number) |
| `traders_comm_long_other` | `double` | Traders_Comm_Long_Other (number) |
| `traders_comm_short_other` | `double` | Traders_Comm_Short_Other (number) |
| `traders_tot_rept_long_other` | `double` | Traders_Tot_Rept_Long_Other (number) |
| `traders_tot_rept_short_other` | `double` | Traders_Tot_Rept_Short_Other (number) |
| `conc_gross_le_4_tdr_long` | `double` | Conc_Gross_LE_4_TDR_Long_All (number) |
| `conc_gross_le_4_tdr_short` | `double` | Conc_Gross_LE_4_TDR_Short_All (number) |
| `conc_gross_le_8_tdr_long` | `double` | Conc_Gross_LE_8_TDR_Long_All (number) |
| `conc_gross_le_8_tdr_short` | `double` | Conc_Gross_LE_8_TDR_Short_All (number) |
| `conc_net_le_4_tdr_long_all` | `double` | Conc_Net_LE_4_TDR_Long_All (number) |
| `conc_net_le_4_tdr_short_all` | `double` | Conc_Net_LE_4_TDR_Short_All (number) |
| `conc_net_le_8_tdr_long_all` | `double` | Conc_Net_LE_8_TDR_Long_All (number) |
| `conc_net_le_8_tdr_short_all` | `double` | Conc_Net_LE_8_TDR_Short_All (number) |
| `conc_gross_le_4_tdr_long_1` | `double` | Conc_Gross_LE_4_TDR_Long_Old (number) |
| `conc_gross_le_4_tdr_short_1` | `double` | Conc_Gross_LE_4_TDR_Short_Old (number) |
| `conc_gross_le_8_tdr_long_1` | `double` | Conc_Gross_LE_8_TDR_Long_Old (number) |
| `conc_gross_le_8_tdr_short_1` | `double` | Conc_Gross_LE_8_TDR_Short_Old (number) |
| `conc_net_le_4_tdr_long_old` | `double` | Conc_Net_LE_4_TDR_Long_Old (number) |
| `conc_net_le_4_tdr_short_old` | `double` | Conc_Net_LE_4_TDR_Short_Old (number) |
| `conc_net_le_8_tdr_long_old` | `double` | Conc_Net_LE_8_TDR_Long_Old (number) |
| `conc_net_le_8_tdr_short_old` | `double` | Conc_Net_LE_8_TDR_Short_Old (number) |
| `conc_gross_le_4_tdr_long_2` | `double` | Conc_Gross_LE_4_TDR_Long_Other (number) |
| `conc_gross_le_4_tdr_short_2` | `double` | Conc_Gross_LE_4_TDR_Short_Other (number) |
| `conc_gross_le_8_tdr_long_2` | `double` | Conc_Gross_LE_8_TDR_Long_Other (number) |
| `conc_gross_le_8_tdr_short_2` | `double` | Conc_Gross_LE_8_TDR_Short_Other (number) |
| `conc_net_le_4_tdr_long_other` | `double` | Conc_Net_LE_4_TDR_Long_Other (number) |
| `conc_net_le_4_tdr_short_other` | `double` | Conc_Net_LE_4_TDR_Short_Other (number) |
| `conc_net_le_8_tdr_long_other` | `double` | Conc_Net_LE_8_TDR_Long_Other (number) |
| `conc_net_le_8_tdr_short_other` | `double` | Conc_Net_LE_8_TDR_Short_Other (number) |
| `contract_units` | `string` | Contract_Units (text) |
| `commodity` | `string` | COMMODITY_NAME (text) |
| `commodity_subgroup_name` | `string` | COMMODITY_SUBGROUP_NAME (text) |
| `commodity_group_name` | `string` | COMMODITY_GROUP_NAME (text) |
| `futonly_or_combined` | `string` | FutOnly_or_Combined (text) |

## `macro/hl_candles_1d.parquet`

- rows: 1,178; bytes: 52,857; sha256: `7d893f9a8a528068c0356b394dbe56fde8f42567f65cb2eb45bac0e007a05cbd`
- date range (open_utc): 2025-12-22T00:00:00+00:00 to 2026-10-22T00:00:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 1178}; clocks {'published': 'available_utc'}
- rule: Every row is published: available_utc = close_utc, the candle's close; capture happened later.
- note: candleSnapshot on the xyz builder dex. The API serves only the most recent 5000 candles per coin and interval (documented; verified live: explicit earlier windows return nothing), so the earliest stored 1h candle is bounded by the first build date, not by the listing. Every run unions new candles into the stored history.
- note: Still-open candles (close_utc after the fetch instant) are never stored.
- note: Continuity: 0 gap(s) between consecutive candles; listed under gaps.
- note: Prices USD; volume in base units; provider fields t/T/o/h/l/c/v/n mapped 1:1.

| column | type | meaning |
|---|---|---|
| `instrument` | `string` | Hyperliquid coin name on the xyz builder dex |
| `open_utc` | `timestamp[us, tz=UTC]` | candle open time (t) |
| `close_utc` | `timestamp[us, tz=UTC]` | candle close time (T, last millisecond of the interval) |
| `open` | `double` | o, USD |
| `high` | `double` | h, USD |
| `low` | `double` | l, USD |
| `close` | `double` | c, USD |
| `volume` | `double` | v, base units (contracts of the underlying unit as sized by szDecimals) |
| `trade_count` | `int64` | n |
| `available_utc` | `timestamp[us, tz=UTC]` | equal to close_utc: a candle is known at its close |
| `clock_quality` | `string` | published: the candle is final at close_utc; capture happened later |

## `macro/hl_candles_1h.parquet`

- rows: 23,693; bytes: 878,836; sha256: `59f8fe8409443d0bd781e50559f7c15c779ddfec80128fb149c3c128d3378e76`
- date range (open_utc): 2026-02-19T01:00:00+00:00 to 2026-10-23T20:00:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 23693}; clocks {'published': 'available_utc'}
- rule: Every row is published: available_utc = close_utc, the candle's close; capture happened later.
- note: candleSnapshot on the xyz builder dex. The API serves only the most recent 5000 candles per coin and interval (documented; verified live: explicit earlier windows return nothing), so the earliest stored 1h candle is bounded by the first build date, not by the listing. Every run unions new candles into the stored history.
- note: Still-open candles (close_utc after the fetch instant) are never stored.
- note: Continuity: 0 gap(s) between consecutive candles; listed under gaps.
- note: Prices USD; volume in base units; provider fields t/T/o/h/l/c/v/n mapped 1:1.

| column | type | meaning |
|---|---|---|
| `instrument` | `string` | Hyperliquid coin name on the xyz builder dex |
| `open_utc` | `timestamp[us, tz=UTC]` | candle open time (t) |
| `close_utc` | `timestamp[us, tz=UTC]` | candle close time (T, last millisecond of the interval) |
| `open` | `double` | o, USD |
| `high` | `double` | h, USD |
| `low` | `double` | l, USD |
| `close` | `double` | c, USD |
| `volume` | `double` | v, base units (contracts of the underlying unit as sized by szDecimals) |
| `trade_count` | `int64` | n |
| `available_utc` | `timestamp[us, tz=UTC]` | equal to close_utc: a candle is known at its close |
| `clock_quality` | `string` | published: the candle is final at close_utc; capture happened later |

## `macro/hl_funding.parquet`

- rows: 28,312; bytes: 624,723; sha256: `47aa664b04ceb9c5e5642615e758d80d13c34013edf7c4035dcb5076148f32d7`
- date range (time_utc): 2025-12-22T15:00:00.012000+00:00 to 2026-10-23T21:00:00.075000+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 28312}; clocks {'published': 'available_utc'}
- rule: Every row is published: available_utc = time_utc, the funding timestamp; capture happened later.
- note: fundingHistory paged 500 entries per call from before listing to the build instant.
- note: Funding is hourly; times carry the provider's millisecond offset after the hour.
- note: Continuity at 1h spacing (times floored to the hour): 0 gap(s) listed under gaps.

| column | type | meaning |
|---|---|---|
| `instrument` | `string` | Hyperliquid coin name on the xyz builder dex |
| `time_utc` | `timestamp[us, tz=UTC]` | funding timestamp as returned (hourly, a few ms after the hour) |
| `funding_rate` | `double` | fundingRate, hourly rate as a fraction |
| `premium` | `double` | premium as returned |
| `available_utc` | `timestamp[us, tz=UTC]` | equal to time_utc: the funding value is known when it is applied |
| `clock_quality` | `string` | published |

## `macro/usdinr.parquet`

- rows: 1,400; bytes: 49,743; sha256: `8c3880ac18933462abfabf2b28d74f77173dfa2f434da91c1faadd07b1f38b20`
- date range (date): 2021-01-01 to 2026-10-16
- clock quality: published; per-row column `clock_quality` with counts {'published': 1400}; clocks {'published': 'available_utc'}
- rule: Every row is published: available_utc is FBIL's stated displayTime (published_ist, Asia/Kolkata) in UTC; we did not capture at that time. usdinr_dexinus is the latest FRED vintage joined on the civil date for cross-checking only and carries no clock.
- note: FBIL reference rate via the site's own JSON API (wasdm/refrates/fetchfiltered, one request per calendar year, authenticated=false). displayTime is the source-stated publication instant (IST); clock_quality published.
- note: Unauthenticated FBIL access lags: last available date 2026-10-16, build date 2026-10-23. Days after the last date are absent, not filled.
- note: DEXINUS (FRED, latest vintage, observation_start 2021-01-01) joined on civil date as a cross-check only; 750 days differ by more than 0.05 (listed under diff_over_threshold_days). Different fixings: Mumbai 13:00/13:30 IST vs New York noon.
- note: Business-day gaps: 111 weekdays without an FBIL rate between the first and last date; 110 explained by the captured RBI Mumbai holiday matrix, 1 unexplained (see gaps).
- note: Rows are deduplicated on date (first occurrence kept); no synthetic rows.

| column | type | meaning |
|---|---|---|
| `date` | `date32[day]` | Mumbai civil date of the FBIL reference rate |
| `usdinr_fbil` | `double` | FBIL USD/INR reference rate, INR per 1 USD |
| `published_ist` | `timestamp[us, tz=Asia/Kolkata]` | FBIL displayTime as stated by the source, Asia/Kolkata |
| `available_utc` | `timestamp[us, tz=UTC]` | published_ist in UTC |
| `clock_quality` | `string` | published (source-stated publication instant; we did not capture at that time) |
| `fbil_comments` | `string` | FBIL comments field when non-empty |
| `fbil_product` | `string` | FBIL subProdName verbatim ('INR / 1 USD'; 'INR/1 USD' for 2021-02-01..15) |
| `usdinr_dexinus` | `double` | FRED DEXINUS (H.10 noon buying rate, New York) for the same civil date, latest vintage; null when FRED has no value |
| `diff_vs_dexinus` | `double` | usdinr_fbil - usdinr_dexinus |
| `diff_over_threshold` | `bool` | abs(diff_vs_dexinus) > 0.05 |

## `mcx/mcx_daily.parquet`

- rows: 159,529; bytes: 4,120,141; sha256: `284057f8d01ec1c5f4b5f2dce2557c406c8f054393a991bfcb22267374fcc405`
- date range: 2021-01-01 to 2026-10-23
- clock quality: published; per-row column `clock_quality` with counts {'published': 159529}; clocks {'published': 'available_utc'}
- rule: The exchange publishes the Bhav Copy after the session closes and we did not capture it live, so every row is published with unknown latency. available_utc is the session's close instant from mcx_sessions (evening close 23:30 or 23:55 IST per the hours circular in force, the 17:00 morning close on morning-only days, the Muhurat or budget-session close where one applies); for a session whose evening close no retained circular states, the later published close (23:55 IST) is used so the instant is never earlier than the true close.
- note: One row per (session_date, contract_id) for every FUTCOM contract the exchange listed that day, all commodities, whole curve.
- note: Units are native: INR per MCX quotation unit (GOLD per 10 g, SILVER per kg, COPPER per kg, CRUDEOIL per barrel; see mcx_contract_specs.json).
- note: The Bhav Copy has a single closing price column (`Close`); it is the daily settlement price. `settlement` carries it for every row, `close` only where the contract traded.
- note: Zero `Open`/`High`/`Low` in the exchange file mean no trade and are stored as null, never as 0.
- note: `open_interest_change` is derived here from consecutive sessions; the exchange file does not publish it.

| column | type | meaning |
|---|---|---|
| `session_date` | `date32[day]` | MCX trade date (Asia/Kolkata civil date); Bhav Copy `Date`/`DateDisplay` |
| `symbol` | `string` | Bhav Copy `Symbol`, trailing padding stripped (GOLD, GOLDM, SILVER, ...) |
| `asset` | `string` | dataset asset key for the four required products (gold/silver/copper/crude), null for other symbols |
| `expiry_date` | `date32[day]` | Bhav Copy `ExpiryDate` (DDMONYYYY) as a date |
| `contract_id` | `string` | feed contract id `mcx:<SYMBOL><DD><MON><YY>FUT` |
| `instrument` | `string` | Bhav Copy `InstrumentName` (FUTCOM) |
| `open` | `double` | Bhav Copy `Open`, INR per quotation unit; null when the exchange prints 0 (no trade) |
| `high` | `double` | Bhav Copy `High`; null when the exchange prints 0 (no trade) |
| `low` | `double` | Bhav Copy `Low`; null when the exchange prints 0 (no trade) |
| `close` | `double` | Bhav Copy `Close` for contract-days with volume_lots > 0, null otherwise. MCX publishes one closing price and it is the daily settlement price, not the last trade |
| `settlement` | `double` | Bhav Copy `Close`: the exchange's daily settlement price, present for every listed contract including untraded ones |
| `previous_close` | `double` | Bhav Copy `Previous Close`: the prior session's settlement as the exchange restates it |
| `volume_lots` | `int64` | Bhav Copy `Volume(Lots)` |
| `volume_units` | `double` | Bhav Copy `Volume(In 000's)` times 1000, in `volume_unit` |
| `volume_unit` | `string` | unit label carried in `VolumeInThousands` (GRMS, KGS, BBL, ...) |
| `value_inr` | `double` | Bhav Copy `Value(Lacs)` times 100000, rounded to the rupee (the file carries two decimals of lakhs) |
| `open_interest` | `int64` | Bhav Copy `Open Interest(Lots)` |
| `open_interest_change` | `int64` | open_interest minus the same contract's open_interest on the immediately preceding session present in this file; null when the contract has no row on that session (derived, not published) |
| `source_file` | `string` | raw capture path relative to build/mcx/raw/ |
| `clock_quality` | `string` | published: the exchange publishes the file the evening of the trade date; we did not capture it live |
| `available_utc` | `timestamp[us, tz=UTC]` | the session's close instant in UTC from mcx_sessions (evening close, or the morning close on morning-only days, or the special session's close): the earliest instant the exchange can have published this row |

## `mcx/mcx_sessions.parquet`

- rows: 2,191; bytes: 17,048; sha256: `be2316b018137e61d8607f3b95b4fea1660ecfffeee6b93f5c0edd472207c2eb`
- date range: 2021-01-01 to 2026-12-31
- clock quality: published; per-row column `clock_quality` with counts {'published': 2191}; clocks {'published': 'available_utc'}
- rule: Each row's state and stated hours come from the circulars in evidence_ids, and available_utc is 00:00 UTC of the day after the latest of their issue dates: the annual trading-holiday circular alone for the dates it governs, plus the Revision in Trading Hours circular that states the evening close where one covers the date, plus any single-date circular such as an election closure, a Muhurat timing or a budget-day live session. Every row is published, so a default point-in-time read returns it from its available_utc on. The open and evening-only dates from 2026-11-02 to 2026-12-31 are published from the 2026 holiday circular alone, available from 2025-12-16, because no retained Revision in Trading Hours circular covers them. Their evening close is 23:55 with hours_notified false: the later of the two closes MCX has used since October 2020, a bound that is never earlier than the real close and not a time any circular states. A row is not revised once a release has carried it: an hours circular issued later applies only to dates added after 2026-12-31.
- note: Hours are for internationally referenceable non-agricultural commodities (gold, silver, copper, crude oil); agricultural contracts close earlier.
- note: Weekend dates are closed unless a circular states a session (budget-day live sessions, Sunday Muhurat trading).
- note: Muhurat and budget-day sessions are stored with their own trading windows in the open/close columns and flagged in special_session; the state column keeps the four-value enum.
- note: No retained circular states the evening close from 2026-11-01. The open and evening-only dates from 2026-11-02 to 2026-12-31 carry 23:55 with hours_notified=false: the later of 23:30 and 23:55, an upper bound, so no instant inside the real session falls after it. The feed's mcx_calendar.py trades the shorter 23:30 on the same dates, the cautious choice for a desk. The Revision in Trading Hours circular for the US clock change of 2026-11-01 is not among the retained circulars.
- note: The 2026-11-08 Muhurat session is announced by the 2026 holiday circular, which says its timings 'shall be notified subsequently'. Its row has no times; the instant used to date its Bhav Copy is 23:55 IST, never earlier than the real close.
- note: The table ends 2026-12-31 because the 2027 Trading Holidays circular is not among the retained circulars. MCX issued the circulars for 2021 to 2026 on 2020-12-11, 2021-12-10, 2022-12-09, 2023-12-14, 2024-12-13 and 2025-12-15. Dates of 2027 are added as new rows when it is retained; no row of this table changes then.
- note: 2026 differs from feed mcx_calendar.py on two circular-backed dates: 2026-01-15 (evening only, MCX/TRD/017/2026) and Sunday 2026-02-01 (special live session, MCX/TRD/027/2026).

| column | type | meaning |
|---|---|---|
| `session_date` | `date32[day]` | Asia/Kolkata civil date |
| `weekday` | `string` | three-letter weekday name |
| `state` | `string` | open \| morning_only \| evening_only \| closed |
| `morning_open_ist` | `time64[us]` | start of the first trading window, IST; null when the morning session is shut |
| `morning_close_ist` | `time64[us]` | end of the first trading window, IST |
| `evening_open_ist` | `time64[us]` | start of the second trading window, IST; null when the evening session is shut |
| `evening_close_ist` | `time64[us]` | end of the second trading window, IST. Where a Revision in Trading Hours circular covers the date (hours_notified true) it is that circular's close: 23:30 while New York is on daylight time, 23:55 otherwise. Where none does (hours_notified false) it is 23:55, the later of the two, a bound that is never earlier than the real close and not a notified time. Muhurat and special windows carry their own times; null on closed dates and on an announced session no circular has timed |
| `hours_notified` | `bool` | true when a retained Revision in Trading Hours circular covers this date. false when none does: on an open or evening-only date evening_close_ist is then the 23:55 bound and not a notified time; an announced session no circular has timed (the Muhurat of 2026-11-08) has null windows; on a closed date the flag only records whether a circular's period spans it |
| `special_session` | `string` | muhurat \| budget_live_session \| delayed_open \| null |
| `holiday_name` | `string` | holiday as printed in the circular, null on ordinary days |
| `evidence_ids` | `list<item: string>` | ids of the captured circulars that state something about this date (build/mcx/raw/circulars/<id>.pdf) |
| `note` | `string` | free text for anything non-standard |
| `available_utc` | `timestamp[us, tz=UTC]` | 00:00 UTC of the day after the latest issue date among this row's evidence_ids: the instant by which every circular the row relies on had been published. A bound close is not a circular and does not move it |
| `clock_quality` | `string` | published on every row: the state and the stated times are backed by the circulars in evidence_ids and available_utc is the instant they were all published. A close shown with hours_notified false is a bound, not a stated time. Pack v2.0.1 classed 43 rows unvintaged; none is |

## `pack/news/news_clusters.parquet`

- rows: 166,570; bytes: 26,286,960; sha256: `ce3c91943ca1d603c0eacb18d1a4108393a4df86c1c151c4e9e4aa9b054fd119`
- date range (fetched_utc): 2026-07-16T02:55:53.469699+00:00 to 2026-10-23T21:30:02.103714+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 166570}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: created_at is the feed's own computation time: exact.
- note: One row per cluster version; join memberships on cluster_version_id.

| column | type | meaning |
|---|---|---|
| `cluster_version_id` | `string` | news.cluster_versions.cluster_version_id |
| `logical_cluster_id` | `string` | stable story id across versions |
| `algorithm_version` | `string` | clustering algorithm version |
| `predecessor_version_id` | `string` | previous version of the same logical cluster |
| `canonical_raw_id` | `string` | raw_id of the canonical member |
| `independent_source_count` | `int64` | distinct publishers in the cluster |
| `first_published_utc` | `timestamp[us, tz=UTC]` | earliest member published_at |
| `last_published_utc` | `timestamp[us, tz=UTC]` | latest member published_at |
| `as_of_fetched_utc` | `timestamp[us, tz=UTC]` | fetched_at horizon the version was computed from |
| `member_hash` | `string` | hash of the member set |
| `fetched_utc` | `timestamp[us, tz=UTC]` | created_at: when the version was computed |
| `available_utc` | `timestamp[us, tz=UTC]` | = fetched_utc |
| `clock_quality` | `string` | exact |

## `pack/news/news_memberships.parquet`

- rows: 436,303; bytes: 15,937,633; sha256: `817a78bcaaf702da75435dc9e6077f2c78ef9e1309dc9767a76cf368ace31cbb`
- date range (fetched_utc): 2026-07-16T02:55:53.469699+00:00 to 2026-10-23T21:30:02.103714+00:00
- clock quality: mixed; per-row column `clock_quality` with counts {'exact': 436302, 'unvintaged': 1}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: clock inherited from the cluster version's created_at (exact).

| column | type | meaning |
|---|---|---|
| `cluster_version_id` | `string` | news.cluster_memberships.cluster_version_id |
| `raw_id` | `string` | member raw_id |
| `member_order` | `int64` | order within the version |
| `publisher_identity` | `string` | publisher identity used for independence counting |
| `fetched_utc` | `timestamp[us, tz=UTC]` | created_at of the cluster version (joined) |
| `available_utc` | `timestamp[us, tz=UTC]` | = fetched_utc |
| `clock_quality` | `string` | exact; unvintaged when the version row is missing |

## `pack/news/news_rows.parquet`

- rows: 173,381; bytes: 100,674,556; sha256: `c95f64300d18957936a790210f41cd6735c1147bc756b837d91e6dc183a80579`
- date range (fetched_utc): 2026-07-16T02:46:02.747259+00:00 to 2026-10-23T21:40:01.760349+00:00
- clock quality: mixed; per-row column `clock_quality` with counts {'exact': 151775, 'published': 21606}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: exact when fetched_at is within 24 h after published_at (the feed polled the source while the item was fresh); otherwise published, with available_utc = fetched_at, the first instant the feed had the item. published_utc is the publisher's label and never an availability clock.
- note: All columns of news.raw_news are kept; late_seconds and the clock columns are added.

| column | type | meaning |
|---|---|---|
| `raw_id` | `string` | news.raw_news.raw_id |
| `source` | `string` | feed source label |
| `source_item_id` | `string` | provider item id |
| `identity_key` | `string` | dedup identity key |
| `content_hash` | `string` | sha256 of the normalized content |
| `original_url` | `string` | article URL as received |
| `original_title` | `string` | title as received |
| `original_summary` | `string` | summary as received |
| `published_utc` | `timestamp[us, tz=UTC]` | publisher-stated publication time (published_at) |
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed fetch time (fetched_at) |
| `available_utc` | `timestamp[us, tz=UTC]` | = fetched_utc for every row (the instant we had the item) |
| `clock_quality` | `string` | exact when fetched_utc - published_utc <= 24 h, else published |
| `late_seconds` | `double` | fetched_utc - published_utc in seconds |
| `trust_version` | `string` | trust model version |
| `trust_tier` | `string` | trust tier |
| `trust_weight` | `double` | trust weight |
| `query` | `string` | search query / feed slot that produced the row |
| `region` | `string` | global \| india |
| `asset` | `string` | gold \| silver \| copper \| crude \| null |
| `publisher_domain` | `string` | publisher domain |
| `source_sentiment` | `double` | provider sentiment when supplied |

## `pack/quotes/brent_quotes.parquet`

- rows: 1,724,529; bytes: 18,205,478; sha256: `786b40b6885c8669be8c29936d0b2962e8de0e56286b4629552b11b83915b69c`
- date range (fetched_utc): 2026-06-22T11:30:20.332854+00:00 to 2026-10-23T21:39:49.759960+00:00
- clock quality: mixed; per-row column `clock_quality` with counts {'exact': 1721960, 'published': 2569}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: TE rows (adapter te:*, status live): ts = datetime.now(UTC) when the shared TE cache was read (<= 10 s after the fetch), so exact and conservative. yfinance fallback rows: ts is the 1m bar time: published, available_utc = bar time.
- note: Native unit: USD per bbl.

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `asset` | `string` | crude |
| `venue` | `string` | ice_brent |
| `source_tag` | `string` | feed source tag (te:BRN, te:CO1:COM, yf-1m:BZ=F, yahoo:BZ=F) |
| `status` | `string` | live (TE) \| delayed (yfinance fallback) |
| `price` | `double` | price, USD per bbl |
| `adapter_source` | `string` | raw adapterSource / raw source |
| `source_event_utc` | `timestamp[us, tz=UTC]` | raw sourceEventTs when present |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/quotes/comex_delayed_quotes.parquet`

- rows: 80,825; bytes: 1,757,554; sha256: `888b1e2a2ed2ab825be3d1113fb596d01d6f28de4b16ceaeb9d738c260d39416`
- date range (fetched_utc): 2026-07-10T07:47:35+00:00 to 2026-10-23T21:10:11.622086+00:00
- clock quality: mixed; per-row column `clock_quality` with counts {'exact': 57944, 'published': 22881}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: Rows with contractEvidence.observedActiveContract.observedAt (from 2026-07-23): exact, fetched_utc = observedAt. Earlier rows: published, available_utc = regularMarketTime (Yahoo's delayed feed shows a trade roughly 10-15 minutes after it prints, so true availability is later than this bound).
- note: Native unit: USD (gold/silver per troy oz, copper per lb, crude per bbl).
- note: Delayed source by construction.
- note: extra_json keys seen: adapterSource (10), price (10), sourceEventTs (10), ticker (10), wsQuote (1)

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | comex \| nymex |
| `symbol` | `string` | Yahoo continuous ticker (GC=F, SI=F, HG=F, CL=F) |
| `status` | `string` | delayed |
| `price` | `double` | regularMarketPrice, USD (gold/silver per oz, copper per lb, crude per bbl) |
| `regular_market_time_utc` | `timestamp[us, tz=UTC]` | Yahoo regularMarketTime = raw ts (provider event time of a delayed feed) |
| `short_name` | `string` | Yahoo shortName |
| `exchange` | `string` | Yahoo exchange label |
| `instrument_type` | `string` | Yahoo instrumentType |
| `previous_close` | `double` | Yahoo previousClose |
| `regular_market_volume` | `double` | Yahoo regularMarketVolume |
| `active_contract_symbol` | `string` | observedActiveContract.symbol (dated contract, e.g. GCZ26.CMX) |
| `active_contract_id` | `string` | observedActiveContract.contractId |
| `active_contract_month` | `string` | observedActiveContract.contractMonth |
| `advertised_contract_month` | `string` | continuousAlias.advertisedContractMonth |
| `provider_market_time_utc` | `timestamp[us, tz=UTC]` | observedActiveContract.providerMarketTime |
| `observed_utc` | `timestamp[us, tz=UTC]` | observedActiveContract.observedAt: the feed's capture clock (from 2026-07-23) |
| `verification` | `string` | observedActiveContract.verification |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/quotes/hl_quotes.parquet`

- rows: 6,696,056; bytes: 228,159,672; sha256: `4e4bf1f6acd5891788294a660bf2a06ea112a69574ecfe2137d3f6fbe2a05de0`
- date range (fetched_utc): 2026-06-22T11:30:19.349218+00:00 to 2026-10-23T21:39:30.173798+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 6696056}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: ts is datetime.now(UTC) at the poll by the upstream collector: exact; available_utc = fetched_utc.
- note: Native unit: USD per contract unit of the xyz perpetual.
- note: assetMeta (margin tiers, max leverage) is kept in extra_json.
- note: The broker account object (always null in this source) is removed by the reader.
- note: extra_json keys seen: assetMeta (2555782)

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | hyperliquid |
| `instrument` | `string` | xyz:GOLD \| xyz:SILVER \| xyz:COPPER \| xyz:CL |
| `status` | `string` | feed status |
| `price` | `double` | Reading.price, USD: WS price when price_source is ws:*, else markPx |
| `price_source` | `string` | ws:<kind> \| rest:metaAndAssetCtxs \| null (pre-2026-07 rows) |
| `bid` | `double` | l2Book best bid, USD |
| `ask` | `double` | l2Book best ask, USD |
| `bid_qty` | `double` | l2Book best bid size, contracts |
| `ask_qty` | `double` | l2Book best ask size, contracts |
| `mid` | `double` | metaAndAssetCtxs midPx, USD |
| `mark` | `double` | raw markPx: the row price (see price_source) |
| `oracle` | `double` | metaAndAssetCtxs oraclePx, USD |
| `funding` | `double` | metaAndAssetCtxs funding (hourly rate, as received) |
| `open_interest` | `double` | metaAndAssetCtxs openInterest, contracts |
| `day_notional_volume` | `double` | metaAndAssetCtxs dayNtlVlm, USD notional / 24h |
| `premium` | `double` | metaAndAssetCtxs premium, as received |
| `snapshot_ts_utc` | `timestamp[us, tz=UTC]` | raw snapshotTs = capture clock (null in pre-2026-07 rows; equals fetched_utc otherwise) |
| `l2_event_utc` | `timestamp[us, tz=UTC]` | raw l2EventTs: l2Book event time |
| `sz_decimals` | `int64` | szDecimals |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/quotes/mcx_quotes.parquet`

- rows: 1,532,825; bytes: 63,989,284; sha256: `5a5dedfca5c54f7e9cdff27cfa94db2ec245f409e1e8d23e4eec82b3dbe7ab07`
- date range (fetched_utc): 2026-06-22T11:30:22.386100+00:00 to 2026-10-23T17:59:58+00:00
- clock quality: mixed; per-row column `clock_quality` with counts {'exact': 363763, 'published': 1169062}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: Rows without a transport key (2026-06-22..2026-07-14 polling era) have ts stamped by the feed at the poll: exact, available_utc = fetched_utc. Rows with transport angel_ws/angel_rest have ts = the exchange timestamp (Reading.ts), not a capture clock: published, available_utc = max(ts, exchFeedTime, exchTradeTime). Capture followed within the collector's freshness window for live rows (WS delivery; REST fetch - exchFeedTime <= 60 s) and with unbounded lag for delayed rows.
- note: Native unit: INR per exchange unit; gold 10 g, silver 1 kg, copper 1 kg, crude 1 bbl.
- note: dated_contract rows come from the reading's dated-contract block (from 2026-09-07): the 2nd and 3rd dated contracts polled by REST in the same cycle; deduplicated on (ts, entry hash) separately from reading rows.
- note: Empty depth levels (price 0, quantity 0, orders 0) are stored as null.
- note: A websocket reading whose raw ts is its own last_traded_timestamp_ms read as milliseconds (1970-01-21; the feed stamped readings so on 2026-09-28 from 03:30 to 04:57 UTC, while Angel sends that field in seconds) is stamped with the instant the field states: fetched_utc, session_date and exch_trade_time_utc follow it, and available_utc stays the latest of the row's stamps, which is the exchange feed time.
- note: Dropped raw keys with constant or duplicate content: contractEvidence.authenticatedSearchRow (= symbol/token), scripMasterRow.exch_seg/instrumenttype/strike/is_cas_enabled/name, resolved.* (= symbol/token/expiry), fullQuote.exchange/tradingSymbol/symbolToken, marginEvidence.source/currency/requestQuantity/nativeInstrument.
- note: The broker account object of the raw rows is removed by the reader before typing; it never reaches a frame.
- note: extra_json keys seen: depth_quantity_unit (382794), ws_received_at (382794)

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `origin` | `string` | reading = the upstream reading itself; dated_contract = a 2nd/3rd dated contract polled in the same cycle |
| `session_date` | `date32[day]` | Asia/Kolkata civil date of fetched_utc |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | mcx |
| `contract_id` | `string` | mcx:<SYMBOL> as in the feed's source tag |
| `symbol` | `string` | Angel tradingsymbol, exactly as received |
| `token` | `string` | Angel symboltoken, exactly as received |
| `expiry_date` | `date32[day]` | contract expiry from Angel expiry (DDMONYYYY) |
| `ltp` | `double` | last traded price, INR per exchange unit (gold: 10 g; silver: 1 kg; copper: 1 kg; crude: 1 bbl) |
| `day_open` | `double` | Angel open, INR |
| `day_high` | `double` | Angel high, INR |
| `day_low` | `double` | Angel low, INR |
| `previous_close` | `double` | Angel close = previous session close, INR |
| `open_interest` | `double` | Angel opnInterest, lots |
| `volume` | `double` | Angel tradeVolume: cumulative session volume, lots |
| `exch_trade_time_utc` | `timestamp[us, tz=UTC]` | Angel exchTradeTime (IST parsed to UTC); WS rows: the tick exchange timestamp |
| `exch_feed_time_utc` | `timestamp[us, tz=UTC]` | Angel exchFeedTime (IST parsed to UTC); WS rows: the tick exchange timestamp |
| `bid_px_1` | `double` | Angel depth.buy[0].price, INR; null when the level is empty |
| `bid_qty_1` | `double` | Angel depth.buy[0].quantity, lots |
| `bid_orders_1` | `int64` | Angel depth.buy[0].orders |
| `bid_px_2` | `double` | Angel depth.buy[1].price, INR; null when the level is empty |
| `bid_qty_2` | `double` | Angel depth.buy[1].quantity, lots |
| `bid_orders_2` | `int64` | Angel depth.buy[1].orders |
| `bid_px_3` | `double` | Angel depth.buy[2].price, INR; null when the level is empty |
| `bid_qty_3` | `double` | Angel depth.buy[2].quantity, lots |
| `bid_orders_3` | `int64` | Angel depth.buy[2].orders |
| `bid_px_4` | `double` | Angel depth.buy[3].price, INR; null when the level is empty |
| `bid_qty_4` | `double` | Angel depth.buy[3].quantity, lots |
| `bid_orders_4` | `int64` | Angel depth.buy[3].orders |
| `bid_px_5` | `double` | Angel depth.buy[4].price, INR; null when the level is empty |
| `bid_qty_5` | `double` | Angel depth.buy[4].quantity, lots |
| `bid_orders_5` | `int64` | Angel depth.buy[4].orders |
| `ask_px_1` | `double` | Angel depth.sell[0].price, INR; null when the level is empty |
| `ask_qty_1` | `double` | Angel depth.sell[0].quantity, lots |
| `ask_orders_1` | `int64` | Angel depth.sell[0].orders |
| `ask_px_2` | `double` | Angel depth.sell[1].price, INR; null when the level is empty |
| `ask_qty_2` | `double` | Angel depth.sell[1].quantity, lots |
| `ask_orders_2` | `int64` | Angel depth.sell[1].orders |
| `ask_px_3` | `double` | Angel depth.sell[2].price, INR; null when the level is empty |
| `ask_qty_3` | `double` | Angel depth.sell[2].quantity, lots |
| `ask_orders_3` | `int64` | Angel depth.sell[2].orders |
| `ask_px_4` | `double` | Angel depth.sell[3].price, INR; null when the level is empty |
| `ask_qty_4` | `double` | Angel depth.sell[3].quantity, lots |
| `ask_orders_4` | `int64` | Angel depth.sell[3].orders |
| `ask_px_5` | `double` | Angel depth.sell[4].price, INR; null when the level is empty |
| `ask_qty_5` | `double` | Angel depth.sell[4].quantity, lots |
| `ask_orders_5` | `int64` | Angel depth.sell[4].orders |
| `status` | `string` | feed status: live \| delayed |
| `transport` | `string` | angel_ws \| angel_rest \| null (2026-06-22..07-14 REST polling era) |
| `exchange_timestamp_ms` | `int64` | Angel WS exchange_timestamp (ms since epoch) |
| `last_traded_timestamp_ms` | `int64` | Angel WS last_traded_timestamp as received (unit as received) |
| `sequence_number` | `int64` | Angel WS sequence_number |
| `usd_per_unit` | `double` | feed-derived USD per standard unit (oz/lb/bbl) using usdinr; derived, not native |
| `usdinr` | `double` | USD/INR rate the feed applied at capture |
| `lot_size` | `double` | Angel scrip master lotsize |
| `tick_size` | `double` | Angel scrip master tick_size as received (paise) |
| `freeze_qty` | `double` | Angel scrip master freeze_qty |
| `margin_per_unit_inr` | `double` | Angel margin API: one-lot carry-forward margin, INR (instrument-level, not account data) |
| `margin_observed_utc` | `timestamp[us, tz=UTC]` | when the margin figure was observed |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/quotes/moneyplant_quotes.parquet`

- rows: 1,940,091; bytes: 88,214,910; sha256: `eb13f0557ad6ef5670e223b157f5430a2740c33eb517dbe3418c1de646cf16f9`
- date range (fetched_utc): 2026-07-21T18:36:08.298258+00:00 to 2026-10-23T21:00:29.149733+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 1940091}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: fetched_utc = raw linuxReceivedTs (feed receive clock), else raw fetchTs (bridge capture clock): exact. available_utc = fetched_utc (the bridge's own availabilityTs is a few hundred ms earlier and is not used as the pack clock). Rows with neither clock would be published on eventTs; none observed.
- note: Native unit: USD per contract unit as quoted by MT5 (COMEX/NYMEX futures, XAU/XAG spot).
- note: terminalSession (opaque session id) and clockCalibratedTs are dropped; the dated-contract block is always empty in this source and dropped.
- note: The broker account object of the raw rows is removed by the reader; it never reaches a frame.
- note: extra_json keys seen: regeneratedAt (33286), regeneratedFrom (33286)

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `event_utc` | `timestamp[us, tz=UTC]` | raw eventTs = source (MT5) event time = raw ts |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | comex \| nymex \| london_spot |
| `native_symbol` | `string` | MT5 symbol exactly as received (GCZ26, XAUUSD, ...) |
| `status` | `string` | live \| stale (stale = event older than 30 s at receipt or historical replay) |
| `price` | `double` | Reading.price, USD: (bid+ask)/2 when both present, else last |
| `bid` | `double` | bid, USD |
| `ask` | `double` | ask, USD |
| `last` | `double` | last, USD |
| `bridge_fetch_utc` | `timestamp[us, tz=UTC]` | raw fetchTs: bridge capture clock |
| `linux_received_utc` | `timestamp[us, tz=UTC]` | raw linuxReceivedTs: feed receive clock |
| `hydrated_utc` | `timestamp[us, tz=UTC]` | raw hydratedTs |
| `selected_utc` | `timestamp[us, tz=UTC]` | raw selectedTs |
| `hydration_ms` | `int64` | raw hydrationMs |
| `clock_correction_sec` | `double` | source clock correction applied to sourceEventEpochMs |
| `clock_max_residual_ms` | `double` | raw clockMaxResidualMs |
| `clock_samples` | `int64` | raw clockSamples |
| `connection_generation` | `int64` | raw connectionGeneration |
| `snapshot_sequence` | `int64` | raw snapshotSequence |
| `protocol` | `string` | bridge protocol version (v1 \| v2) |
| `volume` | `double` | tick volume |
| `volume_real` | `double` | tick volume_real |
| `session_volume` | `double` | symbol_info.session_volume |
| `session_turnover` | `double` | symbol_info.session_turnover |
| `session_interest` | `double` | symbol_info.session_interest (open interest) |
| `volume_high` | `double` | symbol_info volume high |
| `volume_low` | `double` | symbol_info volume low |
| `market_book_json` | `string` | raw marketBook (JSON) when present |
| `instrument_metadata_json` | `string` | raw instrumentMetadata (JSON): contract size, exchange, path, tick |
| `trading_specification_json` | `string` | raw tradingSpecification (JSON) |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/quotes/reference_quotes.parquet`

- rows: 7,110,177; bytes: 66,162,840; sha256: `1ff810e27ca12c2e64e74d57725fce197692520a9eab5c7e1bb3e0ef53ff7401`
- date range (fetched_utc): 2026-06-19T00:00:00+00:00 to 2026-10-23T21:40:03.968657+00:00
- clock quality: mixed; per-row column `clock_quality` with counts {'exact': 6968263, 'published': 141824, 'unvintaged': 90}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: shfe/ine: ts = datetime.now(UTC) at the Sina poll: exact. lbma: ts = the auction time (gold 15:00, silver 12:00 London): published. goldapi: ts = provider updatedAt: published. investing: ts = the bar time of a delayed chart API: published. lme_westmetall: the source gives a date only (timestamp_precision = date): unvintaged; raw_file_date bounds availability from above.
- note: Units: lbma USD/GBP/EUR per troy oz; lme USD per tonne; shfe/ine CNY per cny_unit; goldapi USD per oz; investing USD.
- note: Consecutive identical polls of daily references (lbma, lme_westmetall, goldapi, investing) collapse under the (ts, payload) dedup rule; counts are in per_file.
- note: extra_json keys seen: cash_usd_per_lb (17)

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `source` | `string` | lbma \| lme_westmetall \| shfe \| ine \| goldapi \| investing |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | lbma \| lme \| shfe \| ine \| london_spot \| comex |
| `source_tag` | `string` | feed source tag exactly as received |
| `symbol` | `string` | provider symbol exactly as received |
| `status` | `string` | feed status |
| `price` | `double` | Reading.price in currency |
| `currency` | `string` | price currency |
| `fix_date` | `date32[day]` | lbma: auction date |
| `usd` | `double` | lbma: USD fix |
| `gbp` | `double` | lbma: GBP fix |
| `eur` | `double` | lbma: EUR fix |
| `cash_settlement_usd_per_tonne` | `double` | lme_westmetall: cash settlement, USD/t |
| `three_month_usd_per_tonne` | `double` | lme_westmetall: 3-month, USD/t |
| `published_date` | `date32[day]` | lme_westmetall: published date (date precision only) |
| `trade_date` | `date32[day]` | shfe/ine: Sina trading date |
| `cny_price` | `double` | shfe/ine: price in CNY per cny_unit |
| `cny_unit` | `string` | shfe/ine: CNY/g \| CNY/kg \| CNY/t \| CNY/bbl |
| `open` | `double` | shfe/ine: session open, CNY |
| `high` | `double` | shfe/ine: session high, CNY |
| `low` | `double` | shfe/ine: session low, CNY |
| `settle` | `double` | shfe/ine: settle as received (0.0 before settlement) |
| `prev_settle` | `double` | shfe/ine: previous settlement, CNY |
| `volume` | `double` | shfe/ine: volume as received; investing: volume |
| `open_interest` | `double` | shfe/ine: openInterest as received |
| `usd_per_unit` | `double` | shfe/ine: feed-derived USD per standard unit (derived) |
| `usdcny` | `double` | shfe/ine: USD/CNY the feed applied |
| `updated_utc` | `timestamp[us, tz=UTC]` | goldapi: provider updatedAt |
| `name` | `string` | goldapi name / investing description |
| `pair_id` | `int64` | investing: pairId |
| `kind` | `string` | investing: kind |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/quotes/te_quotes.parquet`

- rows: 5,013,533; bytes: 43,469,938; sha256: `8273604fb50a56dca1577a89e5f79382b00f62c7e56488a0587c548f4285801f`
- date range (fetched_utc): 2026-06-22T11:30:20.577320+00:00 to 2026-10-23T21:39:42.332489+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 5013533}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: ts is datetime.now(UTC) at the poll by the upstream collector: exact; available_utc = fetched_utc.
- note: Native unit: USD.

| column | type | meaning |
|---|---|---|
| `fetched_utc` | `timestamp[us, tz=UTC]` | feed observation clock for the row (raw ts unless a capture clock exists in the payload; see rule) |
| `available_utc` | `timestamp[us, tz=UTC]` | availability lower bound: = fetched_utc for exact rows, source-stated instant for published rows, null for unvintaged |
| `clock_quality` | `string` | exact \| published \| unvintaged (see README.md, Clock quality) |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | london_spot (XAU/XAG spot) \| comex (HG1) \| nymex (CL1) |
| `symbol` | `string` | TE symbol exactly as received |
| `status` | `string` | feed status |
| `price` | `double` | price, USD (spot per oz; HG1 per lb; CL1 per bbl) |
| `nch` | `double` | TE net change as received (diagnostic; not reconciled) |
| `pch` | `double` | TE percent change as received (diagnostic; not reconciled) |
| `raw_file_date` | `date32[day]` | UTC day the feed appended the row (raw file name); availability is never later than the end of this day |
| `extra_json` | `string` | residual raw keys with no typed column (JSON object) or null |

## `pack/receipts/cot_record_receipts.parquet`

- rows: 52; bytes: 16,012; sha256: `42bba379e477d3a3adb929748c823ab0332a4fb7b690ed6f9c8b81ffc026a58d`
- date range (fetched_utc): 2026-07-29T10:49:58.282969+00:00 to 2026-10-16T21:50:40.702735+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 52}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: fetched_ts is the feed's own capture clock: exact. The CFTC release instant the feed recorded is kept as release_utc.
- note: Only the records the production feed fetched (33 rows); the macro lane carries the full CFTC history.

| column | type | meaning |
|---|---|---|
| `receipt_id` | `string` | feed.cot_record_receipts_v1.receipt_id |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `contract_market_code` | `string` | CFTC market code |
| `report_date` | `date32[day]` | COT report date (Tuesday) |
| `source_payload_hash` | `string` | hash of the CFTC payload |
| `release_utc` | `timestamp[us, tz=UTC]` | available_ts as recorded by the feed: the CFTC release instant it applied |
| `fetched_utc` | `timestamp[us, tz=UTC]` | fetched_ts: the feed's fetch clock |
| `available_utc` | `timestamp[us, tz=UTC]` | = fetched_utc (the feed had the record then; release_utc is the earlier CFTC instant) |
| `clock_quality` | `string` | exact |
| `payload_json` | `string` | the CFTC record as stored |

## `pack/receipts/fx_rate_receipts.parquet`

- rows: 1,872,796; bytes: 99,637,499; sha256: `6458d165bede28acf143adebbb63189e060354e57d6da5d979d5011f54027796`
- date range (fetched_utc): 2026-07-22T03:55:25.247581+00:00 to 2026-10-23T21:40:35.796104+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 1872796}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: fetched_ts is the feed's own capture clock: exact.
- note: These are the live USD/INR and USD/CNY rates the feed applied to MCX and SHFE/INE conversions.

| column | type | meaning |
|---|---|---|
| `receipt_id` | `string` | feed.fx_rate_receipts_v1.receipt_id |
| `pair` | `string` | USDINR \| USDCNY \| ... |
| `rate` | `double` | rate as received |
| `source` | `string` | te:USDINR:CUR, te-ws:..., etc. |
| `event_utc` | `timestamp[us, tz=UTC]` | event_ts |
| `recorded_utc` | `timestamp[us, tz=UTC]` | recorded_ts |
| `fetched_utc` | `timestamp[us, tz=UTC]` | fetched_ts: the feed's fetch clock |
| `available_utc` | `timestamp[us, tz=UTC]` | available_ts as recorded by the feed |
| `clock_quality` | `string` | exact |
| `clock_status` | `string` | feed clock_status label |

## `pack/receipts/reference_closes.parquet`

- rows: 4,126; bytes: 205,383; sha256: `93e66f6eac284e1688c309332fb8613c379314681ba1b97657612f4d1b97f1f1`
- date range (fetched_utc): 2026-07-14T16:01:26.246723+00:00 to 2026-10-23T21:11:48.823172+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 4126}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: fetched_ts is the feed's own capture clock: exact. effective_utc is the venue close, not a clock.
- note: MCX rows (angel:FULL:close) are the previous-session close the broker quote carried at the next open; verified=false for those.

| column | type | meaning |
|---|---|---|
| `receipt_id` | `string` | feed.reference_closes.receipt_id |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `venue` | `string` | mcx \| comex \| nymex \| ice_brent \| lbma \| lme \| shfe \| ine |
| `session_date` | `date32[day]` | session the value closes (venue-local civil date) |
| `value` | `double` | close / settlement value in currency |
| `currency` | `string` | value currency |
| `kind` | `string` | exchange_close \| official_settlement \| session_close |
| `effective_utc` | `timestamp[us, tz=UTC]` | documented venue close instant for session_date |
| `source` | `string` | feed source path (e.g. angel:FULL:close, yahoo:GCZ26.CMX:chart:1d) |
| `instrument_symbol` | `string` | provider instrument symbol |
| `contract_id` | `string` | venue:SYMBOL contract id |
| `contract_month` | `string` | YYYY-MM contract month |
| `first_seen_utc` | `timestamp[us, tz=UTC]` | first time the feed saw this value |
| `fetched_utc` | `timestamp[us, tz=UTC]` | fetched_ts: the feed's fetch clock |
| `available_utc` | `timestamp[us, tz=UTC]` | available_ts as recorded by the feed (= fetched_ts) |
| `clock_quality` | `string` | exact |
| `verified` | `bool` | feed verified the session/publication semantics |

## `pack/state/mcx_hourly_state.parquet`

- rows: 5,792; bytes: 419,035; sha256: `217bfc708bd4a726a4b251dcfe26161c2c9beed23dedd512d02bc7b500c52ca0`
- date range (asof_utc): 2026-06-17T03:00:00+00:00 to 2026-10-23T17:30:00+00:00
- clock quality: exact; per-row column `clock_quality` with counts {'exact': 5792}; clocks {'exact': 'fetched_utc', 'published': 'available_utc'}
- rule: asof_utc is the availability clock by construction: every input row has its own availability clock strictly before asof_utc.
- note: grid: 2026-06-17 to 2026-10-23, asof points 08:30 IST plus hour boundaries inside the published session, truncated at the capture end 2026-10-23T17:59:59+00:00
- note: sessions: mcx lane: build:mcx/mcx_sessions.parquet
- note: settlements: {'settlements': 'mcx_daily', 'path': 'build:mcx/mcx_daily.parquet', 'sha256': '284057f8d01ec1c5f4b5f2dce2557c406c8f054393a991bfcb22267374fcc405', 'clock_column': 'available_utc', 'value_column': 'settlement', 'rows': 32184}
- note: definitions.md beside this file states every formula, window, and mask rule

| column | type | meaning |
|---|---|---|
| `asof_utc` | `timestamp[us, tz=UTC]` | evaluation instant; every input row has availability clock < asof_utc |
| `fetched_utc` | `timestamp[us, tz=UTC]` | = asof_utc: the row is knowable at asof_utc by construction |
| `available_utc` | `timestamp[us, tz=UTC]` | = asof_utc |
| `clock_quality` | `string` | exact (derived at asof from inputs strictly before it) |
| `session_date` | `date32[day]` | MCX session (IST civil date) the asof point belongs to |
| `asof_ist` | `string` | asof as HH:MM IST |
| `asset` | `string` | gold \| silver \| copper \| crude |
| `contract_id` | `string` | contract of the last MCX quote before asof (null when none) |
| `last_quote_session_date` | `date32[day]` | session_date of the last MCX quote before asof |
| `last_quote_status` | `string` | feed status of that quote |
| `last_ltp` | `double` | ltp of the last MCX quote before asof, INR |
| `quote_age_s` | `double` | asof - exchange trade time of that quote (poll time for 2026-06-22..07-14 rows), seconds |
| `settle_mean_20s` | `double` | mean of the last 20 available session settlements before the row's session, INR |
| `settle_rv_20s` | `double` | sample std of the 19 log returns between those settlements |
| `settle_window_start_date` | `date32[day]` | earliest session in the 20-settlement window |
| `settle_contracts_n` | `int64` | distinct contracts inside the window (1 = same-contract series) |
| `stretch_20s` | `double` | (last_ltp / settle_mean_20s - 1) / settle_rv_20s |
| `oi_last` | `double` | open interest on the last MCX quote with OI before asof, lots |
| `oi_1s_change` | `double` | oi_last / oi at the end of the previous session (same contract) - 1 |
| `oi_5s_change` | `double` | oi_last / oi at the end of the 5th previous session (same contract) - 1 |
| `oi_price_class` | `string` | liquidation \| new_shorts \| new_longs \| short_covering \| flat |
| `book_imbalance_5` | `double` | (sum bid_qty_1..5 - sum ask_qty_1..5) / (sum bid + sum ask) on the last quote |
| `spread_bp` | `double` | (ask_px_1 - bid_px_1) / mid * 1e4 on the last quote |
| `volume_pace_ratio` | `double` | session volume so far / mean of the same-clock-time volume over the previous 5 sessions (same contract) |
| `volume_pace_n` | `int64` | reference sessions used by volume_pace_ratio |
| `open_gap_pct` | `double` | (day_open - previous_close) / previous_close on the current session's last quote |
| `gap_absorption` | `double` | (day_open - last_ltp) / (day_open - previous_close) on the current session's last quote |
| `mcx_ret_1h` | `double` | ln(last_ltp / ltp one hour earlier), same session and contract |
| `hl_ret_1h` | `double` | ln(HL price / HL price one hour earlier) |
| `hl_agreement_1h` | `double` | sign(mcx_ret_1h) * sign(hl_ret_1h): 1 agree, -1 disagree, 0 either flat |
| `hl_funding` | `double` | funding on the last HL quote before asof (must be < 15 min old) |
| `comex_ret_1h` | `double` | ln(comparator price / price one hour earlier) |
| `comex_agreement_1h` | `double` | sign(mcx_ret_1h) * sign(comex_ret_1h) |
| `comex_leg` | `string` | comparator used: moneyplant:<symbol> or te:<symbol> |
| `mask_last_ltp` | `bool` | true when last_ltp is null (not computable from data before asof) |
| `mask_stretch_20s` | `bool` | true when stretch_20s is null (not computable from data before asof) |
| `mask_oi_1s_change` | `bool` | true when oi_1s_change is null (not computable from data before asof) |
| `mask_oi_5s_change` | `bool` | true when oi_5s_change is null (not computable from data before asof) |
| `mask_oi_price_class` | `bool` | true when oi_price_class is null (not computable from data before asof) |
| `mask_book_imbalance_5` | `bool` | true when book_imbalance_5 is null (not computable from data before asof) |
| `mask_spread_bp` | `bool` | true when spread_bp is null (not computable from data before asof) |
| `mask_quote_age_s` | `bool` | true when quote_age_s is null (not computable from data before asof) |
| `mask_volume_pace_ratio` | `bool` | true when volume_pace_ratio is null (not computable from data before asof) |
| `mask_gap_absorption` | `bool` | true when gap_absorption is null (not computable from data before asof) |
| `mask_hl_agreement_1h` | `bool` | true when hl_agreement_1h is null (not computable from data before asof) |
| `mask_hl_funding` | `bool` | true when hl_funding is null (not computable from data before asof) |
| `mask_comex_agreement_1h` | `bool` | true when comex_agreement_1h is null (not computable from data before asof) |

## `swings/swing_sessions.parquet`

- rows: 5,908; bytes: 79,486; sha256: `2d5e3421b13bc3b9396cac44e13aba6dbe99e9fd056431691e5405b0f6dc5156`
- date range (session_date): 2021-02-01 to 2026-10-23
- clock quality: published; per-row column `clock_quality` with counts {'published': 5908}; clocks {'published': 'available_utc'}
- rule: A session row is available at the settlement publication of the session: that session's close instant from mcx_sessions, the same convention mcx_daily uses. The exchange publishes at or after the close and we did not capture at that instant, so the class is published. The row holds only what is known at that instant: the session's designation, bars, high, low and settlement. It carries nothing derived from the legs of swings.parquet, which are known only once confirmed.
- note: One row per (asset, session) over the designated-contract series, from the first designation to the last session with a Bhav Copy.
- note: eligible_cutoff is the coverage denominator of RULES.md section 5: the session has a designated contract and a priced bar, so a decision record is expected of a model.
- note: session_high, session_low and session_settlement are the designated contract's own Bhav Copy values, whatever the bar type; on an hourly session they bound the hourly bars but are the exchange's numbers, not ours.
- note: No column depends on a swing leg. A leg is known only when it is confirmed, which can be sessions after its extreme, and a row stamped at the session close could not be changed when the leg confirmed. To count the turns and extremes of a session, group the legs of swings.parquet by the Asia/Kolkata date of turn_utc and extreme_utc; the point-in-time client returns each leg from its confirm_available_utc.
- note: Price series: the contract of designations.parquet at horizon 5, session by session. Prices are the contract's own, never spread-adjusted; contract_changed marks a leg whose turn and extreme sit on different contracts, so its move includes the calendar spread.
- note: Bars: hourly highs and lows of ltp from pack/quotes/mcx_quotes.parquet, bucketed on available_utc floored to the Asia/Kolkata hour so a bar boundary falls on the 09:00 IST open. A quote counts only inside its session's own trading window from mcx_sessions; the 2026-06-22 to 2026-07-14 polling era also wrote rows outside trading hours and on closed days, carrying an already-settled last traded price, and those are not part of any bar.
- note: Before 2026-06-22 there are no intraday quotes and the bar is the Bhav Copy session high and low, marked daily. The same fallback covers the sessions after 2026-06-22 where the feed had not yet started polling the contract the designation rule had already moved to (for example silver 2026-08-31 to 2026-09-03 on the December contract).
- note: Within a bar the order of the high and the low is unknown. A bar that both reverses the threshold from the running extreme and makes a new extreme completes the leg: the extreme established in an earlier bar wins.

| column | type | meaning |
|---|---|---|
| `asset` | `string` | gold \| silver \| copper \| crude |
| `session_date` | `date32[day]` | Asia/Kolkata civil date of the MCX session |
| `contract_id` | `string` | designated contract for this session (designations.parquet, horizon 5); null when none qualified |
| `designation_eligible` | `bool` | the designation row's own eligible flag |
| `ineligible_reason` | `string` | the designation row's reason; null when eligible |
| `bar` | `string` | hourly \| daily \| none: the bar type this session contributed to the series |
| `bars` | `int64` | bars the session contributed: hours for an hourly session, 1 for a daily one, 0 for none |
| `ticks` | `int64` | quotes behind the hourly bars; 0 for a daily session |
| `session_high` | `double` | designated contract's Bhav Copy high, INR; null when it printed no trade |
| `session_low` | `double` | designated contract's Bhav Copy low, INR; null when it printed no trade |
| `session_settlement` | `double` | designated contract's Bhav Copy settlement, INR |
| `cutoff_utc` | `timestamp[us, tz=UTC]` | 08:30 Asia/Kolkata pre-open of this session, in UTC: the earliest instant a signal may carry this session's date |
| `eligible_cutoff` | `bool` | true when the session has a designated contract and a priced bar, so a decision record is expected of a model and the session counts in the coverage denominator |
| `period` | `string` | training (before 2026-06-01) \| holdout (RULES.md section 5) |
| `session_state` | `string` | open \| morning_only \| evening_only from mcx_sessions |
| `full_day` | `bool` | true when the session is open with no holiday shortening |
| `session_open_utc` | `timestamp[us, tz=UTC]` | first trading instant of the session |
| `available_utc` | `timestamp[us, tz=UTC]` | settlement publication of this session: its close instant |
| `clock_quality` | `string` | published |

## `swings/swings.parquet`

- rows: 2,150; bytes: 70,692; sha256: `2db9866d45deba3d8149a78792a9494765c1d206196f69b9467b8bcf4ab4cbee`
- date range (extreme_utc): 2021-02-02T03:30:00+00:00 to 2026-10-23T13:30:00+00:00
- clock quality: published; per-row column `clock_quality` with counts {'published': 2150}; clocks {'published': 'confirm_available_utc'}
- rule: A swing row is available from confirm_available_utc: the settlement publication of the session of the bar that completed the leg, that session's close instant from mcx_sessions, the same convention mcx_daily uses. A leg is only a swing once the price has reversed threshold_pct from its extreme, and that reversal can print sessions after the extreme, so no row is knowable earlier. The exchange publishes at or after the close and we did not capture at that instant, so the class is published. available_utc, the settlement publication of the session the extreme printed in, is a data column and not the availability of the row. The bar instants are not availability: an hourly bar carries the quotes' own clocks (mcx_quotes states exact or published per row) and a daily bar carries the session's opening instant, inside which the Bhav Copy high and low printed at an unknown time, and confirm_utc is a bar instant of that kind.
- note: One row per completed leg of the percent-threshold zigzag of RULES.md section 2, per asset.
- note: Price series: the contract of designations.parquet at horizon 5, session by session. Prices are the contract's own, never spread-adjusted; contract_changed marks a leg whose turn and extreme sit on different contracts, so its move includes the calendar spread.
- note: Bars: hourly highs and lows of ltp from pack/quotes/mcx_quotes.parquet, bucketed on available_utc floored to the Asia/Kolkata hour so a bar boundary falls on the 09:00 IST open. A quote counts only inside its session's own trading window from mcx_sessions; the 2026-06-22 to 2026-07-14 polling era also wrote rows outside trading hours and on closed days, carrying an already-settled last traded price, and those are not part of any bar.
- note: Before 2026-06-22 there are no intraday quotes and the bar is the Bhav Copy session high and low, marked daily. The same fallback covers the sessions after 2026-06-22 where the feed had not yet started polling the contract the designation rule had already moved to (for example silver 2026-08-31 to 2026-09-03 on the December contract).
- note: Within a bar the order of the high and the low is unknown. A bar that both reverses the threshold from the running extreme and makes a new extreme completes the leg: the extreme established in an earlier bar wins.
- note: A leg in progress at the last session is not a swing and is not written; the reversal that would complete it has not happened inside the data.
- note: A leg is knowable only when it is confirmed: the reversal that completes it can print sessions after its extreme. confirm_utc is the instant of that confirming bar and confirm_available_utc is the settlement publication of its session, the same convention mcx_daily uses. confirm_available_utc is the published clock of this file, so the point-in-time client returns a leg from there and never at its extreme. available_utc is the settlement publication of the session the extreme printed in: a data column that says when the extreme's own session published, and a consumer that reads this file without the client must filter on confirm_available_utc, not on available_utc.
- note: Both confirmation columns are non-null on every row, because a leg is only written once it has completed. confirm_utc is at or after extreme_utc and confirm_available_utc is at or after confirm_utc; stats.json carries the distribution of confirm_available_utc minus available_utc in sessions, per asset.
- note: The confirming bar can sit on a different contract from the leg. A roll between the extreme and the reversal leaves contract_changed false on this leg and true on the next one, which is the leg whose own turn-to-extreme span crosses the roll; contract_changed is a statement about the leg's own span and never about the bar that confirmed it.
- note: The 1-sigma barrier labels of version 2.4 under build/labels/ are untouched and ship as research.
- note: The zigzag reads bars in order, so a leg's fields depend on no bar after its confirming bar. On the same inputs, a build stopped at an earlier session writes exactly the rows of the later build whose confirm_available_utc falls on or before that session's close, and the later build adds the legs confirmed since.

| column | type | meaning |
|---|---|---|
| `asset` | `string` | gold \| silver \| copper \| crude |
| `direction` | `string` | up \| down: the sign of the move from the turn to the extreme |
| `turn_utc` | `timestamp[us, tz=UTC]` | start instant of the bar the turn printed in (the previous leg's extreme) |
| `turn_price` | `double` | price at the turn: that bar's low for an up leg, its high for a down leg, INR per exchange unit |
| `extreme_utc` | `timestamp[us, tz=UTC]` | start instant of the bar the extreme printed in |
| `extreme_price` | `double` | price at the extreme: that bar's high for an up leg, its low for a down leg, INR per exchange unit |
| `move_pct` | `double` | signed (extreme_price - turn_price) / turn_price * 100; its magnitude is at least threshold_pct |
| `sessions_spanned` | `int64` | MCX trading sessions from the turn's session to the extreme's session, inclusive |
| `contract_id` | `string` | designated contract the extreme printed on; the turn's contract differs exactly when contract_changed |
| `contract_changed` | `bool` | true when the designation rolled between the turn bar and the extreme bar, so the two prices are of different contracts and the move includes the calendar spread |
| `bar` | `string` | hourly \| daily \| mixed: the bar type behind the leg's bars |
| `threshold_pct` | `double` | the asset's swing threshold in percent (RULES.md section 2) |
| `available_utc` | `timestamp[us, tz=UTC]` | settlement publication of the session the extreme printed in: that session's close instant. A data column. It is not the availability of the row: the leg is not knowable until confirm_available_utc, which is at or after this instant on every row |
| `confirm_utc` | `timestamp[us, tz=UTC]` | start instant of the bar whose move completed the leg: the first bar to reverse threshold_pct from the extreme. At or after extreme_utc on every row |
| `confirm_available_utc` | `timestamp[us, tz=UTC]` | settlement publication of the session the confirming bar printed in, the same convention available_utc uses. The earliest instant this leg is knowable as a swing and the published clock of this file: the point-in-time client returns the row from here |
| `clock_quality` | `string` | published |
