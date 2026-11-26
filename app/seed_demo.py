import argparse
import secrets
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anomaly.detector import load_model  # noqa: E402
from app import auth, db, service  # noqa: E402
from config import DB_PATH, PROC_DIR  # noqa: E402
from pipeline.common import load_table  # noqa: E402

NUMERIC_FIELDS = ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"]

# Tài khoản demo: mật khẩu ngẫu nhiên, chỉ in ra một lần khi tạo CSDL.
DEFAULT_ACCOUNTS = [
    ("nhapmoi", "Điều dưỡng nhập liệu (demo)", auth.ROLE_ENTRY, "Khoa Khám bệnh"),
    ("xuly", "Nhân viên kiểm tra (demo)", auth.ROLE_PROCESS, "Phòng Chất lượng"),
]


def ensure_default_users(conn, passwords=None):
    """Tạo tài khoản demo nếu CSDL chưa có người dùng.

    passwords: dict {tên đăng nhập: mật khẩu}. Thiếu tài khoản nào thì sinh mật khẩu ngẫu nhiên cho tài khoản đó.
    """
    if db.count_users(conn) > 0:
        return []
    passwords = passwords or {}
    created = []
    for username, name, role, khoa in DEFAULT_ACCOUNTS:
        password = passwords.get(username) or secrets.token_urlsafe(9)
        db.create_user(conn, username, name, role, khoa, auth.hash_password(password))
        created.append((username, password, auth.ROLE_LABELS[role]))
    return created


def to_record(r):
    record = {k: r.get(k) for k in db.RECORD_COLUMNS}
    record["START"], record["STOP"], record["BIRTHDATE"] = r["START"], r["STOP"], r["BIRTHDATE"]
    for c in NUMERIC_FIELDS:
        value = pd.to_numeric(r.get(c), errors="coerce")
        record[c] = None if pd.isna(value) else float(value)
    return record


def split_test_patients():
    split = pd.read_csv(PROC_DIR / "split_patients.csv", dtype=str)
    return set(split.loc[split["split"] == "test", "PATIENT"])


def split_test_records(all_records=None):
    """Lấy các dòng thuộc tập kiểm thử (đã sắp xếp), dùng cho nạp demo và kiểm thử tích hợp."""
    test_pats = split_test_patients()
    records = all_records if all_records is not None else load_table(PROC_DIR / "encounters_injected.csv")
    return [r for r in records if r["PATIENT"] in test_pats]


def load_conditions(test_pats, skip_patients=frozenset()):
    """Chẩn đoán và tiền sử của bệnh nhân trong tập kiểm thử, bỏ qua bệnh nhân đã có."""
    df = pd.read_csv(PROC_DIR / "conditions_clean.csv", dtype=str, keep_default_na=False)
    keep = df["PATIENT"].isin(test_pats) & ~df["PATIENT"].isin(skip_patients)
    return df[keep].to_dict("records")


def seed(conn, model, progress=None):
    n = 0
    for r in split_test_records():
        if db.encounter_exists(conn, r["Id"]):
            continue
        service.score_and_store(conn, model, to_record(r), source="seed", actor=auth.SYSTEM)
        n += 1
        if progress and n % 1000 == 0:
            progress(n, None)
    test_pats = split_test_patients()
    rows = load_conditions(test_pats, skip_patients=db.patients_with_conditions(conn))
    if rows:
        with conn:
            db.insert_conditions(conn, rows, source="seed")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
    conn = db.connect()
    for username, password, role_label in ensure_default_users(conn):
        print(f"Tài khoản demo: {username} / {password}  ({role_label})")
    if db.count_encounters(conn) > 0:
        print("CSDL đã có dữ liệu. Dùng --reset để nạp lại.")
        return
    model = load_model()
    n = seed(conn, model, progress=lambda a, b: print(f"  đã xử lý {a} lượt khám"))
    print(f"Đã nạp {n} lượt khám demo vào {DB_PATH}")


if __name__ == "__main__":
    main()
