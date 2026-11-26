import re
import unicodedata
from collections import Counter

import pandas as pd

from anomaly.features import to_number, to_ts
from config import DIAGNOSIS_CODE_PATTERN, PROCEDURE_CODE_PATTERN

REQUIRED_FIELDS = ["PATIENT", "ENCOUNTERCLASS", "START", "STOP", "BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST"]
DATE_FIELDS = {"START", "STOP", "BIRTHDATE"}
NUM_FIELDS = {"BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST"}

DEFAULT_RULES_CONFIG = {
    "required_fields": list(REQUIRED_FIELDS),
    "birthdate_required_for_new_patient": True,
    "age_min": 0.0,
    "age_max": 120.0,
    "duplicate_cost_tolerance": 0.005,
    "recent_window_days": 30,
    "first_encounter_gap_days": 3650.0,
    "procedure_code_pattern": PROCEDURE_CODE_PATTERN,
    "diagnosis_code_pattern": DIAGNOSIS_CODE_PATTERN,
    "identity_check": True,
}

# Cờ cứng: đưa lượt khám vào trạng thái "bất thường".
HARD_RULE_CODES = {
    "date_logic", "birthdate_mismatch", "age_range",
    "code_missing", "code_format", "diagnosis_code_missing", "diagnosis_code_format",
    "document_missing", "signature_missing", "identity_gender_mismatch",
}
# Cờ thông tin: hiển thị để người dùng xác nhận, không làm đổi trạng thái và không tính là phát hiện.
INFO_RULE_CODES = {"identity_name_mismatch"}

RULE_MESSAGES = {
    "missing": "Thiếu hoặc không đọc được trường: {fields}",
    "duplicate": "Trùng lượt khám đã lưu (cùng bệnh nhân, thời điểm, loại, mã và chi phí)",
    "date_logic": "Ngày kết thúc trước ngày bắt đầu",
    "age_range": "Tuổi tại lượt khám ({age:.1f} năm) ngoài khoảng hợp lệ [{lo:g}, {hi:g}]",
    "birthdate_mismatch": "Ngày sinh không khớp với ngày sinh trong lịch sử của bệnh nhân ({ref})",
    "code_missing": "Có thủ thuật/dịch vụ nhưng thiếu mã thủ tục (CODE)",
    "code_format": "Mã thủ tục ({code}) không đúng định dạng quy định",
    "diagnosis_code_missing": "Có chẩn đoán bằng chữ nhưng thiếu mã ICD-10",
    "diagnosis_code_format": "Mã chẩn đoán ({code}) không đúng định dạng ICD-10",
    "document_missing": "Hồ sơ được khai báo là thiếu phiếu hoặc biểu mẫu",
    "signature_missing": "Tài liệu được khai báo là chưa ký số",
    "identity_gender_mismatch": "Giới tính ({value}) khác giới tính trong lịch sử của bệnh nhân ({ref})",
    "identity_name_mismatch": ("Họ tên khác với lịch sử của bệnh nhân ({ref}). Có thể do đổi tên "
                               "hoặc nhập sai, cần xác nhận"),
}


def is_blank(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def text_of(value):
    return "" if is_blank(value) else str(value).strip()


def fold_text(value):
    """So khớp không phân biệt hoa thường và dấu tiếng Việt."""
    if is_blank(value):
        return ""
    s = unicodedata.normalize("NFD", str(value))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().replace("đ", "d").split())


def _bad_field(field, value):
    if is_blank(value):
        return True
    if field in DATE_FIELDS:
        return to_ts(value) is None
    if field in NUM_FIELDS:
        return to_number(value) is None
    return False


def find_missing(record, has_history, cfg):
    fields = list(cfg["required_fields"])
    if cfg["birthdate_required_for_new_patient"] and not has_history:
        fields.append("BIRTHDATE")
    missing = [f for f in fields if _bad_field(f, record.get(f))]
    if "BIRTHDATE" not in fields and not is_blank(record.get("BIRTHDATE")) \
            and _bad_field("BIRTHDATE", record.get("BIRTHDATE")):
        missing.append("BIRTHDATE")
    return missing


