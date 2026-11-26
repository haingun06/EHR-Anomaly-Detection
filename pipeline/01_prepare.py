import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROC_DIR, RAW_DIR  # noqa: E402
from pipeline.common import count_unmatched_patients  # noqa: E402

PATIENT_COLUMNS = ["PATIENT", "BIRTHDATE", "FIRST", "LAST", "GENDER", "ADDRESS", "CITY", "STATE", "ZIP"]
OUT_COLUMNS = ["Id", "START", "STOP", "PATIENT", "ENCOUNTERCLASS", "CODE", "DESCRIPTION",
               "BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "REASONDESCRIPTION", "BIRTHDATE",
               "FIRST", "LAST", "GENDER", "ADDRESS", "CITY", "STATE", "ZIP",
               "PAYER", "PAYER_COVERAGE", "PROVIDER"]
CONDITION_COLUMNS = ["PATIENT", "ENCOUNTER", "START", "STOP", "CODE", "DESCRIPTION"]

EMR_SCOPE = {
    "included": {
        "hành chính": "patients.csv (FIRST, LAST, GENDER, BIRTHDATE, ADDRESS, CITY, STATE, ZIP), Id bệnh nhân",
        "bảo hiểm": "encounters.csv (PAYER, PAYER_COVERAGE): chỉ có mã đơn vị thanh toán, không có tên hay số thẻ",
        "lý do khám": "encounters.csv (REASONDESCRIPTION), chỉ có ở khoảng 26% lượt khám",
        "chẩn đoán và tiền sử bệnh": "conditions.csv (gắn với lượt khám qua ENCOUNTER)",
        "thủ thuật": "encounters.csv (CODE, DESCRIPTION)",
        "bác sĩ phụ trách": "encounters.csv (PROVIDER): chỉ có mã",
        "diễn biến": "lịch sử các lượt khám của cùng bệnh nhân",
    },
    "not_in_source": [
        "thông tin liên hệ (số điện thoại, email)",
        "tiền sử gia đình",
        "tiền sử dị ứng thuốc và thực phẩm",
        "dấu hiệu sinh tồn và kết quả khám lâm sàng",
        "bệnh sử hiện tại dạng tường thuật",
        "đơn thuốc, liều lượng, phác đồ điều trị",
        "lời dặn xuất viện và tái khám",
        "chữ ký số của bác sĩ",
    ],
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    pats = pd.read_csv(RAW_DIR / "patients.csv", dtype=str, keep_default_na=False)
    enc = pd.read_csv(RAW_DIR / "encounters.csv", dtype=str, keep_default_na=False)
    con = pd.read_csv(RAW_DIR / "conditions.csv", dtype=str, keep_default_na=False)

    pats = pats.rename(columns={"Id": "PATIENT"})[PATIENT_COLUMNS]
    df = enc.merge(pats, on="PATIENT", how="left", validate="many_to_one")
    unmatched = count_unmatched_patients(df)
    if unmatched:
        print(f"CẢNH BÁO: {unmatched} lượt khám không khớp bệnh nhân")

    for col in ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    start_ts = pd.to_datetime(df["START"], utc=True, errors="coerce")
    stop_ts = pd.to_datetime(df["STOP"], utc=True, errors="coerce")
    bad_dates = int(start_ts.isna().sum() + stop_ts.isna().sum())
    df = df[OUT_COLUMNS].copy()
    df["_s"] = start_ts.values
    df = df.sort_values(["PATIENT", "_s", "Id"]).drop(columns="_s").reset_index(drop=True)

    out = PROC_DIR / "encounters_clean.csv"
    df.to_csv(out, index=False)

    cond = con[CONDITION_COLUMNS].copy()
    cond_out = PROC_DIR / "conditions_clean.csv"
    cond.to_csv(cond_out, index=False)
    enc_ids = set(df["Id"])
    linked = int(cond["ENCOUNTER"].isin(enc_ids).sum())

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Synthea (dữ liệu tổng hợp), bộ CSV mẫu",
        "files": {name: {"sha256": sha256(RAW_DIR / name), "bytes": (RAW_DIR / name).stat().st_size}
                  for name in ["patients.csv", "encounters.csv", "conditions.csv"]},
        "n_patients": int(pats.shape[0]),
        "n_encounters": int(df.shape[0]),
        "encounterclass_counts": df["ENCOUNTERCLASS"].value_counts().to_dict(),
        "unmatched_birthdate": unmatched,
        "unparseable_dates": bad_dates,
        "conditions_rows": int(cond.shape[0]),
        "conditions_linked_to_encounter": linked,
        "conditions_unlinked": int(cond.shape[0] - linked),
        "emr_scope": EMR_SCOPE,
        "note": "Không lọc theo khoa. Không có cột khoa trong dữ liệu.",
    }
    (PROC_DIR / "manifest_clean.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã ghi {out}: {len(df)} lượt khám, {df['PATIENT'].nunique()} bệnh nhân")
    print(f"Đã ghi {cond_out}: {len(cond)} dòng chẩn đoán, {linked} dòng gắn với lượt khám")
    print(df["ENCOUNTERCLASS"].value_counts().to_string())


if __name__ == "__main__":
    main()
