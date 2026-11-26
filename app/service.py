import re
import uuid

import pandas as pd

from anomaly.detector import score_record
from anomaly.features import to_number, to_ts, to_ts_vn
from anomaly.rules import is_blank
from app import auth, db

ENCOUNTER_CLASSES = ["wellness", "ambulatory", "outpatient", "urgentcare", "emergency", "inpatient"]
GENDERS = ["M", "F"]
GENDER_LABELS = {"": "Chọn...", "M": "Nam", "F": "Nữ"}
DOC_LABELS = {"": "Chưa khai báo", "co": "Đầy đủ", "khong": "Thiếu"}

DEMOGRAPHIC_FIELDS = ["FIRST", "LAST", "GENDER", "ADDRESS", "CITY", "STATE", "ZIP"]

REQUIRED_AT_SAVE = ("PATIENT", "ENCOUNTERCLASS", "START", "STOP")

# Nhãn trường theo bối cảnh Việt Nam: Quận/Huyện/Phường/Xã thay cho mô hình Mỹ.
EMR_FIELDS = [
    ("LAST", "Họ", "text"),
    ("FIRST", "Tên", "text"),
    ("GENDER", "Giới tính", "gender"),
    ("BIRTHDATE", "Ngày sinh", "date"),
    ("ADDRESS", "Địa chỉ", "text"),
    ("CITY", "Quận/Huyện/Phường/Xã", "text"),
    ("STATE", "Tỉnh/Thành phố", "text"),
    ("ZIP", "Mã bưu chính (nếu có)", "text"),
    ("PAYER", "Đơn vị thanh toán (PAYER)", "text"),
    ("PAYER_COVERAGE", "Phần BH chi trả", "money"),
    ("PROVIDER", "Bác sĩ phụ trách (PROVIDER)", "text"),
    ("ENCOUNTERCLASS", "Loại lượt khám", "class"),
    ("START", "Bắt đầu", "datetime"),
    ("STOP", "Kết thúc", "datetime"),
    ("REASONDESCRIPTION", "Lý do khám", "text"),
    ("CODE", "Mã thủ tục", "text"),
    ("DESCRIPTION", "Mô tả thủ tục", "text"),
    ("BASE_ENCOUNTER_COST", "Chi phí cơ bản", "money"),
    ("TOTAL_CLAIM_COST", "Tổng chi phí", "money"),
    ("PHIEU_DAY_DU", "Phiếu và biểu mẫu đầy đủ", "doc"),
    ("DA_KY_SO", "Tài liệu đã ký số", "doc"),
]
EMR_LABELS = {f: label for f, label, _ in EMR_FIELDS}


class EditError(Exception):
    """Lỗi nghiệp vụ khi chỉnh sửa, xác nhận. errors chứa từng lỗi để hiển thị."""

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or [message]


def _text(value):
    return None if is_blank(value) else str(value).strip()


def parse_money(text):
    """Chấp nhận dạng 1.250.000 như trong mẫu, đổi về 1250000 trước khi kiểm tra."""
    text = "" if text is None else str(text).strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    return text


def parse_doc(raw):
    """Giá trị khai báo phiếu/chữ ký: 'co', 'khong' hoặc None (chưa khai báo). Trả (giá trị, lỗi)."""
    text = _text(raw)
    if text is None:
        return None, None
    key = text.lower()
    if key in ("co", "có", "y", "yes"):
        return "co", None
    if key in ("khong", "không", "n", "no"):
        return "khong", None
    return None, "chỉ nhận 'co' hoặc 'khong'"


