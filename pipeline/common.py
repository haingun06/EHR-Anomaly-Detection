from collections import defaultdict

import numpy as np
import pandas as pd

from anomaly.detector import analyze_record
from anomaly.features import to_ts


def load_table(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    records = []
    for seq, r in enumerate(df.to_dict("records")):
        r["START"] = to_ts(r.get("START"))
        r["STOP"] = to_ts(r.get("STOP"))
        r["BIRTHDATE"] = to_ts(r.get("BIRTHDATE"))
        r["_seq"] = seq
        records.append(r)
    records.sort(key=lambda r: (r["PATIENT"], r["START"] or pd.Timestamp.min, r["_seq"]))
    return records


def count_unmatched_patients(df, column="BIRTHDATE"):
    """Số lượt khám không khớp được bệnh nhân sau khi ghép (ô ghép bị NaN hoặc rỗng)."""
    return int((df[column].isna() | (df[column].astype(str).str.strip() == "")).sum())


def analyze_table(records, cfg):
    history = defaultdict(list)
    analyses = []
    for r in records:
        h = history[r["PATIENT"]]
        analyses.append(analyze_record(r, h, cfg))
        h.append(r)
    return analyses


def make_split(patients, seed, test_size):
    """Chia bệnh nhân thành train/test. Cùng một bệnh nhân chỉ nằm ở một tập."""
    pats = sorted(set(patients))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(pats)
    n_test = int(round(len(pats) * test_size))
    test = set(perm[:n_test])
    return {p: ("test" if p in test else "train") for p in pats}
