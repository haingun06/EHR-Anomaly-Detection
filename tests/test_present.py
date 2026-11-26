from app import present


def test_money_uses_dot_thousands_and_handles_blank():
    assert present.fmt_money("1250000") == "1.250.000 VND"
    assert present.fmt_money(833.9) == "834 VND"
    assert present.fmt_money(None) == present.NOT_AVAILABLE
    assert present.fmt_money("") == present.NOT_AVAILABLE
    assert present.fmt_money(float("nan")) == present.NOT_AVAILABLE


def test_dates_accept_synthea_and_manual_formats():
    assert present.fmt_date("2019-02-17T05:07:38Z") == "17/02/2019"
    assert present.fmt_date("2019-02-17") == "17/02/2019"
    assert present.fmt_datetime("2021-06-01T10:00:00") == "01/06/2021 10:00"
    assert present.fmt_date("không phải ngày") == present.NOT_AVAILABLE


def test_hours_between_start_and_stop():
    assert present.fmt_hours("2020-01-10T08:00:00", "2020-01-10T09:30:00") == "1.5 giờ"
    assert present.fmt_hours("2020-01-10T08:00:00", None) == present.NOT_AVAILABLE


def test_full_name_and_address_skip_blanks():
    assert present.full_name("Langosh790", "Damon455") == "Langosh790 Damon455"
    assert present.full_name(None, "Damon455") == "Damon455"
    assert present.full_name("", None) == present.NOT_AVAILABLE
    assert present.address_line("620 Lynch Tunnel", "Springfield", "Massachusetts", None) == \
        "620 Lynch Tunnel, Springfield, Massachusetts"
    assert present.address_line(None, None, None, None) == present.NOT_AVAILABLE


def test_gender_labels():
    assert present.gender_label("M") == "Nam"
    assert present.gender_label("F") == "Nữ"
    assert present.gender_label(None) == present.NOT_AVAILABLE


def test_edit_values_keep_seconds_so_saving_does_not_change_data():
    assert present.edit_datetime("2019-02-17T05:07:38Z") == "2019-02-17 05:07:38"
    assert present.edit_date("1990-01-10T00:00:00") == "1990-01-10"
    assert present.edit_money(833.9) == "833.9"
    assert present.edit_money(1000.0) == "1000"
    assert present.edit_money(None) == ""


def test_html_is_escaped_in_rows_and_lists():
    assert "&lt;script&gt;" in present.row("Ghi chú", "<script>x</script>")
    assert "&lt;b&gt;" in present.bullet_list_html(["<b>đậm</b>"])


def test_condition_line_falls_back_to_code():
    assert present.condition_line({"START": "2013-06-24", "DESCRIPTION": "Viêm phế quản cấp"}) == \
        "24/06/2013 — Viêm phế quản cấp"
    assert present.condition_line({"START": None, "CODE": "123"}) == "123"


def _latest(status, rule_flags=(), reasons=()):
    return {"status": status, "rule_flags": list(rule_flags), "reasons": list(reasons)}


def test_clean_only_when_status_is_normal():
    assert present.is_clean(_latest("bình thường"))
    assert not present.is_clean(_latest("bất thường"))   # mô hình gắn cờ, không luật, không đặc trưng
    assert not present.is_clean(None)


def test_model_only_flag_is_detected_and_not_clean():
    latest = _latest("bất thường")
    assert not present.is_clean(latest)
    assert present.model_only_flag(latest)


def test_rule_or_reason_flag_is_not_model_only():
    assert not present.model_only_flag(_latest("bất thường", rule_flags=[{"code": "date_logic", "message": "x"}]))
    assert not present.model_only_flag(_latest("bất thường", reasons=["Thời lượng = 9,00 giờ"]))
