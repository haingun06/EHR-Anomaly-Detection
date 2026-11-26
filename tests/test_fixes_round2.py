import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from anomaly.detector import load_model
from anomaly.features import to_ts
from app import auth, db, service
from config import MODEL_PATH, PROC_DIR

needs_model = pytest.mark.skipif(not MODEL_PATH.exists(), reason="Chưa có file mô hình")
needs_artifacts = pytest.mark.skipif(not (PROC_DIR / "encounters_injected.csv").exists(),
                                     reason="Chưa có dữ liệu đã xử lý")
NHAP = auth.User("n", "n", auth.ROLE_ENTRY, "")
KT = auth.User("k", "k", auth.ROLE_PROCESS, "")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "f.sqlite")
    yield c
    c.close()


def raw(eid, start="2024-03-01 09:00", **over):
    base = {"PATIENT": "PX", "Id": eid, "ENCOUNTERCLASS": "ambulatory", "START": start,
            "STOP": "2024-03-01 09:15", "BIRTHDATE": "1980-01-01", "LAST": "Nguyễn", "FIRST": "An",
            "GENDER": "M", "BASE_ENCOUNTER_COST": "100", "TOTAL_CLAIM_COST": "100", "CODE": "1234",
            "DESCRIPTION": "Khám"}
    base.update(over)
    return base


# ---------- 1–2. Thứ tự nhập, không phụ thuộc mã lượt khám ----------

@needs_model
@pytest.mark.parametrize("first_id,second_id", [("zzz-1", "aaa-1"), ("aaa-1", "zzz-1")])
def test_duplicate_detected_whatever_the_ids_are(conn, first_id, second_id):
    model = load_model()
    r1, _ = service.validate_input(raw(first_id), False)
    service.score_and_store(conn, model, r1, actor=NHAP)
    r2, _ = service.validate_input(raw(second_id), True)
    res = service.score_and_store(conn, model, r2, actor=NHAP)
    assert res["status"] == "trùng lặp"          # bản nhập sau luôn bị gắn cờ


@needs_model
def test_uuid_ids_do_not_change_duplicate_detection(conn):
    import uuid
    model = load_model()
    hits = 0
    import tempfile
    for i in range(12):
        c = db.connect(Path(tempfile.mkdtemp()) / "u.sqlite")
        a, _ = service.validate_input(raw(uuid.uuid4().hex), False)
        service.score_and_store(c, model, a, actor=NHAP)
        b, _ = service.validate_input(raw(uuid.uuid4().hex), True)
        hits += service.score_and_store(c, model, b, actor=NHAP)["status"] == "trùng lặp"
        c.close()
    assert hits == 12


def test_history_for_uses_insertion_order_not_id(conn):
    # Hai lượt cùng thời điểm, nhập theo thứ tự A rồi B (Id của B nhỏ hơn A)
    conn.execute("INSERT INTO luot_kham (Id, START, STOP, PATIENT, ENCOUNTERCLASS, source, created_at) "
                 "VALUES ('zzz', '2024-03-01T09:00:00', '2024-03-01T09:15:00', 'P', 'wellness', 'manual', 'x')")
    conn.execute("INSERT INTO luot_kham (Id, START, STOP, PATIENT, ENCOUNTERCLASS, source, created_at) "
                 "VALUES ('aaa', '2024-03-01T09:00:00', '2024-03-01T09:15:00', 'P', 'wellness', 'manual', 'x')")
    start = to_ts("2024-03-01 09:00")
    ids_for_zzz = {h["Id"] for h in db.history_for(conn, "P", start, "zzz")}   # zzz nhập trước: không có ai trước
    ids_for_aaa = {h["Id"] for h in db.history_for(conn, "P", start, "aaa")}   # aaa nhập sau: có zzz
    assert ids_for_zzz == set()
    assert ids_for_aaa == {"zzz"}


@needs_artifacts
def test_injected_duplicates_have_random_ids_and_are_the_later_copy():
    inj = pd.read_csv(PROC_DIR / "encounters_injected.csv", dtype=str, keep_default_na=False)
    lab = pd.read_csv(PROC_DIR / "labels.csv", dtype=str)
    dup_ids = lab.loc[lab["error_type"] == "duplicate", "Id"].tolist()
    assert dup_ids and not any(i.endswith("-dup") for i in dup_ids)
    pos = {i: k for k, i in enumerate(inj["Id"])}
    # Mỗi bản sao nằm sau bản gốc trong file, tức là bản nhập sau
    for d in dup_ids[:200]:
        row = inj.iloc[pos[d]]
        orig = inj[(inj["PATIENT"] == row["PATIENT"]) & (inj["START"] == row["START"]) &
                   (inj["CODE"] == row["CODE"]) & (inj["TOTAL_CLAIM_COST"] == row["TOTAL_CLAIM_COST"]) &
                   (inj["Id"] != d)]
        assert len(orig) >= 1
        assert min(pos[i] for i in orig["Id"]) < pos[d]


