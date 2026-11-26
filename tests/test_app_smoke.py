import pytest
from streamlit.testing.v1 import AppTest

from app import auth
from config import MODEL_PATH, ROOT

APP_PATH = str(ROOT / "app" / "streamlit_app.py")

pytestmark = pytest.mark.skipif(not MODEL_PATH.exists(), reason="Chưa có file mô hình")


ADMIN = auth.User("xuly", "BS B", auth.ROLE_PROCESS, "Khoa Giám định")


def _login(at, user=ADMIN):
    """Đặt người dùng đã đăng nhập trước lần chạy đầu, bỏ qua màn hình đăng nhập."""
    at.session_state["user"] = user
    return at


def _reset(monkeypatch, tmp_path, name):
    import streamlit as st

    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    st.cache_resource.clear()
    return tmp_path / name


def _field(at, prefix):
    matches = [t for t in at.text_input if t.label.startswith(prefix)]
    assert matches, f"Không thấy ô nhập: {prefix}"
    return matches[0]


def _select(at, prefix):
    matches = [s for s in at.selectbox if s.label.startswith(prefix)]
    assert matches, f"Không thấy ô chọn: {prefix}"
    return matches[0]


def _messages(at):
    return [m.value for m in list(at.success) + list(at.error) + list(at.warning) + list(at.markdown)]


def _submit(at):
    next(b for b in at.button if b.label.startswith("✓")).click().run()


def _button(at, key):
    return next(b for b in at.button if b.key == key)


def _set_datetime(at, label, value):
    prefix = {"bắt đầu": "f_start", "kết thúc": "f_stop"}[label]
    day, hour = value.split()
    next(t for t in at.text_input if t.key == f"{prefix}_date").set_value(day)
    next(t for t in at.text_input if t.key == f"{prefix}_time").set_value(hour)


def _fill_new_patient(at, patient, enc, start, stop, total="250", base="100"):
    _field(at, "Mã bệnh nhân").set_value(patient)
    _field(at, "Mã lượt khám").set_value(enc)
    _field(at, "Họ").set_value("Nguyễn")
    _field(at, "Tên").set_value("An")
    _select(at, "Giới tính").set_value("F")
    next(t for t in at.text_input if t.key == "f_birth").set_value("1980-05-20")
    _set_datetime(at, "bắt đầu", start)
    _set_datetime(at, "kết thúc", stop)
    _field(at, "Chi phí cơ bản").set_value(base)
    _field(at, "Tổng chi phí").set_value(total)


