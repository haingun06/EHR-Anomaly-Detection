import sqlite3

import pandas as pd
import pytest

from app import auth, db, service

BS_A = auth.User("bsa", "bs A", auth.ROLE_PROCESS, "")
BS_B = auth.User("bsb", "bs B", auth.ROLE_PROCESS, "")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.sqlite")
    yield c
    c.close()


@pytest.fixture
def no_rescore(monkeypatch):

    calls = []

    def fake(conn, model, encounter_id, actor=None):
        calls.append(encounter_id)
        return None, True

    monkeypatch.setattr(service, "rescore", fake)
    return calls


def fake_record(i="L1"):
    return {"Id": i, "PATIENT": "P1", "ENCOUNTERCLASS": "emergency", "CODE": "1",
            "START": "2020-01-10T08:00:00", "STOP": "2020-01-10T09:00:00", "DESCRIPTION": None,
            "BASE_ENCOUNTER_COST": 10.0, "TOTAL_CLAIM_COST": 20.0, "REASONDESCRIPTION": None,
            "BIRTHDATE": "1990-01-10", "FIRST": "An", "LAST": "Nguyễn", "GENDER": "F"}


def fake_result(version="vtest"):
    return {"model_version": version, "status": "bất thường", "rule_flags": [{"code": "date_logic", "message": "x"}],
            "anomaly_score": None, "threshold": 0.5, "group": "emergency", "model_used": "group",
            "reasons": [], "features": {"age_years": 30.0, "duration_hours": float("nan")}}


def seed_flagged(conn, i="L1"):
    with conn:
        db.insert_encounter(conn, fake_record(i), "manual")
        db.save_score(conn, i, fake_result())
        db.ensure_workflow(conn, i, "tester")


def state(conn, i="L1"):
    return db.get_workflow(conn, i)["trang_thai"]


def test_schema_has_three_states_only():
    assert db.STATES == ["chờ xử lý", "đang xử lý", "đã xử lý"]
    assert db.RESULTS == ["Đã cập nhật dữ liệu", "Xác nhận cảnh báo, cần xem xét thêm"]


def test_validate_transition_rules():
    db.validate_transition("chờ xử lý", "đang xử lý", None)
    db.validate_transition("đang xử lý", "đã xử lý", "")
    db.validate_transition("đã xử lý", "đang xử lý", "mở lại để kiểm tra")
    with pytest.raises(db.TransitionError):
        db.validate_transition("chờ xử lý", "đã xử lý", "")
    with pytest.raises(db.TransitionError):
        db.validate_transition("đang xử lý", "chờ xử lý", "")
    with pytest.raises(db.TransitionError):
        db.validate_transition("đã xử lý", "đang xử lý", "   ")


def test_full_cycle_writes_audit_in_order(conn):
    seed_flagged(conn)
    assert state(conn) == "chờ xử lý"
    service.start_processing(conn, "L1", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "cần xem thêm", actor=BS_A)
    service.reopen_processing(conn, "L1", "kiểm tra lại", actor=BS_B)
    assert state(conn) == "đang xử lý"
    log = db.audit_log(conn, "L1")
    assert [r["den_trang_thai"] for r in log] == ["chờ xử lý", "đang xử lý", "đã xử lý", "đang xử lý"]
    assert log[2]["ghi_chu"].startswith("Xác nhận cảnh báo, cần xem xét thêm. ")


def test_invalid_transition_writes_nothing(conn):
    seed_flagged(conn)
    with pytest.raises(service.EditError):
        service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "vội", actor=BS_A)
    assert state(conn) == "chờ xử lý"
    assert len(db.audit_log(conn, "L1")) == 1


def test_finish_saves_outcome_fields(conn):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "chuyển khoa khác", actor=BS_A)
    wf = db.get_workflow(conn, "L1")
    assert wf["trang_thai"] == "đã xử lý"
    assert wf["ket_qua"] == db.RESULT_CONFIRMED
    assert wf["ghi_chu_ket_qua"] == "chuyển khoa khác"
    assert wf["nguoi_hoan_tat"] == "bs A" and wf["hoan_tat_luc"]


def test_reopen_clears_previous_outcome(conn):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "ok", actor=BS_A)
    service.reopen_processing(conn, "L1", "lý do", actor=BS_A)
    wf = db.get_workflow(conn, "L1")
    assert wf["ket_qua"] is None and wf["ghi_chu_ket_qua"] is None and wf["hoan_tat_luc"] is None


