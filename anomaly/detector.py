import math
from pathlib import Path

import joblib
import numpy as np
import sklearn

from anomaly.features import (FEATURE_LABELS_VI, FEATURE_NAMES, LOG_FEATURES,
                              age_years, build_features, to_ts)
from anomaly.rules import (DEFAULT_RULES_CONFIG, HARD_RULE_CODES, INFO_RULE_CODES, birth_majority,
                           code_checks, document_checks, find_missing, identity_checks,
                           is_duplicate, make_flag, text_of)
from config import MODEL_PATH

REQUIRED_MODEL_KEYS = {"model_version", "sklearn_version", "feature_names", "groups", "fallback", "rules_config"}
_MODEL_CACHE = {}

def load_model(path=MODEL_PATH):
    """Nạp file joblib do chính đồ án tạo ra. Không nạp file lạ vì joblib dùng pickle."""
    key = str(Path(path).resolve())
    if key not in _MODEL_CACHE:
        model = joblib.load(path)
        missing = REQUIRED_MODEL_KEYS - set(model)
        if missing:
            raise ValueError(f"File mô hình thiếu khóa: {sorted(missing)}")
        # File mô hình cũ không có các khóa cấu hình mới: bổ sung giá trị mặc định.
        model["rules_config"] = {**DEFAULT_RULES_CONFIG, **model["rules_config"]}
        _MODEL_CACHE[key] = model
    return _MODEL_CACHE[key]


def model_warnings(model):
    warns = []
    if model["sklearn_version"] != sklearn.__version__:
        warns.append(
            f"Mô hình huấn luyện bằng scikit-learn {model['sklearn_version']}, "
            f"đang chạy {sklearn.__version__}. Nên cài đúng phiên bản trong requirements.txt."
        )
    return warns

def analyze_record(record, history, cfg=DEFAULT_RULES_CONFIG):
    """Kiểm tra luật và tính đặc trưng. history: các lượt khám trước đó của cùng bệnh nhân."""
    start = to_ts(record.get("START"))
    stop = to_ts(record.get("STOP"))
    birth_in = to_ts(record.get("BIRTHDATE"))
    ref_birth = birth_majority([to_ts(h.get("BIRTHDATE")) for h in history])
    birth = birth_in if birth_in is not None else ref_birth

    flags = []
    missing = find_missing(record, bool(history), cfg)
    if missing:
        flags.append(make_flag("missing", fields=", ".join(missing)))
    flags += code_checks(record, cfg)
    flags += document_checks(record)
    flags += identity_checks(record, history, cfg)

    if is_duplicate(record, start, history, cfg):
        flags.append(make_flag("duplicate"))

    if start is not None and stop is not None and stop < start:
        flags.append(make_flag("date_logic"))

    if start is not None and birth is not None:
        age = age_years(start, birth)
        if age < cfg["age_min"] or age > cfg["age_max"]:
            flags.append(make_flag("age_range", age=age, lo=cfg["age_min"], hi=cfg["age_max"]))

    if birth_in is not None and ref_birth is not None and birth_in.normalize() != ref_birth:
        flags.append(make_flag("birthdate_mismatch", ref=ref_birth.date().isoformat()))

    features = build_features(start, stop, birth, record.get("TOTAL_CLAIM_COST"),
                              [to_ts(h.get("START")) for h in history], cfg)
    cls = text_of(record.get("ENCOUNTERCLASS")) or None

    return {
        "missing_fields": missing,
        "rule_flags": flags,
        # Cờ thông tin không tính là phát hiện
        "rule_hit": any(f["code"] not in INFO_RULE_CODES for f in flags),
        "hard_rule_hit": any(f["code"] in HARD_RULE_CODES for f in flags),
        "features": features,
        "complete": all(math.isfinite(features[n]) for n in FEATURE_NAMES),
        "group": cls,
    }

def _entry_for(model, group):
    if group is not None and group in model["groups"]:
        return model["groups"][group], "group", group
    return model["fallback"], "fallback", "__fallback__"


def _display(name, value):
    return math.expm1(value) if name in LOG_FEATURES else value


def _reasons(features, entry, group_label):
    reasons = []
    for name in FEATURE_NAMES:
        value = features[name]
        lo, hi = entry["reference"][name]
        if value < lo or value > hi:
            reasons.append(
                f"{FEATURE_LABELS_VI[name]} = {_display(name, value):.2f}, ngoài khoảng tham chiếu "
                f"[{_display(name, lo):.2f}, {_display(name, hi):.2f}] của nhóm {group_label}"
            )
    return reasons


def score_batch(analyses, model):
    """Chấm điểm Isolation Forest cho danh sách phân tích, trả về kết quả theo đúng thứ tự."""
    names = model["feature_names"]
    out = [None] * len(analyses)
    pending = {}
    for i, a in enumerate(analyses):
        entry, used, key = _entry_for(model, a["group"])
        out[i] = {"anomaly_score": None, "threshold": float(entry["threshold"]),
                  "ml_flag": False, "model_used": used, "reasons": []}
        if a["complete"]:
            pending.setdefault(key, (entry, []))[1].append(i)

    for key, (entry, idxs) in pending.items():
        X = np.array([[analyses[i]["features"][n] for n in names] for i in idxs], dtype=float)
        scores = -entry["model"].score_samples(entry["scaler"].transform(X))
        thr = float(entry["threshold"])
        for pos, i in enumerate(idxs):
            s = float(scores[pos])
            out[i]["anomaly_score"] = s
            out[i]["ml_flag"] = s > thr
            out[i]["reasons"] = _reasons(analyses[i]["features"], entry, analyses[i]["group"] or "dự phòng")
    return out


def decide_status(analysis, ml_flag):
    codes = {f["code"] for f in analysis["rule_flags"]}
    if "missing" in codes:
        return "thiếu thông tin"
    if "duplicate" in codes:
        return "trùng lặp"
    if codes & HARD_RULE_CODES or ml_flag:
        return "bất thường"
    return "bình thường"


def assemble(analysis, ml, model):
    return {
        "status": decide_status(analysis, ml["ml_flag"]),
        "rule_flags": analysis["rule_flags"],
        "anomaly_score": ml["anomaly_score"],
        "threshold": ml["threshold"],
        "ml_flag": ml["ml_flag"],
        "group": analysis["group"],
        "model_used": ml["model_used"],
        "reasons": ml["reasons"],
        "features": analysis["features"],
        "model_version": model["model_version"],
    }


def score_record(record, history, model=None):
    """Chấm điểm một bản ghi. Đây là hàm mà ứng dụng và đặc tả trong báo cáo gọi."""
    model = model or load_model()
    analysis = analyze_record(record, history, model["rules_config"])
    ml = score_batch([analysis], model)[0]
    return assemble(analysis, ml, model)