def validate_input(raw, has_history):
    """Kiểm tra định dạng đầu vào. Lỗi logic (ví dụ ngày kết thúc trước ngày bắt đầu) không chặn lưu, luật sẽ gắn cờ."""
    errors = []
    record = {}

    patient = _text(raw.get("PATIENT")) or ""
    if not patient:
        errors.append("Thiếu mã bệnh nhân (PATIENT)")
    record["PATIENT"] = patient

    cls = _text(raw.get("ENCOUNTERCLASS")) or ""
    if cls not in ENCOUNTER_CLASSES:
        errors.append("Loại lượt khám (ENCOUNTERCLASS) không hợp lệ")
    record["ENCOUNTERCLASS"] = cls

    for field, label in [("START", "Bắt đầu (START)"), ("STOP", "Kết thúc (STOP)")]:
        value = to_ts_vn(raw.get(field))
        if value is None:
            errors.append(f"{label}: cần định dạng DD/MM/YYYY HH:MM (hoặc YYYY-MM-DD HH:MM)")
        record[field] = value

    birth_raw = _text(raw.get("BIRTHDATE"))
    if birth_raw:
        birth = to_ts_vn(birth_raw)
        if birth is None:
            errors.append("Ngày sinh (BIRTHDATE): cần định dạng DD/MM/YYYY (hoặc YYYY-MM-DD)")
        record["BIRTHDATE"] = birth
    elif not has_history:
        errors.append("Bệnh nhân mới: cần nhập ngày sinh (BIRTHDATE)")
        record["BIRTHDATE"] = None
    else:
        record["BIRTHDATE"] = None

    for field, label in [("LAST", "họ (LAST)"), ("FIRST", "tên (FIRST)")]:
        value = _text(raw.get(field))
        if value is None and not has_history:
            errors.append(f"Bệnh nhân mới: cần nhập {label}")
        record[field] = value

    gender = _text(raw.get("GENDER"))
    if gender is not None and gender not in GENDERS:
        errors.append("Giới tính (GENDER) chỉ nhận M hoặc F")
    if gender is None and not has_history:
        errors.append("Bệnh nhân mới: cần chọn giới tính (GENDER)")
    record["GENDER"] = gender

    for field in ["ADDRESS", "CITY", "STATE", "ZIP"]:
        record[field] = _text(raw.get(field))

    for field, label in [("BASE_ENCOUNTER_COST", "Chi phí cơ bản"), ("TOTAL_CLAIM_COST", "Tổng chi phí")]:
        value = to_number(parse_money(raw.get(field)))
        if value is None or value < 0:
            errors.append(f"{label} ({field}): cần là số không âm")
        record[field] = value

    cov_raw = _text(raw.get("PAYER_COVERAGE"))
    cov = None
    if cov_raw is not None:
        cov = to_number(parse_money(cov_raw))
        if cov is None or cov < 0:
            errors.append("Phần BH chi trả (PAYER_COVERAGE): cần là số không âm")
    record["PAYER_COVERAGE"] = cov

    phieu, err = parse_doc(raw.get("PHIEU_DAY_DU"))
    if err:
        errors.append(f"Phiếu và biểu mẫu (PHIEU_DAY_DU): {err}")
    record["PHIEU_DAY_DU"] = phieu
    signed, err = parse_doc(raw.get("DA_KY_SO"))
    if err:
        errors.append(f"Ký số (DA_KY_SO): {err}")
    record["DA_KY_SO"] = signed

    record["PAYER"] = _text(raw.get("PAYER"))
    record["PROVIDER"] = _text(raw.get("PROVIDER"))
    record["REASONDESCRIPTION"] = _text(raw.get("REASONDESCRIPTION"))
    record["CODE"] = _text(raw.get("CODE"))
    record["DESCRIPTION"] = _text(raw.get("DESCRIPTION"))
    record["DIAGNOSIS"] = _text(raw.get("DIAGNOSIS"))
    dx_code = _text(raw.get("DIAGNOSIS_CODE"))
    record["DIAGNOSIS_CODE"] = dx_code.upper() if dx_code else None

    ma = _text(raw.get("Id")) or ""
    record["Id"] = ma or str(uuid.uuid4())
    return record, errors