def test_state_actions_require_correct_state(conn):
    seed_flagged(conn)
    with pytest.raises(service.EditError, match="đang xử lý"):
        service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "x", actor=BS_A)
    with pytest.raises(service.EditError, match="đã xử lý"):
        service.reopen_processing(conn, "L1", "x", actor=BS_A)
    service.start_processing(conn, "L1", actor=BS_A)
    with pytest.raises(service.EditError, match="chờ xử lý"):
        service.start_processing(conn, "L1", actor=BS_A)


def test_finish_requires_note_and_valid_result(conn):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    with pytest.raises(service.EditError, match="ghi chú"):
        service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "   ", actor=BS_A)
    with pytest.raises(service.EditError, match="kết luận"):
        service.finish_processing(conn, "L1", "tùy ý", "ghi chú", actor=BS_A)
    assert state(conn) == "đang xử lý"


def test_reopen_requires_reason(conn):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "ok", actor=BS_A)
    with pytest.raises(service.EditError, match="lý do"):
        service.reopen_processing(conn, "L1", "  ", actor=BS_A)
    assert state(conn) == "đã xử lý"


def test_new_score_version_keeps_workflow_state(conn):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    with conn:
        _, created = db.save_score(conn, "L1", fake_result("v2"))
    assert created is True
    assert state(conn) == "đang xử lý"
    assert db.latest_score(conn, "L1")["model_version"] == "v2"


def test_save_score_is_idempotent_per_version(conn):
    seed_flagged(conn)
    _, created = db.save_score(conn, "L1", fake_result())
    assert created is False
    count = conn.execute("SELECT COUNT(*) FROM ket_qua_cham_diem WHERE encounter_id='L1'").fetchone()[0]
    assert count == 1

def test_list_queue_orders_pending_first_and_filters_status(conn):
    seed_flagged(conn, "A")
    seed_flagged(conn, "B")
    seed_flagged(conn, "C")
    service.start_processing(conn, "B", actor=BS_A)
    service.start_processing(conn, "C", actor=BS_A)
    service.finish_processing(conn, "C", db.RESULT_CONFIRMED, "ok", actor=BS_A)
    with conn:
        db.insert_encounter(conn, dict(fake_record("D"), START="2020-02-01T08:00:00",
                                       STOP="2020-02-01T09:00:00"), "manual")
        db.save_score(conn, "D", dict(fake_result(), status="bình thường", rule_flags=[]))

    queue = [i["Id"] for i in db.list_items(conn, sort="trang_thai")]
    assert queue == ["A", "B", "C"]
    assert [i["Id"] for i in db.list_items(conn, status="đã xử lý")] == ["C"]
    assert [i["Id"] for i in db.list_items(conn, status="chờ xử lý")] == ["A"]
    everything = [i["Id"] for i in db.list_items(conn, flagged_only=False)]
    assert sorted(everything) == ["A", "B", "C", "D"]


def test_list_items_carries_name_and_outcome_for_display(conn):
    seed_flagged(conn, "A")
    row = db.list_items(conn)[0]
    assert row["FIRST"] == "An" and row["LAST"] == "Nguyễn"
    assert row["trang_thai"] == "chờ xử lý" and row["status"] == "bất thường"


def test_duplicate_encounter_id_rejected(conn):
    seed_flagged(conn)
    with pytest.raises(db.EncounterExists):
        db.insert_encounter(conn, fake_record("L1"), "manual")

def test_audit_log_is_append_only(conn):
    seed_flagged(conn)
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("UPDATE nhat_ky SET ghi_chu = 'sửa'")
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("DELETE FROM nhat_ky")


def test_thay_doi_and_truy_cap_are_append_only(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "sửa", actor=BS_A)
    db.add_access(conn, "L1", "bs A")
    updates = {"thay_doi": "UPDATE thay_doi SET ghi_chu = 'x'",
               "truy_cap": "UPDATE truy_cap SET nguoi_truy_cap = 'x'"}
    for table, update_sql in updates.items():
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(update_sql)
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(f"DELETE FROM {table}")


def test_access_log_newest_first(conn):
    seed_flagged(conn)
    db.add_access(conn, "L1", "bs A")
    db.add_access(conn, "L1", "bs B")
    assert [r["nguoi_truy_cap"] for r in db.access_log(conn, "L1")] == ["bs B", "bs A"]

def test_parse_money_accepts_thousand_separators():
    assert service.parse_money("1.250.000") == "1250000"
    assert service.parse_money("1.25") == "1.25"
    assert service.parse_money("abc") == "abc"
    assert service.parse_money(None) == ""


