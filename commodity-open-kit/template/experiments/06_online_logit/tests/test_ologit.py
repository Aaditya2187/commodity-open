#!/usr/bin/env python3
"""Required tests for ologit (stdlib unittest). Dev smoke window only: train_end 2026-04-01, sessions 1–17 Apr.

    python experiments/06_online_logit/tests/test_ologit.py --pack /path/to/v2.1
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SUB = Path(__file__).resolve().parents[1] / "submission"
sys.path.insert(0, str(SUB))
import model as M  # noqa: E402

from swing_dataset.kit import formats, loop, repro  # noqa: E402
from swing_dataset.pack.pit import PointInTime, ReadLog  # noqa: E402
from swing_dataset.scoring2.prices import ns_of  # noqa: E402

PACK: Path | None = None
TRAIN_END = pd.Timestamp("2026-04-01 03:00", tz="UTC").to_pydatetime()
SMOKE = (date(2026, 4, 1), date(2026, 4, 17))
KEY = ["asset", "signal_utc", "horizon"]


def run(frozen: bool, lam: float, log: Path | None = None, recorder=None, no_op_update=False):
    pit = PointInTime(PACK, read_log=ReadLog(log) if log else None)
    m = M.OnlineLogit(2, (5, 10), lam=lam)
    if no_op_update:
        m.update = lambda rows: {"noop": True}
    if recorder is not None:
        inner = m.update

        def wrapped(rows):
            cutoff = pd.Timestamp(pit.read_log.context.get("cutoff_utc")) if pit.read_log else None
            before = m.state_digest()
            out = inner(rows)
            recorder.append({"cutoff": cutoff, "rows": rows.copy(), "before": before, "after": m.state_digest(),
                             "log": out})
            return out
        m.update = wrapped
    period = loop.period_for("holdout", SMOKE[0], SMOKE[1], TRAIN_END)
    res = loop.run(m, pit, challenge=2, period=period, horizons=(5, 10), frozen=frozen)
    return res, m


class Ologit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = Path(__file__).resolve().parent / "_tmp"
        tmp.mkdir(exist_ok=True)
        cls.tmp = tmp
        cls.rec = []
        cls.learn, cls.lm = run(False, 0.95, tmp / "learn.readlog.jsonl", cls.rec)
        cls.frozen, cls.fm = run(True, 0.95)
        cls.noop, _ = run(False, 0.95, no_op_update=True)
        cls.again, _ = run(False, 0.95)

    def test_initial_states_match(self):
        a, b = M.OnlineLogit(2, (5, 10), lam=0.95), M.OnlineLogit(2, (5, 10), lam=0.95)
        ia, ib = a.fit(PointInTime(PACK), TRAIN_END), b.fit(PointInTime(PACK), TRAIN_END)
        self.assertEqual(ia, ib)
        self.assertEqual(a.state_digest(), b.state_digest())
        self.assertEqual(self.fm.state_digest(), ia["state_digest"])  # frozen never moved

    def test_updates_change_state(self):
        used = [r for r in self.rec if r["log"]["used"] > 0]
        self.assertTrue(used, "no update used any label in the smoke window")
        self.assertTrue(all(r["before"] != r["after"] for r in used))
        self.assertNotEqual(self.lm.state_digest(), self.fm.state_digest())

    def test_labels_after_predictions_and_available(self):
        for r in self.rec:
            rows, cutoff = r["rows"], r["cutoff"]
            self.assertTrue((pd.to_datetime(rows["signal_utc"], utc=True) < cutoff).all())
            # the delivered outcome was decided or complete on data available before the cutoff
            decided = rows["realized"].astype(bool) | (rows["mae_pct"] >= rows["threshold_pct"] - 1e-9) | rows["window_complete"].astype(bool)
            self.assertTrue(decided.all())
            # the latest label in the update log precedes the cutoff
            ls = r["log"].get("latest_label_signal_utc")
            if ls:
                self.assertLess(pd.Timestamp(ls), cutoff)

    def test_disabling_updates_reproduces_frozen(self):
        a = self.noop.decisions.reset_index(drop=True)
        b = self.frozen.decisions.reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)

    def test_pairing_keys_identical(self):
        a = self.learn.signals.set_index(KEY).sort_index()
        b = self.frozen.signals.set_index(KEY).sort_index()
        self.assertTrue(a.index.equals(b.index))

    def test_no_future_reads(self):
        rep = repro.check_read_log(repro.load_read_log(self.tmp / "learn.readlog.jsonl"), self.learn.decisions,
                                   TRAIN_END, PACK)
        self.assertGreater(rep["entries"], 0)
        self.assertTrue(rep["ok"], rep["violations"])

    def test_reproducible(self):
        pa = formats.write_predictions(self.learn.decisions, self.tmp / "a.parquet")
        pb = formats.write_predictions(self.again.decisions, self.tmp / "b.parquet")
        self.assertEqual(hashlib.sha256(Path(pa).read_bytes()).hexdigest(), hashlib.sha256(Path(pb).read_bytes()).hexdigest())

    def test_timestamp_units(self):
        s = pd.Series(pd.to_datetime(["2026-04-01 17:59:59.999"], utc=True)).astype("datetime64[us, UTC]")
        self.assertEqual(int(M.to_ns(s)[0]), ns_of(s.iloc[0]))
        self.assertNotEqual(int(M.to_ns(s)[0]), int(pd.DatetimeIndex(s).asi8[0]))

    def test_training_labels_precede_train_end(self):
        panel = M.training_panel(PointInTime(PACK), TRAIN_END)
        self.assertTrue((panel["t_ns"] < ns_of(TRAIN_END)).all())

    def test_anchor_capped_at_last_close(self):
        sig = self.learn.signals
        anchors = pd.to_datetime(sig["evidence"].str.extract(r"anchored (\S+)$")[0], utc=True, format="ISO8601")
        self.assertTrue((anchors < sig["signal_utc"]).all())


if __name__ == "__main__":
    if "--pack" not in sys.argv:
        sys.exit("pass --pack")
    i = sys.argv.index("--pack")
    PACK = Path(sys.argv[i + 1])
    del sys.argv[i : i + 2]
    unittest.main(verbosity=2)
