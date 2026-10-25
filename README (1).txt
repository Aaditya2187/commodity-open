Commodity Open 2026: kit and data pack

commodity-open-kit-2.6.3.zip        the participant kit: rules 2.6, scorer, template, notebooks, tools
commodity-open-pack-v2.1.tar.zst    the data pack, data to the close of Fri 23 Oct 2026
MANIFEST.json                       every table of the pack with its sha256 and row count
SHA256SUMS                          checksums of the three files above

Start here:
  sha256sum -c SHA256SUMS
  unzip commodity-open-kit-2.6.3.zip && tar --zstd -xf commodity-open-pack-v2.1.tar.zst
  then follow commodity-open-kit/README.md
tar needs a zstd program. If it stops with "zstd: Cannot exec: No such file or directory" (GNU tar) or
"unable to run program "zstd -d -qq"" (macOS), install one: brew install zstd (macOS), or
sudo apt install zstd unzip (Ubuntu, WSL).

The kit is Apache-2.0 (see its LICENSE and README.md). The pack and the second data file are for your
team's use in Commodity Open 2026 only: until the verdicts are sent they may not be shared outside the
team or redistributed in any form.

Questions: contact@commodity-open.xyz, quoting your ticket number.

CORRECTIONS TO PACK v2.1'S OWN DOCUMENTATION

The pack's data and its checksums are unchanged; this file is not covered by SHA256SUMS. Four statements in
the pack's README and MANIFEST are wrong, and one table carries four rows that should be ignored.

- mcx/mcx_sessions: the corrections list says v2.0.1's 43 rows carried a note reading the winter close as
  23:30. They carried no note; that text was the sidecar's file-level note, which called 23:30 a fallback.
  The change itself is as stated: 23:30 to 23:55 IST, unvintaged to published, hours_notified false.
- pack/quotes/moneyplant_quotes: the two declared gaps hold 67 and 52 rows, then 23 and 24. The bridge's spool
  holds 532 and 512 quotes in the first two hours and 504 in each of the second two; only 71 and 52, then 23
  and 27, arrived within 30 seconds of their event, and the pack takes only those. The rest sit in the spool at
  lags of minutes rather than being lost, and a later release can add them. Normal hours carry about 1,300 to
  1,600 quotes, so the wording "in a normal session" overstates what those hours used to hold.
- 2026-10-18, 13:42 to 13:49 UTC: the feed host stopped without a clean shutdown and the feed restarted after
  it. The five torn capture lines are a crash artifact, not two writers appending at once: the unfinished line
  has no newline, so the first append after the restart continued it. Every collector has a gap of about six
  minutes, and the five complete readings recovered from the torn lines are in the pack.
- pack/receipts/reference_closes holds four MCX close receipts with session_date 1970-01-20 and verified false,
  a date no session can have. They are dropped from the next release; ignore them here.