def test_validate_input_messages():
    raw = {"PATIENT": "", "ENCOUNTERCLASS": "xyz", "START": "không", "STOP": "2020-01-10 09:00",
           "BIRTHDATE": "", "BASE_ENCOUNTER_COST": "-1", "TOTAL_CLAIM_COST": "abc"}
    record, errors = service.validate_input(raw, has_history=False)
    text = " | ".join(errors)
    assert "PATIENT" in text and "ENCOUNTERCLASS" in text and "START" in text
    assert "BIRTHDATE" in text and "TOTAL_CLAIM_COST" in text
    assert record["Id"]


def test_validate_input_accepts_logic_errors():
    raw = {"PATIENT": "P9", "ENCOUNTERCLASS": "wellness", "START": "2020-01-10 09:00",
           "STOP": "2020-01-10 08:00", "BIRTHDATE": "1990-01-01", "FIRST": "An", "LAST": "Nguyễn",
           "GENDER": "F", "BASE_ENCOUNTER_COST": "10", "TOTAL_CLAIM_COST": "20"}
    _, errors = service.validate_input(raw, has_history=False)
    assert errors == []

def test_new_patient_must_have_name_and_gender():
    raw = {"PATIENT": "P9", "ENCOUNTERCLASS": "wellness", "START": "2020-01-10 09:00",
           "STOP": "2020-01-10 10:00", "BIRTHDATE": "1990-01-01", "BASE_ENCOUNTER_COST": "10",
           "TOTAL_CLAIM_COST": "20"}
    _, errors = service.validate_input(raw, has_history=False)
    text = " | ".join(errors)
    assert "LAST" in text and "FIRST" in text and "GENDER" in text
    _, errors_old = service.validate_input(raw, has_history=True)
    assert errors_old == []


def test_fill_from_history_copies_blank_demographics_only():
    history = [{"START": "2019-01-01T08:00:00", "FIRST": "Cũ", "LAST": "Họ", "GENDER": "M",
                "ADDRESS": "12 Lê Lợi", "CITY": "Huế", "STATE": None, "ZIP": "01104"},
               {"START": "2019-06-01T08:00:00", "FIRST": "Mới", "LAST": None, "GENDER": None,
                "ADDRESS": None, "CITY": None, "STATE": None, "ZIP": None}]
    record = {"FIRST": None, "LAST": None, "GENDER": "F", "ADDRESS": None, "CITY": None, "STATE": None, "ZIP": None}
    out, copied = service._fill_from_history(record, history)
    assert out["FIRST"] == "Mới" and out["LAST"] == "Họ" and out["GENDER"] == "F"
    assert out["ADDRESS"] == "12 Lê Lợi" and out["CITY"] == "Huế" and out["ZIP"] == "01104"
    # Trường đã được chép phải được ghi lại để người dùng xác nhận
    assert set(copied) == {"FIRST", "LAST", "ADDRESS", "CITY", "ZIP"}


def test_score_and_store_refuses_null_not_null_fields(conn):
    for field in ["START", "STOP", "PATIENT", "ENCOUNTERCLASS"]:
        bad = dict(fake_record("L-bad"), **{field: None})
        with pytest.raises(ValueError, match=field):
            service.score_and_store(conn, None, bad, actor=BS_A)
    assert db.count_encounters(conn) == 0

def test_update_requires_processing_state(conn, no_rescore):
    seed_flagged(conn)
    with pytest.raises(service.EditError, match="đang xử lý"):
        service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "lý do", actor=BS_A)
    assert no_rescore == []


def test_update_requires_reason(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    with pytest.raises(service.EditError, match="lý do"):
        service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "   ", actor=BS_A)