def _is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _fill_from_history(record, history):
    """Bệnh nhân cũ để trống họ tên, giới tính, địa chỉ thì chép từ lượt khám gần nhất có dữ liệu.

    Trả về (bản ghi đã chép, danh sách trường đã chép). Danh sách này được ghi vào nhật ký để
    người dùng xác nhận lại, thay vì để việc chép diễn ra âm thầm.
    """
    copied = []
    if not history:
        return record, copied
    ordered = sorted(history, key=lambda h: to_ts(h.get("START")) or pd.Timestamp.min)
    out = dict(record)
    for field in DEMOGRAPHIC_FIELDS:
        if is_blank(out.get(field)):
            for h in reversed(ordered):
                if not is_blank(h.get(field)):
                    out[field] = h[field]
                    copied.append(field)
                    break
    return out, copied


def _record_from_row(row):
    record = {k: row.get(k) for k in db.RECORD_COLUMNS}
    record["START"] = to_ts(row["START"])
    record["STOP"] = to_ts(row["STOP"])
    record["BIRTHDATE"] = to_ts(row["BIRTHDATE"])
    return record


def _manual_diagnosis(conn, encounter_id):
    """Chẩn đoán nhập tay của lượt khám (không lấy dữ liệu nguồn Synthea)."""
    for c in db.conditions_for_encounter(conn, encounter_id):
        if c.get("source") == "manual":
            return {"DIAGNOSIS": c.get("DESCRIPTION"), "DIAGNOSIS_CODE": c.get("CODE")}
    return {}


def _who(actor):
    """Tên hiển thị ghi vào nhật ký. None chỉ dùng cho tác vụ nội bộ."""
    return "hệ thống" if actor is None else actor.name


def _authorize(actor, perm):
    """Chỉ cho phép thao tác khi actor là người dùng đã xác thực và có quyền."""
    if not isinstance(actor, auth.User) or not actor.can(perm):
        raise EditError("Tài khoản hiện tại không có quyền thực hiện thao tác này")


def score_and_store(conn, model, record, source="manual", actor=None):
    """Chấm điểm bản ghi theo lịch sử hiện có rồi lưu tất cả trong một giao dịch.

    Hàm này giả định đầu vào đã qua validate_input. Nếu vẫn thiếu trường NOT NULL thì báo ValueError
    thay vì để SQLite báo lỗi ràng buộc khi đang ghi.
    """
    _authorize(actor, auth.PERM_NHAP_BAN_GHI)
    missing = [f for f in REQUIRED_AT_SAVE if _is_empty(record.get(f))]
    if missing:
        raise ValueError(f"Thiếu trường bắt buộc trước khi lưu: {', '.join(missing)}")
    if db.encounter_exists(conn, record["Id"]):
        raise db.EncounterExists(record["Id"])
    history = db.history_for(conn, record["PATIENT"], record["START"], record["Id"])
    record, copied = _fill_from_history(record, history)
    result = score_record(record, history, model)
    diagnosis = record.get("DIAGNOSIS")
    with conn:
        db.insert_encounter(conn, record, source)
        db.save_score(conn, record["Id"], result, 0)
        if diagnosis:
            db.insert_conditions(conn, [{
                "PATIENT": record["PATIENT"], "ENCOUNTER": record["Id"],
                "START": record["START"], "STOP": record["STOP"],
                "CODE": record.get("DIAGNOSIS_CODE"), "DESCRIPTION": diagnosis,
            }], source)
        if copied:
            db.add_audit(conn, record["Id"], db.COPIED_ACTION,
                         "Chép từ lượt khám trước, cần xác nhận: " + ", ".join(EMR_LABELS.get(f, f) for f in copied),
                         _who(actor))
        if result["status"] != "bình thường":
            db.ensure_workflow(conn, record["Id"], _who(actor))
    return result


