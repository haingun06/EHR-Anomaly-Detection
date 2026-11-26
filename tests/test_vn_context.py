import pytest

from anomaly import rules
from anomaly.detector import analyze_record, decide_status, load_model
from anomaly.features import to_ts, to_ts_vn
from anomaly.rules import DEFAULT_RULES_CONFIG, fold_text
from app import auth, db, portal, present, service
from config import MODEL_PATH

needs_model = pytest.mark.skipif(not MODEL_PATH.exists(), reason="Chưa có file mô hình")
NHAP = auth.User("nl", "Điều dưỡng", auth.ROLE_ENTRY, "")
XU_LY = auth.User("xl", "Nhân viên", auth.ROLE_PROCESS, "")


def base(**over):
    rec = {"Id": "L1", "PATIENT": "P1", "ENCOUNTERCLASS": "ambulatory", "CODE": "1234",
           "DESCRIPTION": "Khám", "START": to_ts("2024-03-01 09:00"), "STOP": to_ts("2024-03-01 09:15"),
           "BIRTHDATE": to_ts("1980-01-01"), "FIRST": "An", "LAST": "Nguyễn Văn",
           "GENDER": "M", "BASE_ENCOUNTER_COST": 100.0, "TOTAL_CLAIM_COST": 100.0,
           "DIAGNOSIS": None, "DIAGNOSIS_CODE": None, "PHIEU_DAY_DU": None, "DA_KY_SO": None}
    rec.update(over)
    return rec


def codes(rec, history=()):
    a = analyze_record(rec, list(history), DEFAULT_RULES_CONFIG)
    return {f["code"] for f in a["rule_flags"]}, a


# ---------- 1. Ngày giờ kiểu Việt Nam ----------

def test_to_ts_vn_reads_day_first():
    assert to_ts_vn("03/04/2024 09:30") == to_ts("2024-04-03 09:30")
    assert to_ts_vn("03/04/2024") == to_ts("2024-04-03")


def test_to_ts_vn_still_accepts_iso():
    assert to_ts_vn("2024-04-03 09:30") == to_ts("2024-04-03 09:30")


@pytest.mark.parametrize("bad", ["31/02/2024", "03/04/2024 25:00", "03/04/2024 09:75", "abc", "13/13/2024"])
def test_to_ts_vn_rejects_invalid(bad):
    assert to_ts_vn(bad) is None


def test_validate_input_uses_day_first_and_reports_bad_format():
    raw = {"PATIENT": "P9", "ENCOUNTERCLASS": "wellness", "START": "05/06/2024 08:00",
           "STOP": "05/06/2024 08:30", "BIRTHDATE": "15/08/1990", "LAST": "Trần", "FIRST": "Bình",
           "GENDER": "F", "BASE_ENCOUNTER_COST": "1.250.000", "TOTAL_CLAIM_COST": "1250000"}
    rec, errors = service.validate_input(raw, has_history=False)
    assert errors == []
    assert rec["START"] == to_ts("2024-06-05 08:00")
    assert rec["BIRTHDATE"] == to_ts("1990-08-15")
    raw["START"] = "2024-13-05 08:00"
    _, errors = service.validate_input(raw, has_history=False)
    assert any("Bắt đầu" in e for e in errors)


# ---------- 2. Cờ age_range là lỗi cứng (sửa lỗi đã nêu trước đó) ----------

def test_age_range_alone_makes_record_abnormal():
    rec = base(BIRTHDATE=to_ts("1800-01-01"))  # tuổi > 120, không có lịch sử nên không có birthdate_mismatch
    found, a = codes(rec)
    assert found == {"age_range"}
    assert decide_status(a, ml_flag=False) == "bất thường"


# ---------- 3. Mã thủ tục và mã ICD-10 ----------

def test_code_missing_when_description_without_code():
    found, a = codes(base(CODE=None))
    assert "code_missing" in found
    assert decide_status(a, False) == "bất thường"


def test_code_format_rejects_non_numeric_procedure_code():
    found, _ = codes(base(CODE="ABC-1"))
    assert "code_format" in found


def test_diagnosis_text_needs_icd10_code():
    found, _ = codes(base(DIAGNOSIS="Viêm phổi", DIAGNOSIS_CODE=None))
    assert "diagnosis_code_missing" in found


def test_valid_icd10_code_passes_and_bad_format_is_flagged():
    ok, _ = codes(base(DIAGNOSIS="Hen phế quản", DIAGNOSIS_CODE="J45.9"))
    assert "diagnosis_code_missing" not in ok and "diagnosis_code_format" not in ok
    bad, _ = codes(base(DIAGNOSIS="Hen phế quản", DIAGNOSIS_CODE="j459"))
    assert "diagnosis_code_format" in bad