def test_entry_form_scores_and_flags_logic_error(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    _reset(monkeypatch, tmp_path, "ui.sqlite")

    at = _login(AppTest.from_file(APP_PATH, default_timeout=60))
    at.run()
    assert not at.exception
    _fill_new_patient(at, "PAT-NEW-1", "ENC-UI-1", "2021-06-01 10:00", "2021-06-01 09:00")  # STOP trước START
    _submit(at)

    assert not at.exception
    messages = _messages(at)
    assert any("Đã lưu lượt khám ENC-UI-1" in m for m in messages)
    assert any("Ngày kết thúc trước ngày bắt đầu" in m for m in messages)


def test_entry_form_requires_date_and_time(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    _reset(monkeypatch, tmp_path, "ui2.sqlite")

    at = _login(AppTest.from_file(APP_PATH, default_timeout=60))
    at.run()
    _field(at, "Mã bệnh nhân").set_value("PAT-X")
    next(t for t in at.text_input if t.key == "f_start_date").set_value("2021-06-01")
    _set_datetime(at, "kết thúc", "2021-06-01 09:00")
    _field(at, "Tổng chi phí").set_value("abc")
    _field(at, "Chi phí cơ bản").set_value("10")
    _submit(at)

    assert not at.exception
    errors = [e.value for e in at.error]
    assert any("chọn ngày và giờ bắt đầu" in e for e in errors)
    assert any("BIRTHDATE" in e for e in errors)     # bệnh nhân mới bắt buộc có ngày sinh
    assert any("LAST" in e for e in errors)          # và có họ, tên, giới tính
    assert any("TOTAL_CLAIM_COST" in e for e in errors)


def test_status_filter_on_list_page(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    _reset(monkeypatch, tmp_path, "ui-status.sqlite")

    at = _login(AppTest.from_file(APP_PATH, default_timeout=60))
    at.run()
    _fill_new_patient(at, "PAT-ST-1", "ENC-ST-1", "2021-06-01 10:00", "2021-06-01 09:00")  # cảnh báo logic
    _submit(at)

    at.session_state["page"] = "Danh sách cảnh báo"
    at.run()
    assert any(b.key == "view_ENC-ST-1" for b in at.button)                    # mặc định: tất cả
    next(s for s in at.selectbox if s.key == "f_status").set_value("đã xử lý").run()
    assert not any(b.key == "view_ENC-ST-1" for b in at.button)
    next(s for s in at.selectbox if s.key == "f_status").set_value("chờ xử lý").run()
    assert any(b.key == "view_ENC-ST-1" for b in at.button)


def test_full_processing_flow_start_update_finish_reopen(tmp_path, monkeypatch):
    """Nhập bản ghi lỗi -> bắt đầu xử lý -> cập nhật hồ sơ -> hoàn tất -> mở lại."""
    from streamlit.testing.v1 import AppTest

    from app import db
    db_file = _reset(monkeypatch, tmp_path, "ui-flow.sqlite")
    enc = "ENC-FLOW-1"

    at = _login(AppTest.from_file(APP_PATH, default_timeout=60))
    at.run()
    _fill_new_patient(at, "PAT-FLOW-1", enc, "2021-06-01 10:00", "2021-06-01 09:00")
    _submit(at)
    assert not at.exception
    assert any(f"Đã lưu lượt khám {enc}" in m for m in _messages(at))

    # 1. Nhận xử lý: chờ xử lý -> đang xử lý
    _button(at, f"start_{enc}").click().run()
    assert not at.exception
    assert any("Đã chuyển sang đang xử lý" in m for m in _messages(at))

    # 2. Cập nhật giờ kết thúc cho đúng, có lý do. Trạng thái vẫn là đang xử lý.
    next(t for t in at.text_input if t.key == f"e_{enc}_0_STOP").set_value("2021-06-01 11:00:00")
    next(t for t in at.text_area if t.key == f"enote_{enc}_0").set_value("Đối chiếu phiếu khám giấy")
    _button(at, f"save_{enc}_0").click().run()
    assert not at.exception
    assert any("Đã lưu 1 trường" in m for m in _messages(at))

    # 3. Hoàn tất với kết luận đã cập nhật dữ liệu
    next(r for r in at.radio if r.key == f"res_{enc}").set_value("Đã cập nhật dữ liệu")
    next(t for t in at.text_area if t.key == f"fnote_{enc}").set_value("Đã sửa theo phiếu giấy")
    _button(at, f"finish_{enc}").click().run()
    assert not at.exception
    assert any("Đã hoàn tất xử lý" in m for m in _messages(at))
    assert not any(b.key == f"save_{enc}_1" for b in at.button)    # đã xử lý: không còn form cập nhật

    conn = db.connect(db_file)
    wf = db.get_workflow(conn, enc)
    assert wf["trang_thai"] == "đã xử lý"
    assert wf["ket_qua"] == "Đã cập nhật dữ liệu" and wf["nguoi_hoan_tat"]
    assert db.get_encounter(conn, enc)["revision"] == 1
    assert [r["truong"] for r in db.edit_log(conn, enc)] == ["STOP"]
    assert any(r["hanh_dong"] == "chấm_lại" for r in db.audit_log(conn, enc))   # tự chấm lại sau khi sửa
    assert db.access_log(conn, enc)                                              # lượt xem được ghi lại
    conn.close()

    # 4. Mở lại: cần lý do, rồi quay về đang xử lý
    next(t for t in at.text_area if t.key == f"reopen_note_{enc}").set_value("Cần kiểm tra thêm")
    _button(at, f"reopen_{enc}").click().run()
    assert not at.exception
    assert any("Đã mở lại xử lý" in m for m in _messages(at))
    conn = db.connect(db_file)
    assert db.get_workflow(conn, enc)["trang_thai"] == "đang xử lý"
    conn.close()


def test_confirm_warning_outcome_without_editing(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from app import db
    db_file = _reset(monkeypatch, tmp_path, "ui-confirm.sqlite")
    enc = "ENC-CONF-1"

    at = _login(AppTest.from_file(APP_PATH, default_timeout=60))
    at.run()
    _fill_new_patient(at, "PAT-CONF-1", enc, "2021-06-01 10:00", "2021-06-01 09:00")
    _submit(at)
    _button(at, f"start_{enc}").click().run()

    next(r for r in at.radio if r.key == f"res_{enc}").set_value("Xác nhận cảnh báo, cần xem xét thêm")
    next(t for t in at.text_area if t.key == f"fnote_{enc}").set_value("Chuyển bác sĩ khoa khác xem")
    _button(at, f"finish_{enc}").click().run()
    assert not at.exception
    assert any("Đã hoàn tất xử lý" in m for m in _messages(at))

    conn = db.connect(db_file)
    assert db.get_workflow(conn, enc)["ket_qua"] == "Xác nhận cảnh báo, cần xem xét thêm"
    conn.close()


def test_update_only_outcome_is_refused_without_saved_change(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    _reset(monkeypatch, tmp_path, "ui-refuse.sqlite")
    enc = "ENC-REF-1"

    at = _login(AppTest.from_file(APP_PATH, default_timeout=60))
    at.run()
    _fill_new_patient(at, "PAT-REF-1", enc, "2021-06-01 10:00", "2021-06-01 09:00")
    _submit(at)
    _button(at, f"start_{enc}").click().run()

    next(r for r in at.radio if r.key == f"res_{enc}").set_value("Đã cập nhật dữ liệu")
    next(t for t in at.text_area if t.key == f"fnote_{enc}").set_value("không sửa gì")
    _button(at, f"finish_{enc}").click().run()
    assert not at.exception
    assert any("Chưa có cập nhật dữ liệu" in e.value for e in at.error)


def test_login_gate_blocks_until_correct_password(tmp_path, monkeypatch):
    from app import db
    path = _reset(monkeypatch, tmp_path, "gate.sqlite")
    conn = db.connect(path)
    db.create_user(conn, "nhapmoi", "Điều dưỡng A", auth.ROLE_ENTRY, "Khoa Khám", auth.hash_password("matkhau123"))
    conn.close()

    at = AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    assert [t.key for t in at.text_input if t.key == "login_user"]
    assert not any(b.key == "nav_0" for b in at.button)

    at.text_input(key="login_user").set_value("nhapmoi")
    at.text_input(key="login_pass").set_value("sai")
    next(b for b in at.button if b.label == "Đăng nhập").click().run()
    assert any("Sai tên đăng nhập" in e.value for e in at.error)

    at.text_input(key="login_pass").set_value("matkhau123")
    next(b for b in at.button if b.label == "Đăng nhập").click().run()
    assert at.session_state["user"].username == "nhapmoi"
    assert "Đăng xuất" in [b.label for b in at.button]


def test_entry_role_sees_only_entry_pages(tmp_path, monkeypatch):
    _reset(monkeypatch, tmp_path, "nav.sqlite")
    nhap = auth.User("nhapmoi", "Điều dưỡng A", auth.ROLE_ENTRY, "Khoa Khám")
    at = _login(AppTest.from_file(APP_PATH, default_timeout=60), nhap)
    at.run()
    labels = [b.label for b in at.button]
    assert "Danh sách cảnh báo" not in labels
    assert "Nhật ký" not in labels
    assert "Mô hình và dữ liệu" not in labels
    assert "Đăng xuất" in labels
