import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score
from sklearn.preprocessing import RobustScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anomaly.features import FEATURE_NAMES  # noqa: E402
from anomaly.rules import DEFAULT_RULES_CONFIG  # noqa: E402
from config import (CONTAMINATION_GRID, DEFAULT_CONTAMINATION, IF_MAX_SAMPLES,  # noqa: E402
                    IF_N_ESTIMATORS, MIN_GROUP_TRAIN_N, MODEL_DIR, MODEL_PATH, MODEL_VERSION,
                    PROC_DIR, SEED, TEST_SIZE, VALUE_ERROR_TYPES)
from pipeline.common import analyze_table, load_table, make_split  # noqa: E402


def collect(records, analyses, labels=None):
    """Lấy ma trận đặc trưng của các bản ghi đủ 5 đặc trưng. labels là dict Id -> loại lỗi, có thể None."""
    X, groups, y = [], [], []
    for r, a in zip(records, analyses):
        if a["complete"]:
            X.append([a["features"][n] for n in FEATURE_NAMES])
            groups.append(a["group"])
            y.append(bool(labels) and labels.get(r["Id"]) in VALUE_ERROR_TYPES)
    return np.array(X, dtype=float).reshape(-1, len(FEATURE_NAMES)), np.array(groups), np.array(y, dtype=bool)


def build_entry(X_clean, X_cal, y_cal, seed):
    """Fit trên dữ liệu sạch, chọn ngưỡng và contamination trên dữ liệu có nhãn."""
    scaler = RobustScaler()
    Xs = scaler.fit_transform(X_clean)
    iso = IsolationForest(n_estimators=IF_N_ESTIMATORS, max_samples=IF_MAX_SAMPLES, random_state=seed)
    iso.fit(Xs)

    s_clean = -iso.score_samples(Xs)
    grid = {c: float(np.quantile(s_clean, 1 - c)) for c in CONTAMINATION_GRID}

    if len(X_cal) == 0 or y_cal.sum() == 0:
        best_c, best_f1 = DEFAULT_CONTAMINATION, 0.0
    else:
        s_cal = -iso.score_samples(scaler.transform(X_cal))
        best_c, best_f1 = None, -1.0
        for c in CONTAMINATION_GRID:
            f1 = f1_score(y_cal, s_cal > grid[c], zero_division=0)
            if f1 > best_f1:
                best_c, best_f1 = c, f1

    return {
        "scaler": scaler,
        "model": iso,
        "contamination": float(best_c),
        "threshold": float(grid[best_c]),
        "threshold_grid": grid,
        "train_f1": float(best_f1),
        "n_train": int(len(X_clean)),
        "n_positive_train": int(y_cal.sum()),
        "n_calibration": int(len(X_cal)),
        "reference": {n: [float(np.quantile(X_clean[:, j], 0.01)), float(np.quantile(X_clean[:, j], 0.99))]
                      for j, n in enumerate(FEATURE_NAMES)},
    }


REPORT_KEYS = ["n_train", "n_calibration", "n_positive_train", "contamination", "threshold", "train_f1"]


def main():
    injected = load_table(PROC_DIR / "encounters_injected.csv")
    clean = load_table(PROC_DIR / "encounters_clean.csv")
    labels = pd.read_csv(PROC_DIR / "labels.csv", dtype=str)
    lab = dict(zip(labels["Id"], labels["error_type"]))

    split = make_split([r["PATIENT"] for r in injected], SEED, TEST_SIZE)
    pd.DataFrame({"PATIENT": list(split), "split": list(split.values())}).to_csv(
        PROC_DIR / "split_patients.csv", index=False)

    train_inj = [r for r in injected if split[r["PATIENT"]] == "train"]
    train_clean = [r for r in clean if split[r["PATIENT"]] == "train"]
    X_clean, g_clean, _ = collect(train_clean, analyze_table(train_clean, DEFAULT_RULES_CONFIG))
    X_cal, g_cal, y_cal = collect(train_inj, analyze_table(train_inj, DEFAULT_RULES_CONFIG), lab)

    model_groups, report = {}, {}
    for g in sorted(set(g_clean)):
        n_clean = int((g_clean == g).sum())
        if n_clean >= MIN_GROUP_TRAIN_N:
            model_groups[g] = build_entry(X_clean[g_clean == g], X_cal[g_cal == g], y_cal[g_cal == g], SEED)
            model_groups[g]["model_type"] = "group"
        else:
            report[g] = "dùng mô hình dự phòng (dưới ngưỡng huấn luyện riêng)"

    fallback = build_entry(X_clean, X_cal, y_cal, SEED)
    fallback["model_type"] = "fallback"

    for g, e in model_groups.items():
        report[g] = {k: e[k] for k in REPORT_KEYS}
    report["__fallback__"] = {k: fallback[k] for k in REPORT_KEYS}

    model = {
        "model_version": MODEL_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED,
        "sklearn_version": sklearn.__version__,
        "feature_names": FEATURE_NAMES,
        "groups": model_groups,
        "fallback": fallback,
        "rules_config": DEFAULT_RULES_CONFIG,
        "training_data": "encounters_clean (bệnh nhân train); nhãn chỉ dùng để chọn contamination",
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH, compress=3)
    (PROC_DIR / "train_report.json").write_text(
        json.dumps({k: (v if isinstance(v, str) else {kk: (float(vv) if isinstance(vv, (np.floating, float)) else vv)
                                                        for kk, vv in v.items()}) for k, v in report.items()},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã lưu {MODEL_PATH}")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