# ---------- 3. Huấn luyện trên dữ liệu sạch ----------

@needs_artifacts
def test_training_fit_uses_clean_rows_only():
    from anomaly.rules import DEFAULT_RULES_CONFIG
    from pipeline.common import analyze_table, load_table, make_split
    from config import SEED, TEST_SIZE
    model = load_model()
    injected = load_table(PROC_DIR / "encounters_injected.csv")
    split = make_split([r["PATIENT"] for r in injected], SEED, TEST_SIZE)
    clean = [r for r in load_table(PROC_DIR / "encounters_clean.csv") if split[r["PATIENT"]] == "train"]
    an = analyze_table(clean, DEFAULT_RULES_CONFIG)
    n_complete = sum(a["complete"] for a in an)
    assert model["fallback"]["n_train"] == n_complete
    assert "encounters_clean" in model["training_data"]


# ---------- 4. Ngày sinh tham chiếu ----------

def test_reference_birthdate_is_majority(conn):
    for eid, bd in [("a", "1990-01-05"), ("b", "1990-01-05"), ("c", "1991-02-02"), ("d", None)]:
        conn.execute("INSERT INTO luot_kham (Id, START, STOP, PATIENT, ENCOUNTERCLASS, BIRTHDATE, source, created_at)"
                     " VALUES (?, '2024-01-01T08:00:00', '2024-01-01T08:10:00', 'Q', 'wellness', ?, 'manual', 'x')",
                     (eid, bd))
    ref = db.reference_birthdate(conn, "Q")
    assert ref == pd.Timestamp("1990-01-05")
    assert db.reference_birthdate(conn, "NONE") is None


# ---------- 5. Quy tắc cập nhật: không xóa trường đang có, được bổ sung trường còn thiếu ----------

@needs_model
def test_update_cannot_clear_a_filled_required_field(conn):
    model = load_model()
    r, _ = service.validate_input(raw("U1"), False)
    service.score_and_store(conn, model, r, actor=NHAP)
    # Tạo cảnh báo để có quy trình xử lý: kết thúc trước bắt đầu
    r2, _ = service.validate_input(raw("U2", start="2024-03-05 09:00", STOP="2024-03-04 09:00"), True)
    service.score_and_store(conn, model, r2, actor=NHAP)
    service.start_processing(conn, "U2", actor=KT)
    with pytest.raises(service.EditError) as e:
        service.update_emr(conn, model, "U2", {"TOTAL_CLAIM_COST": ""}, "thử xóa", actor=KT)
    assert any("Tổng chi phí" in m for m in e.value.errors)


@needs_model
def test_update_can_fill_a_missing_required_field(conn):
    model = load_model()
    rec = service.validate_input(raw("M1", start="2024-03-05 09:00", STOP="2024-03-04 09:00"), False)[0]
    rec["TOTAL_CLAIM_COST"] = None  # thiếu chi phí như bản ghi bị lỗi thiếu dữ liệu
    service.score_and_store(conn, model, rec, actor=NHAP)
    assert db.get_workflow(conn, "M1") is not None
    service.start_processing(conn, "M1", actor=KT)
    changed = service.update_emr(conn, model, "M1", {"TOTAL_CLAIM_COST": "250000"}, "bổ sung chi phí", actor=KT)
    assert "TOTAL_CLAIM_COST" in changed


# ---------- 6. Thứ tự nhập trong load_table và kiểm tra không khớp ----------

def test_load_table_orders_by_insertion_within_same_start(tmp_path):
    from pipeline.common import load_table
    csv = tmp_path / "e.csv"
    csv.write_text("Id,PATIENT,START,STOP,ENCOUNTERCLASS,BIRTHDATE,CODE,DESCRIPTION,TOTAL_CLAIM_COST,"
                   "BASE_ENCOUNTER_COST\n"
                   "zzz,P,2024-01-01T08:00:00,2024-01-01T08:10:00,wellness,1990-01-01,1,d,1,1\n"
                   "aaa,P,2024-01-01T08:00:00,2024-01-01T08:10:00,wellness,1990-01-01,1,d,1,1\n",
                   encoding="utf-8")
    recs = load_table(csv)
    assert [r["Id"] for r in recs] == ["zzz", "aaa"]   # theo dòng trong file, không theo Id
    assert recs[0]["_seq"] < recs[1]["_seq"]


def test_count_unmatched_patients_counts_nan_and_blank():
    from pipeline.common import count_unmatched_patients
    df = pd.DataFrame({"BIRTHDATE": ["1990-01-01", np.nan, "", "  ", "2000-01-01"]})
    assert count_unmatched_patients(df) == 3


# ---------- 7. Kết nối SQLite ----------

def test_connection_uses_wal_and_busy_timeout(tmp_path):
    c = db.connect(tmp_path / "wal.sqlite")
    try:
        assert c.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert c.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
    finally:
        c.close()
