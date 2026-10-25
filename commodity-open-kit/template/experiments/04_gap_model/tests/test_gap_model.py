#!/usr/bin/env python3
"""Regression tests for gap-v1 (stdlib unittest; the kit ships no pytest).

    python experiments/04_gap_model/tests/test_gap_model.py --pack /path/to/v2.1

The real-data tests drive the kit's own loop over a short smoke window (2026-07-01 to 07-08). They
compare entry prices and keys only; no direction outcome of the holdout is looked at.
"""

from __future__ import annotations

import hashlib
import io
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SUB = Path(__file__).resolve().parents[1] / "submission"
sys.path.insert(0, str(SUB))
import model as M  # noqa: E402

from swing_dataset.kit import formats, loop  # noqa: E402
from swing_dataset.pack.pit import PointInTime, ReadLog  # noqa: E402
from swing_dataset.kit import repro  # noqa: E402
from swing_dataset.scoring2 import BAND_WIDTH_CAP, THRESHOLD_PCT  # noqa: E402
from swing_dataset.scoring2 import outcomes as O  # noqa: E402
from swing_dataset.scoring2 import signals as SIG  # noqa: E402
from swing_dataset.scoring2.prices import ns_of  # noqa: E402

PACK: Path | None = None
SMOKE = (date(2026, 7, 1), date(2026, 7, 8))
KEY = ["asset", "signal_utc", "horizon"]


def _run(frozen: bool, horizons=(5, 10), log: Path | None = None, wrap_update=None):
    pit = PointInTime(PACK, read_log=ReadLog(log) if log else None)
    m = M.build(2, horizons)
    if wrap_update:
        m.update = wrap_update(m.update)
    period = loop.period_for("holdout", *SMOKE)
    res = loop.run(m, pit, challenge=2, period=period, horizons=horizons, frozen=frozen)
    return res, m, pit


def _bytes(frame: pd.DataFrame, tmp: Path) -> bytes:
    path = formats.write_predictions(frame, tmp)
    return Path(path).read_bytes()