def rescore(conn, model, encounter_id, actor=None):
    """Chấm lại theo mô hình và hồ sơ hiện tại. Cùng phiên bản thì trả về kết quả đã lưu, không tạo bản sao."""
    row = db.get_encounter(conn, encounter_id)
    if row is None:
        raise KeyError(encounter_id)
    rev = row["revision"]
    stored = db.get_score(conn, encounter_id, model["model_version"], rev)
    if stored is not None:
        return stored, False
    record = _record_from_row(row)
    record.update(_manual_diagnosis(conn, encounter_id))
    history = db.history_for(conn, row["PATIENT"], record["START"], encounter_id)
    result = score_record(record, history, model)
    with conn:
        saved, created = db.save_score(conn, encounter_id, result, rev)
        if created:
            db.add_audit(conn, encounter_id, "chấm_lại",
                         f"Chấm với mô hình {model['model_version']}, phiên bản hồ sơ {rev}: {result['status']}",
                         _who(actor))
            if result["status"] != "bình thường":
                db.ensure_workflow(conn, encounter_id, _who(actor))
    return saved, created


def _normalize_edit_value(kind, label, raw):
    """Trả về (giá trị đã chuẩn hóa, lỗi). Lỗi là None nếu hợp lệ."""
    text = _text(raw)
    if kind == "text":
        return text, None
    if kind == "gender":
        if text is not None and text not in GENDERS:
            return None, f"{label}: chỉ nhận M hoặc F"
        return text, None
    if kind == "class":
        if text not in ENCOUNTER_CLASSES:
            return None, f"{label}: loại lượt khám không hợp lệ"
        return text, None
    if kind == "doc":
        value, err = parse_doc(text)
        return (value, None) if err is None else (None, f"{label}: {err}")
    if kind == "date":
        if text is None:
            return None, None
        ts = to_ts_vn(text)
        return (ts, None) if ts is not None else (None, f"{label}: cần định dạng DD/MM/YYYY")
    if kind == "datetime":
        if text is None:
            return None, f"{label}: không được để trống"
        ts = to_ts_vn(text)
        return (ts, None) if ts is not None else (None, f"{label}: cần định dạng DD/MM/YYYY HH:MM")
    if kind == "money":
        if text is None:
            return None, None
        n = to_number(parse_money(text))
        if n is None or n < 0:
            return None, f"{label}: cần là số không âm"
        return n, None
    raise ValueError(f"Loại trường không hợp lệ: {kind}")


def normalize_edit(raw):
    """raw: chuỗi nhập từ giao diện theo tên cột. Trả về (giá trị đã chuẩn hóa, danh sách lỗi)."""
    values, errors = {}, []
    for field, label, kind in EMR_FIELDS:
        if field not in raw:
            continue
        value, err = _normalize_edit_value(kind, label, raw[field])
        if err:
            errors.append(err)
        else:
            values[field] = value
    return values, errors


RESULT_CHOICES = db.RESULTS


def _workflow(conn, encounter_id):
    """Trả về (hồ sơ, quy trình xử lý). Báo lỗi nghiệp vụ nếu không có."""
    row = db.get_encounter(conn, encounter_id)
    if row is None:
        raise EditError("Không tìm thấy lượt khám")
    wf = db.get_workflow(conn, encounter_id)
    if wf is None:
        raise EditError("Lượt khám này không có cảnh báo nên không có quy trình xử lý")
    return row, wf


def _require_state(wf, needed, action):
    if wf["trang_thai"] != needed:
        raise EditError(f"{action} chỉ thực hiện khi lượt khám ở trạng thái '{needed}' "
                        f"(hiện: '{wf['trang_thai']}')")


def start_processing(conn, encounter_id, actor=None):
    """Nhận xử lý cảnh báo: chờ xử lý -> đang xử lý."""
    _authorize(actor, auth.PERM_XU_LY)
    who = _who(actor)
    _, wf = _workflow(conn, encounter_id)
    _require_state(wf, db.PENDING, "Bắt đầu xử lý")
    try:
        db.set_status(conn, encounter_id, db.PROCESSING, None, who)
    except db.TransitionError as e:
        raise EditError(str(e))


