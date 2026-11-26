import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anomaly.features import to_number, to_ts  # noqa: E402
from config import ERROR_RATE, ERROR_TYPES, PROC_DIR, SEED  # noqa: E402


def fmt(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


class Ctx:
    def __init__(self, rows, rng, prev_of):
        self.rows, self.rng, self.prev_of = rows, rng, prev_of
        self.new_rows = []
        # RNG riêng cho mã bản sao, để việc đổi mã không làm thay đổi các lỗi khác đã sinh ra
        self.id_rng = np.random.default_rng(SEED + 1000)
        self.used_ids = {r["Id"] for r in rows}

    def new_id(self):
        while True:
            cand = "E" + format(int(self.id_rng.integers(0, 2 ** 52)), "013x")
            if cand not in self.used_ids:
                self.used_ids.add(cand)
                return cand


def inj_missing(i, ctx):
    col = ctx.rng.choice(["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST"])
    ctx.rows[i][col] = ""
    return [ctx.rows[i]["Id"]]


def inj_duplicate(i, ctx):
    # Bản sao được ghi sau bản gốc (dòng cuối file) và có mã ngẫu nhiên, giống thao tác nhập lại thật.
    # Nhãn gắn cho bản sao, tức là bản nhập sau.
    new = dict(ctx.rows[i])
    new["Id"] = ctx.new_id()
    ctx.new_rows.append(new)
    return [new["Id"]]


def inj_date_logic(i, ctx):
    start = to_ts(ctx.rows[i]["START"])
    ctx.rows[i]["STOP"] = fmt(start - pd.Timedelta(days=int(ctx.rng.integers(1, 31))))
    return [ctx.rows[i]["Id"]]


def inj_age(i, ctx):
    birth = to_ts(ctx.rows[i]["BIRTHDATE"])
    years = int(ctx.rng.integers(15, 61)) * int(ctx.rng.choice([-1, 1]))
    ctx.rows[i]["BIRTHDATE"] = (birth + pd.DateOffset(years=years)).strftime("%Y-%m-%d")
    return [ctx.rows[i]["Id"]]


def inj_duration(i, ctx):
    start = to_ts(ctx.rows[i]["START"])
    ctx.rows[i]["STOP"] = fmt(start + pd.Timedelta(days=int(ctx.rng.integers(30, 366))))
    return [ctx.rows[i]["Id"]]


def inj_cost(i, ctx):
    cost = to_number(ctx.rows[i]["TOTAL_CLAIM_COST"])
    if cost is None:
        return None
    ctx.rows[i]["TOTAL_CLAIM_COST"] = f"{cost * ctx.rng.uniform(6, 15):.2f}"
    return [ctx.rows[i]["Id"]]


def inj_frequency(i, ctx):
    if i not in ctx.prev_of:
        return None
    row = ctx.rows[i]
    prev_start = to_ts(ctx.rows[ctx.prev_of[i]]["START"])
    dur = to_ts(row["STOP"]) - to_ts(row["START"])
    new_start = prev_start + pd.Timedelta(days=float(ctx.rng.uniform(1, 10)))
    row["START"] = fmt(new_start)
    row["STOP"] = fmt(new_start + dur)
    return [row["Id"]]


INJECTORS = {"missing": inj_missing, "duplicate": inj_duplicate, "date_logic": inj_date_logic,
             "age": inj_age, "duration": inj_duration, "cost": inj_cost, "frequency": inj_frequency}


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(PROC_DIR / "encounters_clean.csv", dtype=str, keep_default_na=False)
    rows = df.to_dict("records")

    by_patient = defaultdict(list)
    for i, r in enumerate(rows):
        by_patient[r["PATIENT"]].append(i)
    prev_of = {}
    for idxs in by_patient.values():
        idxs = sorted(idxs, key=lambda i: to_ts(rows[i]["START"]))
        for a, b in zip(idxs, idxs[1:]):
            prev_of[b] = a

    by_group = defaultdict(list)
    for i, r in enumerate(rows):
        by_group[r["ENCOUNTERCLASS"]].append(i)

    ctx = Ctx(rows, rng, prev_of)
    used, labels = set(), []
    achieved = Counter()
    shortfall = []

    for g in sorted(by_group):
        idxs = np.array(by_group[g])
        k = int(round(ERROR_RATE * len(idxs)))
        base, extra = divmod(k, len(ERROR_TYPES))
        order = list(rng.permutation(ERROR_TYPES))
        quota = {t: base + (1 if j < extra else 0) for j, t in enumerate(order)}
        for t in ERROR_TYPES:
            done = 0
            for i in rng.permutation(idxs):
                if done >= quota[t]:
                    break
                if i in used:
                    continue
                ids = INJECTORS[t](int(i), ctx)
                if ids is None:
                    continue
                used.add(int(i))
                labels += [{"Id": lid, "error_type": t, "ENCOUNTERCLASS": g} for lid in ids]
                done += 1
            achieved[(g, t)] = done
            if done < quota[t]:
                shortfall.append(f"{g}/{t}: {done}/{quota[t]}")

    out_df = pd.DataFrame(rows + ctx.new_rows)
    out_df.to_csv(PROC_DIR / "encounters_injected.csv", index=False)
    lab = pd.DataFrame(labels)
    lab.to_csv(PROC_DIR / "labels.csv", index=False)

    summary = {
        "error_rate_target": ERROR_RATE,
        "rows_clean": len(rows),
        "rows_injected_file": int(out_df.shape[0]),
        "labeled_rows": int(lab.shape[0]),
        "labeled_share_of_file_pct": round(100 * lab.shape[0] / out_df.shape[0], 2),
        "by_error_type": lab["error_type"].value_counts().to_dict(),
        "by_group": {g: int(n) for g, n in lab["ENCOUNTERCLASS"].value_counts().items()},
        "shortfall": shortfall,
    }
    (PROC_DIR / "injection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
