import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROC_DIR  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["clean", "injected"], required=True)
    args = ap.parse_args()
    src = PROC_DIR / ("encounters_clean.csv" if args.stage == "clean" else "encounters_injected.csv")
    out = PROC_DIR / "eda" / args.stage
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    missing_rate = (df.replace("", np.nan).isna().mean() * 100).round(3)
    missing_rate.to_csv(out / "missing_rate_pct.csv", header=["pct"])

    start = pd.to_datetime(df["START"], utc=True, errors="coerce").dt.tz_localize(None)
    stop = pd.to_datetime(df["STOP"], utc=True, errors="coerce").dt.tz_localize(None)
    birth = pd.to_datetime(df["BIRTHDATE"], errors="coerce")
    d = pd.DataFrame({
        "cls": df["ENCOUNTERCLASS"],
        "duration_h": (stop - start).dt.total_seconds() / 3600,
        "cost": pd.to_numeric(df["TOTAL_CLAIM_COST"], errors="coerce"),
        "age": (start - birth).dt.total_seconds() / 86400 / 365.25,
    })
    d.groupby("cls")[["duration_h", "cost", "age"]].describe().round(2).to_csv(out / "describe_by_class.csv")
    d["cls"].value_counts().rename("n").to_csv(out / "class_counts.csv")

    summary = {
        "rows": int(len(df)),
        "patients": int(df["PATIENT"].nunique()),
        "duplicate_rows_same_key": int(df.duplicated(subset=["PATIENT", "START", "ENCOUNTERCLASS", "CODE", "TOTAL_CLAIM_COST"]).sum()),
        "stop_before_start": int((d["duration_h"] < 0).sum()),
        "age_negative_or_over_120": int(((d["age"] < 0) | (d["age"] > 120)).sum()),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    classes = sorted(d["cls"].unique())
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    for ax, col, title in zip(axes, ["duration_h", "cost", "age"], ["Thời gian khám (giờ)", "Chi phí tổng", "Tuổi (năm)"]):
        ax.boxplot([d.loc[d["cls"] == c, col].dropna() for c in classes], tick_labels=classes, showfliers=False)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out / "boxplots_by_class.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(missing_rate.index, missing_rate.values)
    ax.set_ylabel("% thiếu")
    ax.set_title(f"Tỷ lệ thiếu theo cột ({args.stage})")
    ax.tick_params(axis="x", rotation=60)
    fig.tight_layout()
    fig.savefig(out / "missing_rate.png", dpi=150)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
