import math

import pandas as pd

FEATURE_NAMES = ["age_years", "duration_hours", "log_cost", "encounters_30d", "log_days_since_prev"]
FEATURE_LABELS_VI = {
    "age_years": "Tuổi tại lượt khám (năm)",
    "duration_hours": "Thời gian khám (giờ)",
    "log_cost": "Tổng chi phí lượt khám",
    "encounters_30d": "Số lượt khám trong 30 ngày trước",
    "log_days_since_prev": "Số ngày kể từ lượt khám trước",
}

LOG_FEATURES = {"log_cost", "log_days_since_prev"}
NAN = float("nan")


def to_ts(value):
    """Chuyển chuỗi hoặc Timestamp thành pd.Timestamp không múi giờ (UTC). Trả None nếu rỗng hoặc sai."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.tz_convert(None) if value.tzinfo is not None else value
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        ts = pd.Timestamp(text)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    return ts.tz_convert(None) if ts.tzinfo is not None else ts


def to_number(value):
    """Chuyển về số thực. Trả None nếu rỗng, NaN, vô hạn hoặc không phải số."""
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def age_years(start, birth):
    return (start - birth).total_seconds() / 86400.0 / 365.25


def build_features(start, stop, birth, total_cost, history_starts, cfg):
    """Tính 5 đặc trưng cho một lượt khám. Thiếu dữ liệu nào thì đặc trưng đó là NaN."""
    f = {name: NAN for name in FEATURE_NAMES}
    cost = to_number(total_cost)

    if start is not None:
        if birth is not None:
            f["age_years"] = age_years(start, birth)
        window_start = start - pd.Timedelta(days=cfg["recent_window_days"])
        earlier = [s for s in history_starts if s is not None and s < start]
        f["encounters_30d"] = float(sum(1 for s in earlier if s >= window_start))
        if earlier:
            gap_days = (start - max(earlier)).total_seconds() / 86400.0
        else:
            gap_days = cfg["first_encounter_gap_days"]
        f["log_days_since_prev"] = math.log1p(gap_days)

    if start is not None and stop is not None:
        f["duration_hours"] = (stop - start).total_seconds() / 3600.0

    if cost is not None and cost >= 0:
        f["log_cost"] = math.log1p(cost)
    return f


import re as _re

_VN_DATETIME = _re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$")


def to_ts_vn(value):
    """Đọc ngày giờ do người dùng nhập.

    Chấp nhận YYYY-MM-DD[ HH:MM[:SS]] (ISO) và DD/MM/YYYY[ HH:MM[:SS]] (cách viết thường dùng ở Việt Nam).
    Dạng có dấu gạch chéo luôn được hiểu là ngày-tháng-năm. Không đoán ngược như pd.Timestamp.
    Trả None nếu không hợp lệ.
    """
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return to_ts(value)
    text = str(value).strip()
    m = _VN_DATETIME.match(text)
    if not m:
        return to_ts(text)
    d, mo, y, hh, mm, ss = m.groups()
    try:
        ts = pd.Timestamp(year=int(y), month=int(mo), day=int(d))
    except ValueError:
        return None
    if hh is not None:
        h, mi, s = int(hh), int(mm), int(ss or 0)
        if h > 23 or mi > 59 or s > 59:
            return None
        ts = ts + pd.Timedelta(hours=h, minutes=mi, seconds=s)
    return ts