class Pure(unittest.TestCase):
    def test_timestamp_unit_mismatch(self):
        s = pd.Series(pd.to_datetime(["2026-07-01 17:59:59.999", "2026-07-02 02:59:59.999"], utc=True)).astype(
            "datetime64[us, UTC]"
        )
        ns = M.to_ns(s)
        self.assertEqual(list(ns), [ns_of(v) for v in s])
        self.assertNotEqual(int(ns[0]), int(pd.DatetimeIndex(s).asi8[0]))  # raw asi8 is microseconds here
        series = (ns, ns.copy(), np.array([1.0, 2.0]))
        self.assertEqual(M.last_close(series, int(ns[1]), strict=True)[0], 1.0)  # strictly before
        self.assertEqual(M.last_close(series, int(ns[1]), strict=False)[0], 2.0)  # at/before
        late = (ns, ns + 10**9, np.array([1.0, 2.0]))  # published a second after close
        self.assertEqual(M.last_close(late, int(ns[1]) + 1, strict=True)[0], 1.0)

    def test_band_valid_and_contains_threshold(self):
        for a, thr in THRESHOLD_PCT.items():
            e, lo, hi = M.band(a)
            self.assertLessEqual(hi - lo, BAND_WIDTH_CAP * thr)
            self.assertLess(lo, thr)
            self.assertGreater(hi, 12.9 * thr)
            self.assertGreater(e, 0)

    def test_identical_starting_states(self):
        a, b = M.build(2, (5, 10)), M.build(2, (5, 10))
        fa, fb = a.fit("pack", pd.Timestamp("2026-06-01 03:00", tz="UTC")), b.fit("pack", pd.Timestamp("2026-06-01 03:00", tz="UTC"))
        self.assertEqual(fa, fb)
        self.assertEqual(vars(a), vars(b))


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = Path(__file__).resolve().parent / "_tmp"
        tmp.mkdir(exist_ok=True)
        cls.tmp = tmp
        cls.calls = []

        def wrap(fn):
            def inner(rows):
                cls.calls.append((pit_holder["pit"].read_log.context.get("cutoff_utc"), rows.copy()))
                return fn(rows)
            return inner

        pit_holder = {}
        cls.learn, cls.lm, pit = None, None, None
        pit = PointInTime(PACK, read_log=ReadLog(tmp / "learn.readlog.jsonl"))
        pit_holder["pit"] = pit
        m = M.build(2, (5, 10))
        m.update = wrap(m.update)
        cls.learn = loop.run(m, pit, challenge=2, period=loop.period_for("holdout", *SMOKE), horizons=(5, 10))
        cls.learn_log = tmp / "learn.readlog.jsonl"
        cls.frozen, _, _ = _run(True)
        cls.again, _, _ = _run(False)
        cls.h35, _, _ = _run(False, horizons=(3, 5))

    def test_signals_issued_and_horizons(self):
        sig = self.learn.signals
        self.assertGreater(len(sig), 0)
        self.assertEqual(set(sig["horizon"].astype(int)), {3, 5})
        self.assertTrue(formats.validate(self.learn.decisions, 2).ok)

    def test_horizon_argument_does_not_change_rows(self):
        a = self.learn.decisions.reset_index(drop=True)
        b = self.h35.decisions.reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)

    def test_no_future_reads(self):
        entries = repro.load_read_log(self.learn_log)
        report = repro.check_read_log(entries, self.learn.decisions, loop.period_for("holdout", *SMOKE).train_end, PACK)
        self.assertGreater(report["entries"], 0)
        self.assertTrue(report["ok"], report["violations"])

    def test_snapshot_matches_replay(self):
        # Fresh model, standalone call at one instant == what the loop issued at that instant.
        sig = self.learn.signals
        t = sig["signal_utc"].iloc[len(sig) // 2]
        asset = sig["asset"].iloc[len(sig) // 2]
        m = M.build(2, (5, 10))
        m.fit(PointInTime(PACK), loop.PERIODS["holdout"].train_end)
        out = m.predict(t.to_pydatetime(), asset, 5)
        loop_rows = sig[(sig["signal_utc"] == t) & (sig["asset"] == asset)].sort_values("horizon")
        self.assertEqual([r["direction"] for r in out], loop_rows["direction"].tolist())
        self.assertEqual([r["evidence"] for r in out], loop_rows["evidence"].tolist())

    def test_entry_price_matches_official_scorer(self):
        # Scorer-side prices built from every row available after the window (as the scorer does).
        pit = PointInTime(PACK)
        asof = pd.Timestamp("2026-10-24 06:00", tz="UTC").to_pydatetime()
        prices, _ = loop.price_view(pit, asof, quotes=True)
        sig = self.learn.signals.reset_index(drop=True)
        graded = O.grade_c2(SIG.normalize(sig, 2).signals, prices)
        for i, row in sig.iterrows():
            ev = row["evidence"]
            self.assertIn(f"of {graded.loc[i, 'contract_id']} observed", ev)
            anchor = pd.Timestamp(ev.split("observed ")[1].split(")")[0])
            p = prices.price_at(row["asset"], graded.loc[i, "contract_id"], row["signal_utc"])
            self.assertEqual(ns_of(p[2]), ns_of(anchor))
            self.assertAlmostEqual(p[0], graded.loc[i, "p0"])

    def test_no_update_before_outcome_available(self):
        self.assertTrue(self.calls, "the smoke window delivered no outcomes")
        for cutoff, rows in self.calls:
            c = pd.Timestamp(cutoff)
            self.assertTrue((pd.to_datetime(rows["signal_utc"], utc=True) < c).all())
            decided_or_done = rows["realized"].astype(bool) | rows["window_complete"].astype(bool) | (
                rows["mae_pct"] >= rows["threshold_pct"] - 1e-9)
            self.assertTrue(decided_or_done.all())

    def test_fixed_key_pairing_learning_vs_frozen(self):
        a = self.learn.signals.set_index(KEY).sort_index()
        b = self.frozen.signals.set_index(KEY).sort_index()
        self.assertTrue(a.index.equals(b.index))
        self.assertFalse(a.index.duplicated().any())
        self.assertEqual(a["direction"].tolist(), b["direction"].tolist())

    def test_deterministic_repeated_execution(self):
        b1 = _bytes(self.learn.decisions, self.tmp / "a.parquet")
        b2 = _bytes(self.again.decisions, self.tmp / "b.parquet")
        self.assertEqual(hashlib.sha256(b1).hexdigest(), hashlib.sha256(b2).hexdigest())

    def test_coverage_every_session_has_a_record(self):
        d = self.learn.decisions
        day = d["signal_utc"].fillna(d["decision_utc"]).dt.tz_convert("Asia/Kolkata").dt.date
        per = d.assign(day=day).groupby("asset")["day"].nunique()
        self.assertTrue((per == len(self.learn.sessions)).all(), per)
        ns = d[d["signal_utc"].isna()]
        self.assertTrue(ns["reason"].notna().all())


if __name__ == "__main__":
    if "--pack" in sys.argv:
        i = sys.argv.index("--pack")
        PACK = Path(sys.argv[i + 1])
        del sys.argv[i : i + 2]
    else:
        sys.exit("pass --pack")
    unittest.main(verbosity=2)
