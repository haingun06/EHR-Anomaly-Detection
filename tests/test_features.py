import math

import pandas as pd
import pytest

from anomaly.features import FEATURE_NAMES, build_features, to_ts
from anomaly.rules import DEFAULT_RULES_CONFIG as CFG


def ts(s):
    return pd.Timestamp(s)


def test_age_duration_cost_by_hand():
    start, stop, birth = ts("2020-01-10 08:00"), ts("2020-01-10 09:30"), ts("1990-01-10")
    f = build_features(start, stop, birth, 1000, [], CFG)
    assert f["age_years"] == pytest.approx((10957 + 8 / 24) / 365.25, rel=1e-12)
    assert f["duration_hours"] == pytest.approx(1.5)
    assert f["log_cost"] == pytest.approx(math.log(1001))


def test_recent_window_counts_only_strictly_earlier_within_30_days():
    start = ts("2020-01-10 08:00")
    history = [
        ts("2019-12-20 08:00"),
        ts("2019-11-01 08:00"),
        ts("2020-01-10 08:00"),
        ts("2020-01-09 08:00"),
    ]
    f = build_features(start, start, ts("1990-01-10"), 0, history, CFG)
    assert f["encounters_30d"] == 2.0
    assert f["log_days_since_prev"] == pytest.approx(math.log(2))


def test_first_encounter_uses_cap_gap():
    start = ts("2020-01-10 08:00")
    f = build_features(start, start, ts("1990-01-10"), 0, [], CFG)
    assert f["encounters_30d"] == 0.0
    assert f["log_days_since_prev"] == pytest.approx(math.log(3651))


def test_missing_inputs_give_nan_not_zero():
    f = build_features(None, None, None, None, [], CFG)
    assert all(math.isnan(f[n]) for n in FEATURE_NAMES)


def test_to_ts_accepts_both_formats():
    assert to_ts("2019-02-17T05:07:38Z") == ts("2019-02-17 05:07:38")
    assert to_ts("2021-06-01 08:30") == ts("2021-06-01 08:30")
    assert to_ts("") is None and to_ts("không phải ngày") is None
