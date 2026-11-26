import sqlite3

import pytest

from app import auth, db, service
from app.seed_demo import DEFAULT_ACCOUNTS, ensure_default_users
from app.service import EditError

NHAP = auth.User("nhap", "Điều dưỡng A", auth.ROLE_ENTRY, "Khoa Khám")
XULY = auth.User("xuly", "BS B", auth.ROLE_PROCESS, "Khoa Giám định")



@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "perm.sqlite")
    yield c
    c.close()


@pytest.fixture
def no_rescore(monkeypatch):
    monkeypatch.setattr(service, "rescore", lambda *a, **k: (None, True))


def fake_record(i="L1"):
    return {"Id": i, "PATIENT": "P1", "ENCOUNTERCLASS": "emergency", "CODE": "1",
            "START": "2020-01-10T08:00:00", "STOP": "2020-01-10T09:00:00", "DESCRIPTION": None,
            "BASE_ENCOUNTER_COST": 10.0, "TOTAL_CLAIM_COST": 20.0, "REASONDESCRIPTION": None,
            "BIRTHDATE": "1990-01-10", "FIRST": "An", "LAST": "Nguyễn", "GENDER": "F"}


def fake_result():
    return {"model_version": "vtest", "status": "bất thường",
            "rule_flags": [{"code": "date_logic", "message": "x"}],
            "anomaly_score": None, "threshold": 0.5, "group": "emergency", "model_used": "group",
            "reasons": [], "features": {"age_years": 30.0, "duration_hours": float("nan")}}


def seed_flagged(conn, i="L1"):
    with conn:
        db.insert_encounter(conn, fake_record(i), "manual")
        db.save_score(conn, i, fake_result())
        db.ensure_workflow(conn, i, "tester")


def state(conn, i="L1"):
    return db.get_workflow(conn, i)["trang_thai"]


# ---- Mật khẩu và đăng nhập ----

def test_password_hash_roundtrip_and_not_plaintext():
    stored = auth.hash_password("matkhau123")
    assert "matkhau123" not in stored
    assert auth.verify_password("matkhau123", stored)
    assert not auth.verify_password("sai", stored)


def test_password_hashes_use_random_salt():
    assert auth.hash_password("abc") != auth.hash_password("abc")


def test_verify_rejects_malformed_stored_value():
    assert not auth.verify_password("abc", "không-phải-định-dạng")
    assert not auth.verify_password("abc", "md5$1$00$00")


def test_authenticate_success_and_failure_are_logged(conn):
    db.create_user(conn, "xuly", "BS B", auth.ROLE_PROCESS, "Khoa Giám định", auth.hash_password("matkhau123"))
    user = auth.authenticate(conn, " xuly ", "matkhau123")
    assert user == auth.User("xuly", "BS B", auth.ROLE_PROCESS, "Khoa Giám định")
    assert auth.authenticate(conn, "xuly", "sai") is None
    assert auth.authenticate(conn, "khongco", "matkhau123") is None
    rows = [(r["username"], r["thanh_cong"]) for r in db.login_log(conn)]
    assert rows == [("khongco", 0), ("xuly", 0), ("xuly", 1)]


def test_inactive_user_cannot_login(conn):
    db.create_user(conn, "xuly", "BS B", auth.ROLE_PROCESS, "", auth.hash_password("matkhau123"))
    with conn:
        conn.execute("UPDATE nguoi_dung SET active = 0 WHERE username = 'xuly'")
    assert auth.authenticate(conn, "xuly", "matkhau123") is None


def test_login_log_is_append_only(conn):
    db.log_login(conn, "xuly", True)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE dang_nhap SET thanh_cong = 0")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM dang_nhap")


def test_default_accounts_created_only_once(conn):
    created = ensure_default_users(conn)
    assert [c[0] for c in created] == [a[0] for a in DEFAULT_ACCOUNTS]
    assert ensure_default_users(conn) == []
    assert db.get_user(conn, "xuly")["vai_tro"] == auth.ROLE_PROCESS


# ---- Ma trận quyền ----

def test_permission_matrix():
    assert NHAP.can(auth.PERM_NHAP_BAN_GHI) and not NHAP.can(auth.PERM_XEM_DANH_SACH)
    assert not NHAP.can(auth.PERM_XU_LY) and not NHAP.can(auth.PERM_XEM_NHAT_KY)
    assert XULY.can(auth.PERM_QUAN_LY_MO_HINH)
    assert all(XULY.can(p) for p in auth.PERMISSIONS)


def test_unknown_role_has_no_permissions():
    ghost = auth.User("x", "x", "vai_la", "")
    assert not any(ghost.can(p) for p in auth.PERMISSIONS)


def test_entry_user_can_score_but_not_process():
    service._authorize(NHAP, auth.PERM_NHAP_BAN_GHI)
    with pytest.raises(EditError):
        service._authorize(NHAP, auth.PERM_XU_LY)


def test_none_actor_is_rejected(conn, no_rescore):
    seed_flagged(conn)
    with pytest.raises(EditError):
        service.start_processing(conn, "L1", actor=None)
    assert state(conn) == "chờ xử lý"


def test_plain_string_actor_is_rejected(conn, no_rescore):
    seed_flagged(conn)
    with pytest.raises(EditError):
        service.start_processing(conn, "L1", actor="bs tùy ý")
    assert state(conn) == "chờ xử lý"


def test_entry_user_cannot_start_processing(conn, no_rescore):
    seed_flagged(conn)
    with pytest.raises(EditError, match="không có quyền"):
        service.start_processing(conn, "L1", actor=NHAP)
    assert state(conn) == "chờ xử lý"
    assert all(r["nguoi_thuc_hien"] != NHAP.name for r in db.audit_log(conn, "L1"))


def test_processing_user_can_run_full_cycle_and_audit_records_name(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=XULY)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "cần xem thêm", actor=XULY)
    assert state(conn) == "đã xử lý"
    names = {r["nguoi_thuc_hien"] for r in db.audit_log(conn, "L1") if r["hanh_dong"] != "tạo_xử_lý"}
    assert names == {XULY.name}


def test_entry_user_cannot_reopen_finished_case(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=XULY)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "xong", actor=XULY)
    with pytest.raises(EditError, match="không có quyền"):
        service.reopen_processing(conn, "L1", "mở lại", actor=NHAP)
    assert state(conn) == "đã xử lý"


def test_processing_user_can_reopen_finished_case(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=XULY)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "xong", actor=XULY)
    service.reopen_processing(conn, "L1", "kiểm tra lại", actor=XULY)
    assert state(conn) == "đang xử lý"