def test_update_saves_fields_and_versions_without_changing_state(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    changed = service.update_emr(conn, None, "L1", {"STOP": "2020-01-10 10:30", "CITY": "Huế"},
                                 "đối chiếu phiếu giấy", actor=BS_A)
    assert sorted(changed) == ["CITY", "STOP"]
    row = db.get_encounter(conn, "L1")
    assert row["revision"] == 1 and row["CITY"] == "Huế"
    assert pd.Timestamp(row["STOP"]) == pd.Timestamp("2020-01-10 10:30")
    assert state(conn) == "đang xử lý"
    assert no_rescore == ["L1"]

    log = {r["truong"]: r for r in db.edit_log(conn, "L1")}
    assert set(log) == {"CITY", "STOP"}
    assert log["CITY"]["gia_tri_cu"] is None and log["CITY"]["gia_tri_moi"] == "Huế"
    assert log["STOP"]["ghi_chu"] == "đối chiếu phiếu giấy" and log["STOP"]["nguoi_thuc_hien"] == "bs A"


def test_update_without_real_change_is_refused(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    with pytest.raises(service.EditError, match="Không có thay đổi"):
        service.update_emr(conn, None, "L1", {"START": "2020-01-10 08:00:00", "STOP": "2020-01-10 09:00:00",
                                              "TOTAL_CLAIM_COST": "20"}, "không đổi gì", actor=BS_A)
    assert db.get_encounter(conn, "L1")["revision"] == 0
    assert no_rescore == []


def test_update_rejects_invalid_values_and_writes_nothing(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    with pytest.raises(service.EditError) as info:
        service.update_emr(conn, None, "L1", {"START": "không phải ngày", "PAYER_COVERAGE": "-5"}, "thử", actor=BS_A)
    assert len(info.value.errors) == 2
    assert db.get_encounter(conn, "L1")["revision"] == 0
    assert db.edit_log(conn, "L1") == []


def test_multiple_updates_in_one_processing_session(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "lần 1", actor=BS_A)
    service.update_emr(conn, None, "L1", {"CITY": "Đà Nẵng"}, "lần 2", actor=BS_A)
    assert db.get_encounter(conn, "L1")["revision"] == 2
    assert state(conn) == "đang xử lý"


def test_finish_with_updated_result_needs_an_update_in_this_session(conn, no_rescore):
    seed_flagged(conn)
    with conn:
        conn.execute("UPDATE luot_kham SET revision = 1 WHERE Id = 'L1'")
    service.start_processing(conn, "L1", actor=BS_A)
    with pytest.raises(service.EditError, match="Chưa có cập nhật"):
        service.finish_processing(conn, "L1", db.RESULT_UPDATED, "đã sửa", actor=BS_A)
    service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "sửa trong lần này", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_UPDATED, "đã đối chiếu", actor=BS_A)
    assert state(conn) == "đã xử lý"
    assert db.get_workflow(conn, "L1")["ket_qua"] == db.RESULT_UPDATED


def test_finish_confirm_does_not_need_an_update(conn):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "cần bác sĩ xem lại", actor=BS_A)
    assert state(conn) == "đã xử lý"


def test_edit_after_done_is_refused_until_reopened(conn, no_rescore):
    seed_flagged(conn)
    service.start_processing(conn, "L1", actor=BS_A)
    service.finish_processing(conn, "L1", db.RESULT_CONFIRMED, "ok", actor=BS_A)
    with pytest.raises(service.EditError, match="đang xử lý"):
        service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "sửa sau khi xong", actor=BS_A)
    service.reopen_processing(conn, "L1", "cần sửa thêm", actor=BS_A)
    service.update_emr(conn, None, "L1", {"CITY": "Huế"}, "sửa sau khi mở lại", actor=BS_A)
    assert db.get_encounter(conn, "L1")["revision"] == 1


def test_db_refuses_to_update_unlisted_columns(conn):
    seed_flagged(conn)
    with pytest.raises(ValueError):
        db.apply_emr_changes(conn, "L1", {"PATIENT": "HACK"}, "thử", "bs A")
    assert db.get_encounter(conn, "L1")["PATIENT"] == "P1"


def test_service_editable_fields_are_allowed_by_db():
    names = {f for f, _, _ in service.EMR_FIELDS}
    assert names <= db.EDITABLE_COLUMNS
    assert "PATIENT" not in names and "Id" not in names

def test_schema_outdated_database_is_refused(tmp_path):
    import sqlite3 as sq
    old = tmp_path / "old.sqlite"
    c = sq.connect(old)
    c.execute("CREATE TABLE luot_kham (Id TEXT PRIMARY KEY, START TEXT, STOP TEXT, PATIENT TEXT, "
              "ENCOUNTERCLASS TEXT)")
    c.commit()
    c.close()
    with pytest.raises(db.SchemaOutdated, match="--reset"):
        db.connect(old)


def test_schema_version_outdated_is_refused(tmp_path):
    """CSDL có đủ cột nhưng ghi phiên bản cũ (trạng thái xử lý cũ) cũng phải nạp lại."""
    path = tmp_path / "v2.sqlite"
    good = db.connect(path)
    good.execute("PRAGMA user_version = 2")
    good.commit()
    good.close()
    with pytest.raises(db.SchemaOutdated, match="--reset"):
        db.connect(path)


def test_new_database_gets_current_schema_version(tmp_path):
    c = db.connect(tmp_path / "fresh.sqlite")
    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    c.close()
