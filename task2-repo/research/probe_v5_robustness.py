"""How much of v5's holdout direction is the gate, how much is luck, and how often it goes silent.

Grades the distinct keys of v4 (every trust-issued call) with the scorer's ``grade_c2``, marks the
26 that v5 kept, and reports: per-key hit rates, the row-weighted direction under the repeat
schedule, a variant that files the other calls once, and the share of five-session windows with
no call. Writes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from swing_dataset.scoring2 import outcomes as O  # noqa: E402
from swing_dataset.scoring2 import signals as SIG  # noqa: E402
from swing_dataset.scoring2.prices import PriceSeries  # noqa: E402

PACK = ROOT / "v2.1"
KEY = ["asset", "signal_utc", "horizon"]
COLS = ["asset", "signal_utc", "direction", "horizon", "expected_pct", "p10_pct", "p90_pct", "invalidation_pct", "evidence"]


def keys(path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(path)
    raw = raw[raw["signal_utc"].notna()].copy()
    raw["signal_utc"] = pd.to_datetime(raw["signal_utc"], utc=True)
    copies = raw.groupby(KEY).size().rename("copies").reset_index()
    return raw.drop_duplicates(KEY).merge(copies, on=KEY)


def wilson(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    p, z = k / n, 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"[{100 * (centre - half):.1f}, {100 * (centre + half):.1f}]"


def main() -> None:
    prices = PriceSeries.from_paths(
        PACK / "mcx" / "mcx_daily.parquet", PACK / "labels" / "designations.parquet",
        PACK / "mcx" / "mcx_sessions.parquet", PACK / "pack" / "quotes" / "mcx_quotes.parquet",
    )
    v4 = keys(ROOT / "predictions_v4" / "c2_holdout.parquet")
    v5 = keys(ROOT / "predictions_v5_ship" / "c2_holdout.parquet")
    graded = O.grade_c2(SIG.normalize(v4[COLS], 2).signals, prices)
    graded = graded.merge(v4[KEY + ["copies"]], on=KEY)
    kept = set(map(tuple, v5[KEY].astype(str).to_numpy()))
    graded["kept"] = [tuple(map(str, k)) in kept for k in graded[KEY].to_numpy()]
    graded["right"] = graded["realized"].fillna(False).astype(bool)

    for name, part in (("kept by v5 (others disagree)", graded[graded["kept"]]),
                       ("dropped by v5 (others agree)", graded[~graded["kept"]])):
        k, n = int(part["right"].sum()), len(part)
        print(f"{name}: {k}/{n} = {100 * k / n:.1f}%  95% CI {wilson(k, n)}")

    kept_rows = graded[graded["kept"]]
    misses = kept_rows[~kept_rows["right"]]
    print("v5 misses:", misses[["asset", "signal_utc", "copies"]].to_dict("records"))
    copies = kept_rows["copies"].to_numpy()
    print(f"v5 copies per key: min {copies.min()} median {int(np.median(copies))} max {copies.max()}")
    # A miss that had landed on a key with the median copy count instead of its own:
    med = int(np.median(copies))
    rows = copies.sum()
    print(f"v5 row direction as filed: {100 * (rows - misses['copies'].sum()) / rows:.2f}")
    print(f"same, if the miss carried the median {med} copies: {100 * (rows - med) / rows:.2f}")
    print(f"same, if the miss carried 113 copies: {100 * (rows - 113) / rows:.2f}")

    # Variant: keep v5's repeats, file every dropped call once.
    other = graded[~graded["kept"]]
    right_rows = (kept_rows["right"] * kept_rows["copies"]).sum() + other["right"].sum()
    all_rows = kept_rows["copies"].sum() + len(other)
    d = 100 * right_rows / all_rows
    print(f"variant (disagree repeated, agree once): direction {d:.2f} on {all_rows} rows, "
          f"keys {len(graded)}, success {(d + 100) / 3:.2f}")

    sessions = pd.to_datetime(pd.read_parquet(ROOT / "predictions_v5_ship" / "c2_holdout.parquet")
                              .assign(t=lambda f: f["signal_utc"].fillna(f["decision_utc"]))["t"], utc=True)
    days = sorted(sessions.dt.tz_convert("Asia/Kolkata").dt.date.unique())
    for label, frame in (("v5", v5), ("variant / v4", v4)):
        hit = set(frame["signal_utc"].dt.tz_convert("Asia/Kolkata").dt.date)
        windows = [days[i:i + 5] for i in range(0, len(days) - 4)]
        silent = sum(1 for w in windows if not hit.intersection(w))
        print(f"{label}: sessions with a call {len(hit)}/{len(days)}; five-session windows with none "
              f"{silent}/{len(windows)} = {100 * silent / len(windows):.0f}%")

    # Success per five-session window, as the forward window would score it (improvement 0, depth 100).
    graded["day"] = graded["signal_utc"].dt.tz_convert("Asia/Kolkata").dt.date
    designs = {
        "v4 (all calls repeated)": graded.assign(w=graded["copies"]),
        "v5 (disagree only, repeated)": graded[graded["kept"]].assign(w=lambda f: f["copies"]),
        "variant (disagree repeated, agree once)": graded.assign(w=np.where(graded["kept"], graded["copies"], 1)),
    }
    windows = [set(days[i:i + 5]) for i in range(0, len(days) - 4)]
    for name, frame in designs.items():
        scores = []
        for w in windows:
            part = frame[frame["day"].isin(w)]
            if part.empty or part["w"].sum() == 0:
                scores.append(np.nan)
                continue
            d = 100 * (part["right"] * part["w"]).sum() / part["w"].sum()
            scores.append((d + 100) / 3)
        s = np.array(scores, dtype=float)
        spoke = s[~np.isnan(s)]
        print(f"{name}: windows scored {len(spoke)}/{len(s)}; mean success when scored {spoke.mean():.2f}; "
              f"silent counted as 0 -> {np.nan_to_num(s, nan=0.0).mean():.2f}; "
              f"worst {spoke.min():.1f}; share below 60 {100 * (spoke < 60).mean():.0f}%")
        d_all = 100 * (frame["right"] * frame["w"]).sum() / frame["w"].sum()
        print(f"   whole holdout: direction {d_all:.2f}, success {(d_all + 100) / 3:.2f}")


if __name__ == "__main__":
    main()
