from app import db
from app.search import filter_items  # noqa: F401  (giữ để nhất quán với các module khác)


def _record(i, start, cls="ambulatory"):
    return {"Id": i, "PATIENT": f"P-{i}", "ENCOUNTERCLASS": cls, "CODE": "1",
            "START": start, "STOP": start.replace("08:", "09:"), "DESCRIPTION": None,
            "BASE_ENCOUNTER_COST": 10.0, "TOTAL_CLAIM_COST": 20.0, "REASONDESCRIPTION": None,
            "BIRTHDATE": "1990-01-10", "FIRST": "An", "LAST": "Nguyễn", "GENDER": "F"}


def _result():
    return {"model_version": "vtest", "status": "bất thường",
            "rule_flags": [{"code": "date_logic", "message": "x"}],
            "anomaly_score": None, "threshold": 0.5, "group": "ambulatory", "model_used": "group",
            "reasons": [], "features": {"age_years": 30.0, "duration_hours": float("nan")}}


def _add(conn, i, start, state):
    with conn:
        db.insert_encounter(conn, _record(i, start), "manual")
        db.save_score(conn, i, _result())
        db.ensure_workflow(conn, i, "tester")
    if state != db.PENDING:
        with conn:
            db.set_status(conn, i, db.PROCESSING, None, "tester")
    if state == db.DONE:
        with conn:
            db.set_status(conn, i, db.DONE, "xong", "tester", result=db.RESULT_CONFIRMED)


def test_default_sort_is_newest_encounter_first(tmp_path):
    conn = db.connect(tmp_path / "s.sqlite")
    _add(conn, "A", "2021-01-01 08:00:00", db.PENDING)
    _add(conn, "B", "2023-05-01 08:00:00", db.DONE)
    _add(conn, "C", "2022-03-01 08:00:00", db.PENDING)
    ids = [r["Id"] for r in db.list_items(conn)]
    assert ids == ["B", "C", "A"]
    conn.close()


def test_status_sort_puts_pending_first_then_newest(tmp_path):
    conn = db.connect(tmp_path / "s2.sqlite")
    _add(conn, "A", "2021-01-01 08:00:00", db.PENDING)
    _add(conn, "B", "2023-05-01 08:00:00", db.DONE)
    _add(conn, "C", "2022-03-01 08:00:00", db.PENDING)
    ids = [r["Id"] for r in db.list_items(conn, sort="trang_thai")]
    assert ids == ["C", "A", "B"]
    conn.close()