def test_icd10_normalises_lowercase_input_in_service():
    raw = {"PATIENT": "P1", "ENCOUNTERCLASS": "wellness", "START": "2024-01-01 08:00",
           "STOP": "2024-01-01 08:10", "BIRTHDATE": "1990-01-01", "LAST": "A", "FIRST": "B",
           "GENDER": "M", "BASE_ENCOUNTER_COST": "1", "TOTAL_CLAIM_COST": "1", "DIAGNOSIS_CODE": " j45.9 "}
    rec, errors = service.validate_input(raw, has_history=False)
    assert errors == [] and rec["DIAGNOSIS_CODE"] == "J45.9"


# ---------- 4. Phiếu và chữ ký số ----------

def test_document_missing_only_when_declared_missing():
    assert "document_missing" in codes(base(PHIEU_DAY_DU="khong"))[0]
    assert "document_missing" not in codes(base(PHIEU_DAY_DU="co"))[0]
    assert "document_missing" not in codes(base(PHIEU_DAY_DU=None))[0]


def test_signature_missing_is_hard_flag():
    found, a = codes(base(DA_KY_SO="khong"))
    assert "signature_missing" in found
    assert decide_status(a, False) == "bất thường"


def test_validate_input_rejects_unknown_document_value():
    raw = {"PATIENT": "P1", "ENCOUNTERCLASS": "wellness", "START": "2024-01-01 08:00",
           "STOP": "2024-01-01 08:10", "BIRTHDATE": "1990-01-01", "LAST": "A", "FIRST": "B",
           "GENDER": "M", "BASE_ENCOUNTER_COST": "1", "TOTAL_CLAIM_COST": "1", "PHIEU_DAY_DU": "có lẽ"}
    _, errors = service.validate_input(raw, has_history=False)
    assert any("PHIEU_DAY_DU" in e for e in errors)


# ---------- 5. Danh tính ----------

HIST = [{"START": to_ts("2020-01-01"), "LAST": "Nguyễn Văn", "FIRST": "An", "GENDER": "M"}]


def test_gender_mismatch_is_hard():
    found, a = codes(base(GENDER="F"), HIST)
    assert "identity_gender_mismatch" in found
    assert decide_status(a, False) == "bất thường"


def test_name_compare_ignores_vietnamese_diacritics():
    assert fold_text("Nguyễn Văn Đức") == fold_text("NGUYEN VAN DUC") == "nguyen van duc"
    found, _ = codes(base(LAST="Nguyen Van", FIRST="An"), HIST)
    assert "identity_name_mismatch" not in found


def test_name_mismatch_is_info_only():
    rec = base(LAST="Trần Thị", FIRST="Lan", GENDER="M")
    a = analyze_record(rec, HIST, DEFAULT_RULES_CONFIG)
    found = {f["code"] for f in a["rule_flags"]}
    assert "identity_name_mismatch" in found
    assert a["rule_hit"] is False            # không tính là phát hiện
    assert decide_status(a, False) == "bình thường"   # không đổi trạng thái


def test_identity_check_can_be_switched_off():
    cfg = dict(DEFAULT_RULES_CONFIG, identity_check=False)
    a = analyze_record(base(GENDER="F"), HIST, cfg)
    assert not any(f["code"].startswith("identity") for f in a["rule_flags"])


# ---------- 6. Lưu trữ, nhật ký chép dữ liệu, chấm lại ----------

@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite")
    yield c
    c.close()


@needs_model
def test_copied_fields_are_logged_for_confirmation(conn):
    model = load_model()
    first = service.validate_input({"PATIENT": "P5", "ENCOUNTERCLASS": "wellness", "START": "2024-01-01 08:00",
                                    "STOP": "2024-01-01 08:10", "BIRTHDATE": "1990-01-01", "LAST": "Lê",
                                    "FIRST": "Hoa", "GENDER": "F", "ADDRESS": "12 Lê Lợi", "CITY": "Q1",
                                    "BASE_ENCOUNTER_COST": "10", "TOTAL_CLAIM_COST": "10", "Id": "E1"}, False)[0]
    service.score_and_store(conn, model, first, actor=NHAP)
    later = service.validate_input({"PATIENT": "P5", "ENCOUNTERCLASS": "wellness", "START": "03/01/2024 08:00",
                                    "STOP": "03/01/2024 08:10", "BASE_ENCOUNTER_COST": "10",
                                    "TOTAL_CLAIM_COST": "10", "Id": "E2"}, True)[0]
    service.score_and_store(conn, model, later, actor=NHAP)
    notes = db.copied_fields(conn, "E2")
    assert len(notes) == 1 and "Địa chỉ" in notes[0] and "cần xác nhận" in notes[0]
    assert db.copied_fields(conn, "E1") == []


