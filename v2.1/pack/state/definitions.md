# mcx_hourly_state definitions

Grid: one row per asset per asof point. Asof points of a session are 08:30 IST and every hour
boundary H:00 IST with open <= H:00 < close (regular days 09:00 to 23:00, evening-only days
17:00 to 23:00, morning-only days 09:00 to 16:00). Sessions come from `build/mcx/mcx_sessions.parquet`
when present, else the built-in 2026 rules (see `sessions.py`). The grid starts 2026-06-17 and stops
at the last asof point on or before the last captured MCX quote.

Availability: every input row is used only if its availability clock (`available_utc`, which equals
`fetched_utc` for exact rows) is strictly before `asof_utc`. "Last quote" always means the MCX
`origin = reading` row with the largest `available_utc < asof_utc` for the asset; ties keep file order.
`session_date` of that quote is `S_last` (it is the previous session at 08:30).

Features (null and `mask_<feature> = true` when not computable):

- `last_ltp`: `ltp` of the last quote. Masked when no quote exists before asof.
- `quote_age_s`: `asof_utc - exch_trade_time_utc` of the last quote in seconds; for 2026-06-22..07-14
  rows (no exchange time) the poll time `fetched_utc` is used. Masked with `last_ltp`.
- `stretch_20s`: `(last_ltp / settle_mean_20s - 1) / settle_rv_20s`. The settlement window is the last
  20 sessions with a settlement whose `session_date` is before the row's `session_date` and whose
  `available_utc < asof_utc` (with `reference_closes` the previous session's close arrives at the next
  09:00 open, so the 08:30 row's window ends one session earlier; with the Bhav Copy it is available from
  the previous close). Per session the
  settlement of the last quote's contract is preferred; otherwise the front month that session (the unexpired
  contract with the earliest expiry), so the series is front-month continuous when the current contract was not
  yet listed; `settle_contracts_n` counts the distinct contracts (1 = same contract throughout).
  When a session has several receipts for the chosen contract, the earliest-available one is used: the feed's
  `reference_closes` also files the next session's close under the previous session's label at 23:30 IST, and
  that later receipt is ignored.
  `settle_mean_20s` is the arithmetic mean of the 20 values; `settle_rv_20s` is the sample standard deviation
  (ddof 1) of the 19 log returns between consecutive values. Masked when fewer than 20 sessions are available,
  or `settle_rv_20s = 0`. Source: the mcx lane's `mcx_daily.parquet` (exchange Bhav Copy, whole curve) when it
  exists; its availability instant is the file's own clock column when it has one, else the session close from
  the calendar (the Bhav Copy is published after the close; class published). Otherwise the feed's
  `reference_closes` MCX `exchange_close` rows with their `available_ts`. The meta records which was used.
- `oi_last`: `open_interest` of the last quote in `S_last` carrying OI (falls back to the last row with OI).
- `oi_1s_change`: `oi_last / oi_ref - 1` where `oi_ref` is the OI of the last quote (available before asof)
  in the session one trading day before `S_last` (calendar), same `contract_id`. Masked when that session has
  no OI, the contract differs (roll), or `oi_ref <= 0`.
- `oi_5s_change`: same with the session five trading days before `S_last`.
- `oi_price_class`: with `dp = last_ltp - previous_close` (the last quote's own `previous_close`, the
  exchange's prior-session close for that contract) and `doi = oi_last - oi_ref` (the 1-session reference):
  `flat` when `dp = 0` or `doi = 0`; `new_longs` (dp > 0, doi > 0); `short_covering` (dp > 0, doi < 0);
  `new_shorts` (dp < 0, doi > 0); `liquidation` (dp < 0, doi < 0). Masked when any input is missing.
- `book_imbalance_5`: `(sum bid_qty_1..5 - sum ask_qty_1..5) / (sum bid_qty + sum ask_qty)` over the present
  levels of the last quote. Masked when the last quote has no level-1 quantities on both sides.
- `spread_bp`: `(ask_px_1 - bid_px_1) / ((ask_px_1 + bid_px_1) / 2) * 1e4` on the last quote. Masked without both.
- `volume_pace_ratio`: only when `S_last` is the current session. `vol_now` is the cumulative session `volume`
  of the last quote in the session (same contract). For each of the previous 5 trading sessions, the reference
  is the `volume` of the last quote in that session whose IST time-of-day is <= the IST time-of-day of the
  `vol_now` quote, same contract. Ratio = `vol_now / mean(references)`; needs at least 3 references
  (`volume_pace_n`). Masked otherwise, and always at 08:30.
- `open_gap_pct`: only when `S_last` is the current session: `(day_open - previous_close) / previous_close` on the
  last quote. Filter on it before reading `gap_absorption`; a one-tick gap makes the ratio arbitrarily large.
- `gap_absorption`: only when `S_last` is the current session: `(day_open - last_ltp) / (day_open - previous_close)`
  on the last quote (1 = gap fully closed, 0 = none, negative = extended). Masked when `day_open = previous_close`
  or a value is missing, and always at 08:30.
- `mcx_ret_1h`: `ln(p1 / p0)`, `p1` = ltp of the last quote (must be < 15 min old by availability),
  `p0` = ltp of the last quote with `available_utc < asof_utc - 1h` (must be at most 15 min older than that
  instant), same `session_date` and `contract_id`. Null otherwise (so at 08:30 and the first hour).
- `hl_ret_1h`: same rule on `hl_quotes.price` for the asset's `xyz` instrument.
- `hl_agreement_1h`: `sign(mcx_ret_1h) * sign(hl_ret_1h)` in {-1, 0, 1}. Masked when either return is null.
- `hl_funding`: `funding` of the last HL quote before asof, masked when that quote is 15 min old or older.
- `comex_ret_1h`, `comex_leg`: first leg that yields a return: `moneyplant` (venue comex/nymex rows, same
  `native_symbol` at both ends; leg label `moneyplant:<symbol>`), else `te` (`XAUUSD:CUR`, `XAGUSD:CUR`,
  `HG1:COM`, `CL1:COM`; label `te:<symbol>`), with the 1h rule above.
- `comex_agreement_1h`: `sign(mcx_ret_1h) * sign(comex_ret_1h)`. Masked when either is null.

Units: INR per exchange unit for MCX prices; lots for OI and volume; USD for HL and comparator legs.
