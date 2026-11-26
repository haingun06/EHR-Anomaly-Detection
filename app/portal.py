import csv
import io
import json
from datetime import datetime

from anomaly.features import to_number, to_ts
from anomaly.rules import is_blank
from config import PORTAL_PROFILES_PATH


def load_profiles(path=PORTAL_PROFILES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["profiles"]


def get_profile(name, path=PORTAL_PROFILES_PATH):
    profiles = load_profiles(path)
    if name not in profiles:
        raise KeyError(f"Không có hồ sơ cổng '{name}'. Các hồ sơ hiện có: {sorted(profiles)}")
    return profiles[name]


def _fmt_date(value, profile):
    ts = to_ts(value) if not is_blank(value) else None
    return "" if ts is None else ts.strftime(profile["dinh_dang_ngay"])


def _fmt_datetime(value, profile):
    ts = to_ts(value) if not is_blank(value) else None
    if ts is None:
        return ""
    return f"{ts.strftime(profile['dinh_dang_ngay'])} {ts.strftime(profile['dinh_dang_gio'])}"


def build_rows(rows, profile):
    """Chuyển các dòng lượt khám sang tên cột và định dạng của cổng.

    rows: danh sách dict lấy từ bảng luot_kham kèm cột status (kết quả chấm điểm mới nhất).
    """
    if profile["loai_luot_kham"]:
        rows = [r for r in rows if r.get("ENCOUNTERCLASS") in profile["loai_luot_kham"]]
    out = []
    for r in rows:
        item = {}
        for field, target in profile["anh_xa"].items():
            value = r.get(field)
            if field == "Id":
                item[target] = value
                continue
            if field in profile["truong_ngay"]:
                value = _fmt_datetime(value, profile) if field in ("START", "STOP") else _fmt_date(value, profile)
            elif field in profile["truong_so"]:
                n = to_number(value)
                value = "" if n is None else n
            item[target] = "" if is_blank(value) else value
        out.append(item)
    return out


def check_rows(rows, profile):
    """Trả về danh sách lỗi: mỗi lỗi là dict {Id, truong, loi}. Danh sách rỗng nghĩa là đạt."""
    errors = []
    for r in rows:
        eid = r.get("Id")
        status = r.get("status")
        if status != "bình thường":
            errors.append({"Id": eid, "truong": "trạng thái", "loi": f"Hồ sơ đang ở trạng thái '{status}', chưa đạt để gửi"})
        for field in profile["truong_bat_buoc"]:
            if is_blank(r.get(field)):
                errors.append({"Id": eid, "truong": field, "loi": "Thiếu trường bắt buộc của cổng"})
        for field in profile["truong_so"]:
            if not is_blank(r.get(field)) and to_number(r.get(field)) is None:
                errors.append({"Id": eid, "truong": field, "loi": "Không phải số"})
        for field in profile["truong_ngay"]:
            if not is_blank(r.get(field)) and to_ts(r.get(field)) is None:
                errors.append({"Id": eid, "truong": field, "loi": "Ngày giờ không hợp lệ"})
        start, stop = to_ts(r.get("START")), to_ts(r.get("STOP"))
        if start is not None and stop is not None and stop < start:
            errors.append({"Id": eid, "truong": "STOP", "loi": "Kết thúc trước bắt đầu"})
    return errors


def to_csv_text(rows, profile):
    """Xuất CSV theo tên cột của cổng (không gồm cột nội bộ bắt đầu bằng _)."""
    if not rows:
        return ""
    cols = [c for c in rows[0].keys() if not c.startswith("_")]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def prepare(conn, profile_name, path=PORTAL_PROFILES_PATH):
    from app import db
    profile = get_profile(profile_name, path)
    sql = """
    SELECT l.*, s.status
    FROM luot_kham l
    JOIN ket_qua_cham_diem s ON s.id = (SELECT MAX(k.id) FROM ket_qua_cham_diem k WHERE k.encounter_id = l.Id)
    ORDER BY l.START, l.Id
    """
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    if profile["loai_luot_kham"]:
        rows = [r for r in rows if r.get("ENCOUNTERCLASS") in profile["loai_luot_kham"]]
    errors = check_rows(rows, profile)
    return profile, build_rows(rows, profile), errors
