import html
import math

from anomaly.features import to_ts
from anomaly.rules import INFO_RULE_CODES, is_blank

CLASS_LABELS = {
    "wellness": "Khám sức khỏe định kỳ",
    "ambulatory": "Khám ngoại trú",
    "outpatient": "Khám ngoại trú chuyên khoa",
    "urgentcare": "Khám cấp cứu tại chỗ",
    "emergency": "Cấp cứu",
    "inpatient": "Nội trú",
}
GENDER_LABELS = {"M": "Nam", "F": "Nữ"}
SOURCE_LABELS = {"seed": "Dữ liệu demo (Synthea)", "manual": "Nhập tay trên giao diện"}
NOT_AVAILABLE = "—"


def esc(value):
    return html.escape("" if value is None else str(value))


def value_or_dash(value):
    return NOT_AVAILABLE if is_blank(value) else str(value).strip()


def fmt_money(value):
    if is_blank(value):
        return NOT_AVAILABLE
    try:
        x = float(value)
    except (TypeError, ValueError):
        return NOT_AVAILABLE
    if math.isnan(x):
        return NOT_AVAILABLE
    return f"{x:,.0f}".replace(",", ".") + " VND"


def fmt_date(value):
    ts = to_ts(value) if not is_blank(value) else None
    return NOT_AVAILABLE if ts is None else ts.strftime("%d/%m/%Y")


def fmt_datetime(value):
    ts = to_ts(value) if not is_blank(value) else None
    return NOT_AVAILABLE if ts is None else ts.strftime("%d/%m/%Y %H:%M")


def fmt_hours(start, stop):
    s, e = to_ts(start), to_ts(stop)
    if s is None or e is None:
        return NOT_AVAILABLE
    hours = (e - s).total_seconds() / 3600
    return f"{hours:.1f} giờ"


def full_name(last, first):
    parts = [str(p).strip() for p in (last, first) if not is_blank(p)]
    return " ".join(parts) if parts else NOT_AVAILABLE


def address_line(address, city, state, zip_code):
    parts = [str(p).strip() for p in (address, city, state, zip_code) if not is_blank(p)]
    return ", ".join(parts) if parts else NOT_AVAILABLE


def gender_label(code):
    return GENDER_LABELS.get(code, NOT_AVAILABLE)


def edit_datetime(value):
    """Dạng hiển thị trong ô chỉnh sửa, có giây để không làm đổi giá trị gốc khi lưu."""
    ts = to_ts(value) if not is_blank(value) else None
    return "" if ts is None else ts.strftime("%Y-%m-%d %H:%M:%S")


def edit_date(value):
    ts = to_ts(value) if not is_blank(value) else None
    return "" if ts is None else ts.strftime("%Y-%m-%d")


def edit_money(value):
    if is_blank(value):
        return ""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{x:.2f}".rstrip("0").rstrip(".") if not math.isnan(x) else ""


def row(label, text):
    """Một dòng bảng thông tin. text là văn bản thuần, sẽ được escape."""
    return f"<tr><td>{esc(label)}</td><td>{esc(text)}</td></tr>"


def row_html(label, snippet):
    """Một dòng bảng thông tin, snippet là HTML đã được escape sẵn."""
    return f"<tr><td>{esc(label)}</td><td>{snippet}</td></tr>"


def bullet_list_html(items):
    """Danh sách văn bản thuần, mỗi mục một dòng và đã escape."""
    if not items:
        return None
    return "".join(f"<div>{esc(i)}</div>" for i in items)


def condition_line(cond):
    when = fmt_date(cond.get("START"))
    text = cond.get("DESCRIPTION") or cond.get("CODE") or NOT_AVAILABLE
    return f"{when} — {text}" if when != NOT_AVAILABLE else text


def is_clean(latest):
    """Lượt khám không có lỗi bất thường khi kết quả chấm điểm là 'bình thường'.

    Phải dựa vào status, không dựa vào rule_flags và reasons: mô hình có thể gắn cờ
    bất thường theo tổ hợp đặc trưng dù từng đặc trưng riêng lẻ vẫn trong khoảng tham chiếu.
    """
    return latest is not None and latest["status"] == "bình thường"


def hard_flags(latest):
    """Các luật bị vi phạm, không gồm cờ thông tin."""
    if latest is None:
        return []
    return [f for f in latest["rule_flags"] if f["code"] not in INFO_RULE_CODES]


def info_flags(latest):
    """Cờ thông tin cần người dùng xác nhận (không làm đổi trạng thái)."""
    if latest is None:
        return []
    return [f for f in latest["rule_flags"] if f["code"] in INFO_RULE_CODES]


def model_only_flag(latest):
    """True khi mô hình gắn cờ nhưng không có luật nào vi phạm và không đặc trưng nào ngoài khoảng."""
    return latest is not None and not hard_flags(latest) and not latest["reasons"] \
        and latest["status"] == "bất thường"


MODEL_ONLY_NOTE = ("Mô hình đánh giá tổ hợp các đặc trưng của lượt khám là bất thường, "
                   "dù từng đặc trưng riêng lẻ vẫn nằm trong khoảng tham chiếu của nhóm.")
