import json
import math
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from anomaly.features import to_ts
from config import DB_PATH

PENDING = "chờ xử lý"
PROCESSING = "đang xử lý"
DONE = "đã xử lý"
STATES = [PENDING, PROCESSING, DONE]
TRANSITIONS = {
    PENDING: {PROCESSING},
    PROCESSING: {DONE},
    DONE: {PROCESSING},
}

RESULT_UPDATED = "Đã cập nhật dữ liệu"
RESULT_CONFIRMED = "Xác nhận cảnh báo, cần xem xét thêm"
RESULTS = [RESULT_UPDATED, RESULT_CONFIRMED]

SCHEMA_VERSION = 6

RECORD_COLUMNS = ["Id", "START", "STOP", "PATIENT", "ENCOUNTERCLASS", "CODE", "DESCRIPTION",
                  "BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "REASONDESCRIPTION", "BIRTHDATE",
                  "FIRST", "LAST", "GENDER", "ADDRESS", "CITY", "STATE", "ZIP",
                  "PAYER", "PAYER_COVERAGE", "PROVIDER", "PHIEU_DAY_DU", "DA_KY_SO"]
DOC_VALUES = ("co", "khong")
DATE_FIELDS = {"START", "STOP", "BIRTHDATE"}
NUM_FIELDS = {"BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"}
EDITABLE_COLUMNS = {"LAST", "FIRST", "GENDER", "BIRTHDATE", "ADDRESS", "CITY", "STATE", "ZIP",
                    "PAYER", "PAYER_COVERAGE", "PROVIDER", "ENCOUNTERCLASS", "START", "STOP",
                    "REASONDESCRIPTION", "CODE", "DESCRIPTION", "BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST",
                    "PHIEU_DAY_DU", "DA_KY_SO"}

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS luot_kham (
    Id TEXT PRIMARY KEY,
    START TEXT NOT NULL,
    STOP TEXT NOT NULL,
    PATIENT TEXT NOT NULL,
    ENCOUNTERCLASS TEXT NOT NULL,
    CODE TEXT,
    DESCRIPTION TEXT,
    BASE_ENCOUNTER_COST REAL,
    TOTAL_CLAIM_COST REAL,
    REASONDESCRIPTION TEXT,
    BIRTHDATE TEXT,
    FIRST TEXT,
    LAST TEXT,
    GENDER TEXT,
    ADDRESS TEXT,
    CITY TEXT,
    STATE TEXT,
    ZIP TEXT,
    PAYER TEXT,
    PAYER_COVERAGE REAL,
    PROVIDER TEXT,
    PHIEU_DAY_DU TEXT,
    DA_KY_SO TEXT,
    revision INTEGER NOT NULL DEFAULT 0,
    cap_nhat_emr_luc TEXT,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_luot_kham_patient ON luot_kham(PATIENT);

CREATE TABLE IF NOT EXISTS chan_doan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    PATIENT TEXT NOT NULL,
    ENCOUNTER TEXT,
    START TEXT,
    STOP TEXT,
    CODE TEXT,
    DESCRIPTION TEXT,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chan_doan_patient ON chan_doan(PATIENT);
CREATE INDEX IF NOT EXISTS ix_chan_doan_encounter ON chan_doan(ENCOUNTER);

CREATE TABLE IF NOT EXISTS ket_qua_cham_diem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL REFERENCES luot_kham(Id),
    model_version TEXT NOT NULL,
    emr_revision INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    rule_flags TEXT NOT NULL,
    anomaly_score REAL,
    threshold REAL,
    group_name TEXT,
    model_used TEXT,
    reasons TEXT NOT NULL,
    features TEXT NOT NULL,
    scored_at TEXT NOT NULL,
    UNIQUE (encounter_id, model_version, emr_revision)
);