def required_errors_after_edit(conn, row, values):
    """Không cho phép XÓA một trường bắt buộc đang có giá trị.

    Bổ sung trường còn thiếu (ví dụ chi phí bị thiếu) thì được phép, vì đó chính là việc cần làm
    khi xử lý cảnh báo. Lỗi chỉ phát sinh khi sau khi lưu, trường bắt buộc bị trống mà trước đó có giá trị.
    Quy tắc này khớp với lúc nhập mới: thông tin bắt buộc không được đưa về rỗng.
    """
    final = {**row, **values}
    required = [("ENCOUNTERCLASS", "Loại lượt khám"), ("START", "Bắt đầu"), ("STOP", "Kết thúc"),
                ("BASE_ENCOUNTER_COST", "Chi phí cơ bản"), ("TOTAL_CLAIM_COST", "Tổng chi phí")]
    others = [h for h in db.patient_encounters(conn, row["PATIENT"]) if h["Id"] != row["Id"]]
    if not others:
        required += [("LAST", "Họ"), ("FIRST", "Tên"), ("GENDER", "Giới tính"), ("BIRTHDATE", "Ngày sinh")]
    errors = []
    for field, label in required:
        if not is_blank(row.get(field)) and is_blank(final.get(field)):
            errors.append(f"{label}: không được xóa thông tin đang có")
    return errors


def update_emr(conn, model, encounter_id, raw, note, actor=None):
    """Cập nhật hồ sơ khi đang xử lý, có lý do. Lưu từng trường đã đổi rồi chấm lại ngay.

    Trạng thái không đổi: vẫn đang xử lý cho tới khi hoàn tất. Trả về danh sách trường đã đổi.
    """
    _authorize(actor, auth.PERM_XU_LY)
    who = _who(actor)
    row, wf = _workflow(conn, encounter_id)
    _require_state(wf, db.PROCESSING, "Cập nhật hồ sơ")
    note = (note or "").strip()
    if not note:
        raise EditError("Cần ghi lý do cập nhật")
    values, errors = normalize_edit(raw)
    if not errors:
        errors = required_errors_after_edit(conn, row, values)
    if errors:
        raise EditError("Dữ liệu cập nhật chưa hợp lệ", errors)
    changed = db.apply_emr_changes(conn, encounter_id, values, note, who)
    if not changed:
        raise EditError("Không có thay đổi nào so với hồ sơ hiện tại")
    rescore(conn, model, encounter_id, actor)
    return changed


def finish_processing(conn, encounter_id, result, note, actor=None):
    """Hoàn tất xử lý: đang xử lý -> đã xử lý, kèm kết luận và ghi chú.

    Kết luận 'Đã cập nhật dữ liệu' chỉ hợp lệ khi có ít nhất một lần cập nhật trong lần xử lý này.
    """
    _authorize(actor, auth.PERM_XU_LY)
    who = _who(actor)
    row, wf = _workflow(conn, encounter_id)
    _require_state(wf, db.PROCESSING, "Hoàn tất xử lý")
    if result not in db.RESULTS:
        raise EditError("Chọn kết luận xử lý")
    note = (note or "").strip()
    if not note:
        raise EditError("Cần ghi chú kết luận")
    if result == db.RESULT_UPDATED and row["revision"] <= wf["rev_bat_dau"]:
        raise EditError("Chưa có cập nhật dữ liệu trong lần xử lý này. Hãy lưu cập nhật trước, "
                        "hoặc chọn kết luận 'Xác nhận cảnh báo, cần xem xét thêm'.")
    try:
        db.set_status(conn, encounter_id, db.DONE, note, who, result=result)
    except db.TransitionError as e:
        raise EditError(str(e))


def reopen_processing(conn, encounter_id, note, actor=None):
    """Mở lại lượt đã xử lý: đã xử lý -> đang xử lý, bắt buộc có lý do."""
    _authorize(actor, auth.PERM_XU_LY)
    who = _who(actor)
    _, wf = _workflow(conn, encounter_id)
    _require_state(wf, db.DONE, "Mở lại xử lý")
    note = (note or "").strip()
    if not note:
        raise EditError("Cần ghi lý do mở lại")
    try:
        db.set_status(conn, encounter_id, db.PROCESSING, note, who)
    except db.TransitionError as e:
        raise EditError(str(e))
