#!/usr/bin/env python3
"""Timestamp-unit and availability regression tests for experiment 03 (stdlib unittest).

    python experiments/03_overnight_gap/test_units.py --pack ../../v2.1
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib  # noqa: E402

from swing_dataset.kit import loop  # noqa: E402
from swing_dataset.pack.pit import PointInTime  # noqa: E402
from swing_dataset.scoring2.prices import ns_of  # noqa: E402

PACK: Path | None = None
CUTOFF = pd.Timestamp("2026-06-01 03:00", tz="UTC")


class Units(unittest.TestCase):
    def test_microsecond_column_converts_to_ns(self):
        s = pd.Series(pd.to_datetime(["2026-03-02 17:59:59.999", "2026-03-03 02:59:59.999"], utc=True)).astype(
            "datetime64[us, UTC]"
        )
        got = gaplib.to_ns(s)
        self.assertEqual(list(got), [ns_of(v) for v in s])
        # The bug this guards against: raw asi8 on a microsecond index is 1000x smaller.
        raw = pd.DatetimeIndex(s).asi8
        self.assertEqual(int(got[0]) // 1000, int(raw[0]))
        self.assertNotEqual(int(got[0]), int(raw[0]))

    def test_last_close_respects_close_and_availability(self):
        base = pd.Timestamp("2026-03-02 17:00", tz="UTC")
        close = gaplib.to_ns([base + pd.Timedelta(minutes=59, seconds=59, milliseconds=999 + 60_000 * 60 * k) for k in range(3)])
        avail = close.copy()
        avail[1] = close[1] + 10 * 60 * 10**9  # published 10 minutes after its close
        series = (close, avail, np.array([1.0, 2.0, 3.0]))
        t = int(close[1]) + 60 * 10**9  # 1 minute after candle 1 closed, before it was published
        self.assertEqual(gaplib.last_close(series, t, strict=True)[0], 1.0)
        self.assertEqual(gaplib.last_close(series, int(close[0]), strict=False)[0], 1.0)
        self.assertIsNone(gaplib.last_close(series, int(close[0]), strict=True))


@unittest.skipIf(PACK is None and "--pack" not in sys.argv, "needs --pack")
class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pit = PointInTime(PACK)
        cls.prices, _ = loop.price_view(cls.pit, CUTOFF.to_pydatetime())

    def test_pack_clock_dtype_is_microseconds(self):
        f = self.pit.frame(gaplib.HL_TABLE, CUTOFF.to_pydatetime()).collect(columns=["close_utc"])
        self.assertIn("us", str(f["close_utc"].dtype))

    def test_no_future_candle_and_settlement_anchor(self):
        for day in (date(2026, 3, 3), date(2026, 4, 6), date(2026, 5, 20)):
            t = loop.preopen_instant(day)
            for asset in gaplib.HL_SYMBOL:
                g = gaplib.gap(self.pit, self.prices, asset, t)
                self.assertIsNone(g["missing"], g)
                self.assertEqual(g["p0_source"], "settlement")
                self.assertLess(g["anchor_utc"], pd.Timestamp(t))
                self.assertGreater(g["signal_lag_min"], 0)  # candle closed strictly before the signal
                self.assertGreaterEqual(g["anchor_lag_min"], 0)  # candle closed at/before p0's observation
                # anchor is a previous session's evening close: 23:30 or 23:55 IST
                ist = g["anchor_utc"].tz_convert("Asia/Kolkata")
                self.assertIn((ist.hour, ist.minute), [(23, 30), (23, 55)])
                # no row of the table read at t is available at or after t
                f = self.pit.frame(gaplib.HL_TABLE, t).collect(columns=["available_utc"])
                self.assertTrue((gaplib.to_ns(f["available_utc"]) < ns_of(t)).all())

    def test_deterministic(self):
        t = loop.preopen_instant(date(2026, 4, 6))
        a = gaplib.gap(self.pit, self.prices, "gold", t)
        b = gaplib.gap(self.pit, self.prices, "gold", t)
        self.assertEqual(a, b)


if __name__ == "__main__":
    if "--pack" in sys.argv:
        i = sys.argv.index("--pack")
        PACK = Path(sys.argv[i + 1])
        del sys.argv[i : i + 2]
    unittest.main(verbosity=2)