@needs_model
def test_manual_diagnosis_code_is_stored_and_reused_on_rescore(conn):
    model = load_model()
    raw = {"PATIENT": "P6", "ENCOUNTERCLASS": "ambulatory", "START": "2024-02-01 08:00",
           "STOP": "2024-02-01 08:20", "BIRTHDATE": "1985-05-05", "LAST": "Phạm", "FIRST": "Đức",
           "GENDER": "M", "BASE_ENCOUNTER_COST": "10", "TOTAL_CLAIM_COST": "10", "Id": "E9",
           "DIAGNOSIS": "Hen phế quản", "DIAGNOSIS_CODE": "j45.9", "CODE": "1", "DESCRIPTION": "Khám"}
    rec, errors = service.validate_input(raw, False)
    assert errors == []
    service.score_and_store(conn, model, rec, actor=NHAP)
    cond = db.conditions_for_encounter(conn, "E9")
    assert cond and cond[0]["CODE"] == "J45.9" and cond[0]["source"] == "manual"
    # Chấm lại phải thấy mã chẩn đoán đã lưu (không bị coi là thiếu mã)
    row = db.get_encounter(conn, "E9")
    rec2 = service._record_from_row(row)
    rec2.update(service._manual_diagnosis(conn, "E9"))
    assert rec2["DIAGNOSIS_CODE"] == "J45.9"
    assert "diagnosis_code_missing" not in codes(rec2)[0]


# ---------- 7. Cổng liên thông ----------

def test_portal_profiles_load_and_have_required_keys():
    profiles = portal.load_profiles()
    assert {"emch_gia_dinh", "kham_suc_khoe_gia_dinh"} <= set(profiles)
    for prof in profiles.values():
        assert set(prof["truong_bat_buoc"]) <= set(prof["anh_xa"])


def test_portal_rejects_records_with_open_warning():
    profile = portal.get_profile("emch_gia_dinh")
    row = {"Id": "X", "status": "bất thường", "ENCOUNTERCLASS": "ambulatory", "PATIENT": "P", "BIRTHDATE": "1990-01-01",
           "START": "2024-01-01 08:00", "STOP": "2024-01-01 08:10", "TOTAL_CLAIM_COST": 10, "CODE": "1",
           "DESCRIPTION": "Khám"}
    errors = portal.check_rows([{**row, "status": "bất thường"}], profile)
    assert any(e["truong"] == "trạng thái" for e in errors)


def test_portal_required_and_date_checks():
    profile = portal.get_profile("emch_gia_dinh")
    row = {"Id": "Y", "status": "bình thường", "ENCOUNTERCLASS": "ambulatory", "PATIENT": "P",
           "BIRTHDATE": None, "START": "2024-01-02 08:00", "STOP": "2024-01-01 08:00",
           "TOTAL_CLAIM_COST": 10, "CODE": "1", "DESCRIPTION": "Khám"}
    errors = portal.check_rows([row], profile)
    fields = {e["truong"] for e in errors}
    assert "BIRTHDATE" in fields and "STOP" in fields


def test_portal_export_uses_profile_date_format():
    profile = portal.get_profile("emch_gia_dinh")
    row = {"Id": "Z", "status": "bình thường", "ENCOUNTERCLASS": "ambulatory", "PATIENT": "P",
           "BIRTHDATE": "1990-01-05", "START": "2024-03-01 08:00", "STOP": "2024-03-01 08:15",
           "TOTAL_CLAIM_COST": "10", "BASE_ENCOUNTER_COST": "10", "PAYER_COVERAGE": None,
           "CODE": "1", "DESCRIPTION": "Khám"}
    out = portal.build_rows([row], profile)[0]
    assert out["NGAY_SINH"] == "05/01/1990"
    assert out["THOI_GIAN_BAT_DAU"] == "01/03/2024 08:00"
    assert out["MA_LUOT_KHAM"] == "Z"
    text = portal.to_csv_text([out], profile)
    assert text.splitlines()[0].startswith("MA_LUOT_KHAM")


# ---------- 8. Giao diện ----------

@needs_model
def test_ui_shows_vn_fields_and_portal_check(monkeypatch, tmp_path):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    import config
    from config import ROOT

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "ui.sqlite")
    st.cache_resource.clear()
    app = str(ROOT / "app" / "streamlit_app.py")

    at = AppTest.from_file(app, default_timeout=120)
    at.session_state["user"] = XU_LY
    at.run()
    assert not at.exception
    labels = [s.label for s in at.selectbox]
    assert any(l.startswith("Phiếu và biểu mẫu") for l in labels)
    assert any(l.startswith("Tài liệu đã ký số") for l in labels)
    assert any(t.label.startswith("Mã ICD-10") for t in at.text_input)

    at.session_state["page"] = "Mô hình và dữ liệu"
    at.run()
    assert not at.exception
    assert any("Kiểm tra trước khi gửi" in b.label for b in at.button)
