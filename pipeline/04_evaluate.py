import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anomaly.detector import load_model, score_batch  # noqa: E402
from anomaly.rules import text_of  # noqa: E402
from config import CONTAMINATION_GRID, ERROR_TYPES, PROC_DIR  # noqa: E402
from pipeline.common import analyze_table, load_table  # noqa: E402


def metrics(y, p):
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[False, True]).ravel()
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"n": int(len(y)), "positives": int(y.sum()), "TP": int(tp), "FP": int(fp),
            "FN": int(fn), "TN": int(tn), "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}


def main():
    model = load_model()
    cfg = model["rules_config"]
    labels = pd.read_csv(PROC_DIR / "labels.csv", dtype=str)
    lab = dict(zip(labels["Id"], labels["error_type"]))
    split = pd.read_csv(PROC_DIR / "split_patients.csv", dtype=str)
    test_pats = set(split.loc[split["split"] == "test", "PATIENT"])

    records = [r for r in load_table(PROC_DIR / "encounters_injected.csv") if r["PATIENT"] in test_pats]
    analyses = analyze_table(records, cfg)
    ml = score_batch(analyses, model)

    rows = []
    for r, a, m in zip(records, analyses, ml):
        rows.append({
            "Id": r["Id"], "PATIENT": r["PATIENT"], "group": a["group"] or "",
            "error_type": lab.get(r["Id"], ""), "y": r["Id"] in lab,
            "rule": a["rule_hit"], "ml": m["ml_flag"], "combined": a["rule_hit"] or m["ml_flag"],
            "anomaly_score": m["anomaly_score"], "model_used": m["model_used"],
            "rule_codes": ";".join(f["code"] for f in a["rule_flags"]),
            "rule_messages": " | ".join(f["message"] for f in a["rule_flags"]),
            "reasons": " | ".join(m["reasons"]), "group_entry": a["group"] if m["model_used"] == "group" else "__fallback__",
        })
    res = pd.DataFrame(rows)
    y = res["y"]

    overall = {name: metrics(y, res[col]) for name, col in
               [("rule_based", "rule"), ("isolation_forest", "ml"), ("combined", "combined")]}

    per_type = {}
    for t in ERROR_TYPES:
        mask = res["error_type"] == t
        per_type[t] = {name: round(float(res.loc[mask, col].mean()), 4) for name, col in
                       [("rule_based", "rule"), ("isolation_forest", "ml"), ("combined", "combined")]}
        per_type[t]["n"] = int(mask.sum())

    per_group = {}
    for g, sub in res.groupby("group"):
        per_group[g] = {name: metrics(sub["y"], sub[col]) for name, col in
                        [("rule_based", "rule"), ("isolation_forest", "ml"), ("combined", "combined")]}

    # Độ nhạy theo contamination: thay ngưỡng bằng ngưỡng đã tính sẵn trong file mô hình
    sweep = []
    scores = res["anomaly_score"].to_numpy(dtype=float)
    entry_keys = res["group_entry"].to_numpy()
    for c in CONTAMINATION_GRID:
        thr = np.array([(model["groups"][k] if k in model["groups"] else model["fallback"])["threshold_grid"][c]
                        for k in entry_keys], dtype=float)
        ml_c = np.where(np.isfinite(scores), scores > thr, False)
        comb_c = res["rule"].to_numpy() | ml_c
        sweep.append({"contamination": c, "ml": metrics(y, ml_c), "combined": metrics(y, comb_c)})

    errors = res[res["y"] != res["combined"]].copy()
    errors["kind"] = np.where(errors["y"], "bỏ sót", "cảnh báo nhầm")
    errors[["Id", "PATIENT", "group", "error_type", "kind", "anomaly_score", "rule_messages", "reasons"]] \
        .to_csv(PROC_DIR / "error_cases.csv", index=False)
    res.drop(columns=["group_entry"]).to_csv(PROC_DIR / "test_predictions.csv", index=False)

    out = {"n_test_rows": int(len(res)), "overall": overall, "per_error_type_recall": per_type,
           "per_group": per_group, "contamination_sweep": sweep,
           "model_version": model["model_version"]}
    (PROC_DIR / "eval_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(overall, ensure_ascii=False, indent=2))
    print("Số trường hợp bỏ sót/cảnh báo nhầm:", len(errors))


if __name__ == "__main__":
    main()
