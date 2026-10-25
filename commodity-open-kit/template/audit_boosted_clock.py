"""Read-only check of old versus explicit-nanosecond snapshot indexing.
Run beside the uploaded boosted_model.py in the kit environment.
"""
import argparse
import importlib.util
import json
from datetime import datetime, UTC
from pathlib import Path
import numpy as np
import pandas as pd
from swing_dataset.pack.pit import PointInTime
from swing_dataset.kit.loop import price_view
from swing_dataset.scoring2.prices import ns_of

ap = argparse.ArgumentParser()
ap.add_argument("--pack", required=True, type=Path)
a = ap.parse_args()
spec = importlib.util.spec_from_file_location("clock_audit_target", Path(__file__).with_name("boosted_model.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
pit = PointInTime(a.pack)
_, chains = price_view(pit, datetime(2026,6,1,3,tzinfo=UTC), lookback_sessions=None)
report = {"scope":"training-only diagnostic; no model or pack changes", "assets":{}}
for asset, chain in sorted(chains.chains.items()):
    c=chain.sort_values("session_date").reset_index(drop=True)
    actual_clock, _, _ = module.feature_table(chain, asset)
    raw=pd.DatetimeIndex(pd.to_datetime(c["available_utc"],utc=True))
    normalized=raw.as_unit("ns").asi8
    correct=np.maximum.accumulate(normalized)
    positions=sorted(set([min(90,len(c)-2),len(c)//2,max(0,len(c)-20)]))
    examples=[]
    for i in positions:
        if i<1 or i>=len(c):
            continue
        instant=pd.Timestamp(c.iloc[i]["session_date"]).tz_localize("Asia/Kolkata")+pd.Timedelta(hours=8,minutes=30)
        target=ns_of(instant)
        old_idx=int(np.searchsorted(actual_clock,target,side="left"))-1
        fixed_idx=int(np.searchsorted(correct,target,side="left"))-1
        assert fixed_idx < 0 or correct[fixed_idx] < target
        examples.append({"decision_utc":instant.tz_convert("UTC").isoformat(),
            "current_selected_session":str(c.iloc[old_idx]["session_date"]) if old_idx>=0 else None,
            "fixed_selected_session":str(c.iloc[fixed_idx]["session_date"]) if fixed_idx>=0 else None,
            "indices_differ":old_idx!=fixed_idx,
            "current_uses_future_source":bool(old_idx>=0 and correct[old_idx]>=target)})
    report["assets"][asset]={"pandas_clock_dtype":str(raw.dtype),
        "feature_clock_matches_nanoseconds":bool(np.array_equal(actual_clock,correct)),"examples":examples}
report["timestamp_bug_reproduced"]=any(not v["feature_clock_matches_nanoseconds"] for v in report["assets"].values())
Path("boosted_clock_audit.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