CREATE TABLE IF NOT EXISTS xu_ly (
    encounter_id TEXT PRIMARY KEY REFERENCES luot_kham(Id),
    trang_thai TEXT NOT NULL,
    cap_nhat_luc TEXT NOT NULL,
    rev_bat_dau INTEGER NOT NULL DEFAULT 0,
    ket_qua TEXT,
    ghi_chu_ket_qua TEXT,
    nguoi_hoan_tat TEXT,
    hoan_tat_luc TEXT
);

CREATE TABLE IF NOT EXISTS nhat_ky (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL,
    hanh_dong TEXT NOT NULL,
    tu_trang_thai TEXT,
    den_trang_thai TEXT NOT NULL,
    ghi_chu TEXT,
    nguoi_thuc_hien TEXT NOT NULL,
    thoi_gian TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_encounter ON nhat_ky(encounter_id);

CREATE TABLE IF NOT EXISTS thay_doi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    truong TEXT NOT NULL,
    gia_tri_cu TEXT,
    gia_tri_moi TEXT,
    ghi_chu TEXT NOT NULL,
    nguoi_thuc_hien TEXT NOT NULL,
    thoi_gian TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_thay_doi_encounter ON thay_doi(encounter_id);

CREATE TABLE IF NOT EXISTS truy_cap (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL,
    nguoi_truy_cap TEXT NOT NULL,
    thoi_gian TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_truy_cap_encounter ON truy_cap(encounter_id);

CREATE TRIGGER IF NOT EXISTS nhat_ky_khong_sua BEFORE UPDATE ON nhat_ky
BEGIN SELECT RAISE(ABORT, 'nhat_ky là nhật ký chỉ thêm, không được sửa'); END;
CREATE TRIGGER IF NOT EXISTS nhat_ky_khong_xoa BEFORE DELETE ON nhat_ky
BEGIN SELECT RAISE(ABORT, 'nhat_ky là nhật ký chỉ thêm, không được xóa'); END;
CREATE TRIGGER IF NOT EXISTS thay_doi_khong_sua BEFORE UPDATE ON thay_doi
BEGIN SELECT RAISE(ABORT, 'thay_doi là nhật ký chỉ thêm, không được sửa'); END;
CREATE TRIGGER IF NOT EXISTS thay_doi_khong_xoa BEFORE DELETE ON thay_doi
BEGIN SELECT RAISE(ABORT, 'thay_doi là nhật ký chỉ thêm, không được xóa'); END;
CREATE TRIGGER IF NOT EXISTS truy_cap_khong_sua BEFORE UPDATE ON truy_cap
BEGIN SELECT RAISE(ABORT, 'truy_cap là nhật ký chỉ thêm, không được sửa'); END;
CREATE TRIGGER IF NOT EXISTS truy_cap_khong_xoa BEFORE DELETE ON truy_cap
BEGIN SELECT RAISE(ABORT, 'truy_cap là nhật ký chỉ thêm, không được xóa'); END;

CREATE TABLE IF NOT EXISTS nguoi_dung (
    username TEXT PRIMARY KEY,
    ho_ten TEXT NOT NULL,
    vai_tro TEXT NOT NULL CHECK (vai_tro IN ('nhap_lieu', 'xu_ly')),
    khoa TEXT,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dang_nhap (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    thanh_cong INTEGER NOT NULL,
    thoi_gian TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS dang_nhap_khong_sua BEFORE UPDATE ON dang_nhap
BEGIN SELECT RAISE(ABORT, 'dang_nhap là nhật ký chỉ thêm, không được sửa'); END;
CREATE TRIGGER IF NOT EXISTS dang_nhap_khong_xoa BEFORE DELETE ON dang_nhap
BEGIN SELECT RAISE(ABORT, 'dang_nhap là nhật ký chỉ thêm, không được xóa'); END;
"""


class EncounterExists(Exception):
    pass


class TransitionError(Exception):
    pass


class SchemaOutdated(Exception):
    pass


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        # WAL cho phép nhiều phiên đọc và một phiên ghi cùng lúc; busy_timeout chờ thay vì lỗi ngay.
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        _check_schema(conn)
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    except Exception:
        conn.close()
        raise
    return conn


_RELOAD_MSG = "CSDL được tạo bởi phiên bản cũ. Chạy: python -m app.seed_demo --reset"


def _check_schema(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(luot_kham)")}
    scores = {r[1] for r in conn.execute("PRAGMA table_info(ket_qua_cham_diem)")}
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if cols and ("revision" not in cols or "FIRST" not in cols):
        raise SchemaOutdated(_RELOAD_MSG)
    if scores and "emr_revision" not in scores:
        raise SchemaOutdated(_RELOAD_MSG)
    if cols and version != SCHEMA_VERSION:
        raise SchemaOutdated(_RELOAD_MSG)


def _db_value(v):
    if v is None:
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def _text(v):
    """Chuỗi để ghi vào nhật ký thay đổi. None giữ nguyên là None."""
    v = _db_value(v)
    return None if v is None else str(v)


def _canon(field, v):
    """Dạng so sánh chuẩn: hai giá trị bằng nhau khi cùng ý nghĩa, không phụ thuộc cách ghi."""
    v = _db_value(v)
    if v is None:
        return None
    if field in DATE_FIELDS:
        ts = to_ts(v)
        return ts.isoformat() if ts is not None else str(v)
    if field in NUM_FIELDS:
        try:
            return float(v)
        except (TypeError, ValueError):
            return str(v)
    return str(v).strip()


def _json_safe(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj

def encounter_exists(conn, encounter_id):
    return conn.execute("SELECT 1 FROM luot_kham WHERE Id = ?", (encounter_id,)).fetchone() is not None


def patient_has_records(conn, patient):
    return conn.execute("SELECT 1 FROM luot_kham WHERE PATIENT = ? LIMIT 1", (patient,)).fetchone() is not None


def insert_encounter(conn, record, source):
    """Thêm lượt khám. Không tự commit: người gọi quản lý giao dịch."""
    if encounter_exists(conn, record["Id"]):
        raise EncounterExists(record["Id"])
    values = [_db_value(record.get(c)) for c in RECORD_COLUMNS]
    ts = now_iso()
    cols = RECORD_COLUMNS + ["revision", "cap_nhat_emr_luc", "source", "created_at"]
    marks = ", ".join(["?"] * len(cols))
    conn.execute(f"INSERT INTO luot_kham ({', '.join(cols)}) VALUES ({marks})",
                 values + [0, None, source, ts])


def get_encounter(conn, encounter_id):
    row = conn.execute("SELECT * FROM luot_kham WHERE Id = ?", (encounter_id,)).fetchone()
    return dict(row) if row else None


def history_for(conn, patient, key_start, key_id=None):
    """Lịch sử dùng cho đặc trưng và luật trùng lặp của một lượt khám.

    Gồm lượt khám của bệnh nhân bắt đầu trước lượt đang xét, và lượt khám cùng thời điểm đã được nhập trước đó.
    Thứ tự nhập được lấy từ rowid (thứ tự ghi vào CSDL), không dựa vào mã lượt khám. Mã lượt khám có thể
    là UUID ngẫu nhiên nên không thể dùng để xác định bản nào nhập trước.
    Nếu lượt đang xét chưa lưu (key_id là None) thì mọi lượt cùng thời điểm đã có đều được coi là nhập trước.
    """
    cur_rid = None
    if key_id is not None:
        row = conn.execute("SELECT rowid FROM luot_kham WHERE Id = ?", (key_id,)).fetchone()
        cur_rid = row[0] if row else None
        rows = conn.execute("SELECT rowid AS _rid, * FROM luot_kham WHERE PATIENT = ? AND Id <> ?",
                            (patient, key_id)).fetchall()
    else:
        rows = conn.execute("SELECT rowid AS _rid, * FROM luot_kham WHERE PATIENT = ?", (patient,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        s = to_ts(d["START"])
        if s is None or key_start is None:
            continue
        if s < key_start or (s == key_start and (cur_rid is None or d["_rid"] < cur_rid)):
            out.append(d)
    return out


def reference_birthdate(conn, patient):
    """Ngày sinh tham chiếu của bệnh nhân: giá trị xuất hiện nhiều nhất trong các lượt khám đã lưu."""
    rows = conn.execute("SELECT BIRTHDATE FROM luot_kham WHERE PATIENT = ? AND BIRTHDATE IS NOT NULL",
                        (patient,)).fetchall()
    vals = [to_ts(r[0]).normalize() for r in rows if to_ts(r[0]) is not None]
    if not vals:
        return None
    from collections import Counter
    return Counter(vals).most_common(1)[0][0]


def patient_encounters(conn, patient):
    """Tất cả lượt khám của bệnh nhân, sắp theo thời gian bắt đầu (mới nhất trước)."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM luot_kham WHERE PATIENT = ?", (patient,))]
    rows.sort(key=lambda d: (_sort_ts(d["START"]), d["Id"]), reverse=True)
    return rows


def _sort_ts(value):
    ts = to_ts(value)
    return ts if ts is not None else pd.Timestamp.min


def count_encounters(conn):
    return conn.execute("SELECT COUNT(*) FROM luot_kham").fetchone()[0]


def apply_emr_changes(conn, encounter_id, new_values, note, actor):
    """Ghi các trường đã đổi vào hồ sơ, tăng phiên bản, ghi từng thay đổi và nhật ký.

    Không đổi trạng thái xử lý. Trả về danh sách trường thực sự đổi. Danh sách rỗng nghĩa là không ghi gì.
    """
    unknown = set(new_values) - EDITABLE_COLUMNS
    if unknown:
        raise ValueError(f"Không được sửa các cột: {sorted(unknown)}")
    row = get_encounter(conn, encounter_id)
    if row is None:
        raise KeyError(encounter_id)
    diffs = [(f, row.get(f), v) for f, v in new_values.items()
             if _canon(f, row.get(f)) != _canon(f, v)]
    if not diffs:
        return []
    wf = get_workflow(conn, encounter_id)
    state = wf["trang_thai"] if wf else "không có quy trình"
    rev = row["revision"] + 1
    ts = now_iso()
    fields = [f for f, _, _ in diffs]
    with conn:
        conn.execute(
            f"UPDATE luot_kham SET {', '.join(f + ' = ?' for f in fields)}, revision = ?, cap_nhat_emr_luc = ? "
            "WHERE Id = ?",
            [_db_value(v) for _, _, v in diffs] + [rev, ts, encounter_id])
        conn.executemany(
            """INSERT INTO thay_doi (encounter_id, revision, truong, gia_tri_cu, gia_tri_moi,
                                     ghi_chu, nguoi_thuc_hien, thoi_gian) VALUES (?,?,?,?,?,?,?,?)""",
            [(encounter_id, rev, f, _text(o), _text(n), note, actor, ts) for f, o, n in diffs])
        conn.execute("""INSERT INTO nhat_ky (encounter_id, hanh_dong, tu_trang_thai, den_trang_thai,
                        ghi_chu, nguoi_thuc_hien, thoi_gian) VALUES (?,?,?,?,?,?,?)""",
                     (encounter_id, "chỉnh_sửa_emr", state, state,
                      f"Phiên bản hồ sơ {rev}. Lý do: {note}. Trường đã đổi: {', '.join(fields)}",
                      actor, ts))
    return fields


def edit_log(conn, encounter_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM thay_doi WHERE encounter_id = ? ORDER BY id DESC", (encounter_id,)).fetchall()]

def count_conditions(conn):
    return conn.execute("SELECT COUNT(*) FROM chan_doan").fetchone()[0]


def patients_with_conditions(conn):
    return {r[0] for r in conn.execute("SELECT DISTINCT PATIENT FROM chan_doan")}


def insert_conditions(conn, rows, source):
    """rows: danh sách dict có PATIENT, ENCOUNTER, START, STOP, CODE, DESCRIPTION. Không tự commit."""
    conn.executemany(
        """INSERT INTO chan_doan (PATIENT, ENCOUNTER, START, STOP, CODE, DESCRIPTION, source)
           VALUES (?,?,?,?,?,?,?)""",
        [(r["PATIENT"], _db_value(r.get("ENCOUNTER")), _db_value(r.get("START")), _db_value(r.get("STOP")),
          _db_value(r.get("CODE")), _db_value(r.get("DESCRIPTION")), source) for r in rows])


def conditions_for_encounter(conn, encounter_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM chan_doan WHERE ENCOUNTER = ? ORDER BY START, id", (encounter_id,)).fetchall()]


def prior_conditions(conn, patient, encounter_id, encounter_start):
    """Tiền sử bệnh cá nhân trước lượt khám: bệnh bắt đầu trước hoặc cùng lúc, không thuộc lượt này."""
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM chan_doan WHERE PATIENT = ? ORDER BY START, id", (patient,)).fetchall()]
    out = []
    for r in rows:
        if r["ENCOUNTER"] == encounter_id:
            continue
        s = to_ts(r["START"])
        if s is not None and encounter_start is not None and s <= encounter_start:
            out.append(r)
    return out

def save_score(conn, encounter_id, result, emr_revision=0):
    """Lưu kết quả. Trả về (bản ghi, True nếu vừa tạo, False nếu đã có cùng phiên bản mô hình và hồ sơ)."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO ket_qua_cham_diem
           (encounter_id, model_version, emr_revision, status, rule_flags, anomaly_score, threshold,
            group_name, model_used, reasons, features, scored_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (encounter_id, result["model_version"], emr_revision, result["status"],
         json.dumps(_json_safe(result["rule_flags"]), ensure_ascii=False),
         _db_value(result["anomaly_score"]), _db_value(result["threshold"]),
         result.get("group"), result.get("model_used"),
         json.dumps(_json_safe(result["reasons"]), ensure_ascii=False),
         json.dumps(_json_safe(result["features"])), now_iso()))
    created = cur.rowcount == 1
    return get_score(conn, encounter_id, result["model_version"], emr_revision), created


def _score_row(row):
    if row is None:
        return None
    d = dict(row)
    d["rule_flags"] = json.loads(d["rule_flags"])
    d["reasons"] = json.loads(d["reasons"])
    d["features"] = json.loads(d["features"])
    d["group"] = d.pop("group_name")
    return d


def get_score(conn, encounter_id, model_version, emr_revision=0):
    row = conn.execute(
        "SELECT * FROM ket_qua_cham_diem WHERE encounter_id = ? AND model_version = ? AND emr_revision = ?",
        (encounter_id, model_version, emr_revision)).fetchone()
    return _score_row(row)


def latest_score(conn, encounter_id):
    row = conn.execute("SELECT * FROM ket_qua_cham_diem WHERE encounter_id = ? ORDER BY id DESC LIMIT 1",
                       (encounter_id,)).fetchone()
    return _score_row(row)


def score_history(conn, encounter_id):
    return [dict(r) for r in conn.execute(
        """SELECT model_version, emr_revision, status, anomaly_score, threshold, group_name, model_used, scored_at
           FROM ket_qua_cham_diem WHERE encounter_id = ? ORDER BY id DESC""", (encounter_id,)).fetchall()]

def get_workflow(conn, encounter_id):
    row = conn.execute("SELECT * FROM xu_ly WHERE encounter_id = ?", (encounter_id,)).fetchone()
    return dict(row) if row else None


def ensure_workflow(conn, encounter_id, actor):
    """Tạo quy trình xử lý khi lượt khám có cảnh báo. Không tự commit."""
    if get_workflow(conn, encounter_id):
        return
    ts = now_iso()
    conn.execute("INSERT INTO xu_ly (encounter_id, trang_thai, cap_nhat_luc) VALUES (?,?,?)",
                 (encounter_id, PENDING, ts))
    conn.execute("""INSERT INTO nhat_ky (encounter_id, hanh_dong, tu_trang_thai, den_trang_thai,
                    ghi_chu, nguoi_thuc_hien, thoi_gian) VALUES (?,?,?,?,?,?,?)""",
                 (encounter_id, "tạo_xử_lý", None, PENDING, "Hệ thống tạo khi chấm điểm", actor, ts))


def add_audit(conn, encounter_id, hanh_dong, ghi_chu, actor):
    """Ghi một dòng nhật ký không đổi trạng thái (ví dụ chấm lại). Không tự commit."""
    wf = get_workflow(conn, encounter_id)
    state = wf["trang_thai"] if wf else "không có quy trình"
    conn.execute("""INSERT INTO nhat_ky (encounter_id, hanh_dong, tu_trang_thai, den_trang_thai,
                    ghi_chu, nguoi_thuc_hien, thoi_gian) VALUES (?,?,?,?,?,?,?)""",
                 (encounter_id, hanh_dong, state, state, ghi_chu, actor, now_iso()))


def validate_transition(current, target, note):
    if target not in STATES:
        raise TransitionError(f"Trạng thái không hợp lệ: {target}")
    if target not in TRANSITIONS.get(current, set()):
        raise TransitionError(f"Không thể chuyển từ '{current}' sang '{target}'")
    if current == DONE and not (note or "").strip():
        raise TransitionError("Cần ghi lý do khi mở lại lượt đã xử lý")


def set_status(conn, encounter_id, target, note, actor, result=None):
    """Đổi trạng thái xử lý và ghi nhật ký trong một giao dịch.

    Bắt đầu xử lý (-> đang xử lý) đặt mốc phiên bản hồ sơ và xóa kết luận cũ.
    Hoàn tất (-> đã xử lý) lưu kết luận, người hoàn tất và thời điểm.
    """
    wf = get_workflow(conn, encounter_id)
    if wf is None:
        raise TransitionError("Lượt khám này không có cảnh báo nên không có quy trình xử lý")
    validate_transition(wf["trang_thai"], target, note)
    ts = now_iso()
    note_text = (note or "").strip() or None
    with conn:
        if target == DONE:
            conn.execute("""UPDATE xu_ly SET trang_thai = ?, cap_nhat_luc = ?, ket_qua = ?, ghi_chu_ket_qua = ?,
                            nguoi_hoan_tat = ?, hoan_tat_luc = ? WHERE encounter_id = ?""",
                         (target, ts, result, note_text, actor, ts, encounter_id))
            log_note = f"{result}. {note_text}"
        else:
            rev = get_encounter(conn, encounter_id)["revision"]
            conn.execute("""UPDATE xu_ly SET trang_thai = ?, cap_nhat_luc = ?, rev_bat_dau = ?, ket_qua = NULL,
                            ghi_chu_ket_qua = NULL, nguoi_hoan_tat = NULL, hoan_tat_luc = NULL
                            WHERE encounter_id = ?""",
                         (target, ts, rev, encounter_id))
            log_note = note_text
        conn.execute("""INSERT INTO nhat_ky (encounter_id, hanh_dong, tu_trang_thai, den_trang_thai,
                        ghi_chu, nguoi_thuc_hien, thoi_gian) VALUES (?,?,?,?,?,?,?)""",
                     (encounter_id, "chuyển_trạng_thái", wf["trang_thai"], target, log_note, actor, ts))


def list_items(conn, status=None, encounter_class=None, flagged_only=True, sort="moi_nhat"):
    """Danh sách lượt khám kèm kết quả chấm điểm mới nhất và trạng thái xử lý.

    sort:
      "moi_nhat"  - theo thời gian khám mới nhất trước (mặc định)
      "trang_thai" - chờ xử lý trước, rồi đang xử lý, đã xử lý, rồi các lượt không có quy trình;
                     trong mỗi nhóm vẫn theo thời gian khám mới nhất
    flagged_only: chỉ lượt đã từng có cảnh báo (có quy trình xử lý). Tắt khi tìm kiếm trên toàn bộ hồ sơ.
    """
    if sort == "trang_thai":
        order = ("CASE x.trang_thai WHEN ? THEN 0 WHEN ? THEN 1 WHEN ? THEN 2 ELSE 3 END, "
                 "l.START DESC, l.Id DESC")
        order_params = (PENDING, PROCESSING, DONE)
    else:
        order = "l.START DESC, l.Id DESC"
        order_params = ()

    sql = """
    SELECT l.Id, l.PATIENT, l.FIRST, l.LAST, l.ENCOUNTERCLASS, l.START, l.TOTAL_CLAIM_COST, l.revision,
           s.status, s.anomaly_score, s.model_version, s.reasons,
           x.trang_thai, x.ket_qua, x.cap_nhat_luc
    FROM luot_kham l
    JOIN ket_qua_cham_diem s ON s.id = (SELECT MAX(k.id) FROM ket_qua_cham_diem k WHERE k.encounter_id = l.Id)
    LEFT JOIN xu_ly x ON x.encounter_id = l.Id
    WHERE (? IS NULL OR l.ENCOUNTERCLASS = ?)
      AND (? IS NULL OR x.trang_thai = ?)
      AND (? = 0 OR x.encounter_id IS NOT NULL)
    ORDER BY """ + order
    params = (encounter_class, encounter_class, status, status, 1 if flagged_only else 0) + order_params
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def audit_log(conn, encounter_id=None, limit=500):
    if encounter_id:
        rows = conn.execute("SELECT * FROM nhat_ky WHERE encounter_id = ? ORDER BY id", (encounter_id,))
    else:
        rows = conn.execute("SELECT * FROM nhat_ky ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows.fetchall()]


def add_access(conn, encounter_id, actor):
    with conn:
        conn.execute("INSERT INTO truy_cap (encounter_id, nguoi_truy_cap, thoi_gian) VALUES (?,?,?)",
                     (encounter_id, actor, now_iso()))


def access_log(conn, encounter_id, limit=50):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM truy_cap WHERE encounter_id = ? ORDER BY id DESC LIMIT ?", (encounter_id, limit)).fetchall()]


def get_user(conn, username):
    return conn.execute("SELECT * FROM nguoi_dung WHERE username = ?", (username,)).fetchone()


def count_users(conn):
    return conn.execute("SELECT COUNT(*) FROM nguoi_dung").fetchone()[0]


def create_user(conn, username, ho_ten, vai_tro, khoa, password_hash):
    with conn:
        conn.execute(
            "INSERT INTO nguoi_dung (username, ho_ten, vai_tro, khoa, password_hash) VALUES (?, ?, ?, ?, ?)",
            (username, ho_ten, vai_tro, khoa, password_hash))


def log_login(conn, username, ok):
    with conn:
        conn.execute("INSERT INTO dang_nhap (username, thanh_cong, thoi_gian) VALUES (?, ?, ?)",
                     (username, 1 if ok else 0, now_iso()))


def login_log(conn, limit=100):
    return conn.execute("SELECT * FROM dang_nhap ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def copied_fields(conn, encounter_id):
    """Danh sách các trường đã được chép từ lượt khám trước khi lưu (xem service.score_and_store)."""
    rows = conn.execute(
        "SELECT ghi_chu FROM nhat_ky WHERE encounter_id = ? AND hanh_dong = ? ORDER BY id",
        (encounter_id, COPIED_ACTION)).fetchall()
    return [r[0] for r in rows]


COPIED_ACTION = "chép_từ_lịch_sử"