def is_duplicate(record, start, history, cfg):
    """Trùng nếu lịch sử có lượt khám cùng thời điểm, loại, mã và tổng chi phí."""
    if start is None:
        return False
    cost = to_number(record.get("TOTAL_CLAIM_COST"))
    cls, code = text_of(record.get("ENCOUNTERCLASS")), text_of(record.get("CODE"))
    tol = cfg["duplicate_cost_tolerance"]
    for h in history:
        if to_ts(h.get("START")) != start:
            continue
        if text_of(h.get("ENCOUNTERCLASS")) != cls or text_of(h.get("CODE")) != code:
            continue
        hist_cost = to_number(h.get("TOTAL_CLAIM_COST"))
        if cost is None or hist_cost is None or abs(cost - hist_cost) > tol:
            continue
        return True
    return False


def majority(values):
    values = [v for v in values if v not in (None, "")]
    return Counter(values).most_common(1)[0][0] if values else None


def birth_majority(births):
    """Ngày sinh xuất hiện nhiều nhất trong lịch sử, đã chuẩn hóa về ngày. None nếu không có."""
    normalized = [b.normalize() for b in births if b is not None]
    return majority(normalized)


def code_checks(record, cfg):
    """Kiểm tra mã thủ tục và mã chẩn đoán ICD-10 nhập tay."""
    flags = []
    desc = text_of(record.get("DESCRIPTION"))
    code = text_of(record.get("CODE"))
    if desc and not code:
        flags.append(make_flag("code_missing"))
    elif code and cfg.get("procedure_code_pattern") and not re.fullmatch(cfg["procedure_code_pattern"], code):
        flags.append(make_flag("code_format", code=code))

    dx_text = text_of(record.get("DIAGNOSIS"))
    dx_code = text_of(record.get("DIAGNOSIS_CODE")).upper()
    if dx_text and not dx_code:
        flags.append(make_flag("diagnosis_code_missing"))
    elif dx_code and cfg.get("diagnosis_code_pattern") and not re.fullmatch(cfg["diagnosis_code_pattern"], dx_code):
        flags.append(make_flag("diagnosis_code_format", code=dx_code))
    return flags


def document_checks(record):
    """Phiếu, biểu mẫu và chữ ký số do người nhập khai báo. Chưa khai báo thì không gắn cờ."""
    flags = []
    if text_of(record.get("PHIEU_DAY_DU")) == "khong":
        flags.append(make_flag("document_missing"))
    if text_of(record.get("DA_KY_SO")) == "khong":
        flags.append(make_flag("signature_missing"))
    return flags


def identity_checks(record, history, cfg):
    """So danh tính với lịch sử bệnh nhân. Giới tính là cờ cứng; họ tên chỉ là cờ thông tin."""
    if not cfg.get("identity_check", True) or not history:
        return []
    flags = []
    gender = text_of(record.get("GENDER"))
    ref_gender = majority([text_of(h.get("GENDER")) for h in history])
    if gender and ref_gender and gender != ref_gender:
        flags.append(make_flag("identity_gender_mismatch", value=gender, ref=ref_gender))

    names = [(h.get("LAST"), h.get("FIRST")) for h in history]
    full = lambda last, first: " ".join(p for p in (text_of(last), text_of(first)) if p)
    cur = full(record.get("LAST"), record.get("FIRST"))
    ref_name = majority([full(l, f) for l, f in names])
    if cur and ref_name and fold_text(cur) != fold_text(ref_name):
        flags.append(make_flag("identity_name_mismatch", ref=ref_name))
    return flags


def make_flag(rule_code, **kwargs):
    return {"code": rule_code, "message": RULE_MESSAGES[rule_code].format(**kwargs)}
