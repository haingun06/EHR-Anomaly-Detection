import pytest

from anomaly.detector import decide_status, load_model, score_batch, score_record
from anomaly.rules import DEFAULT_RULES_CONFIG
from app import auth, db, service
from app.seed_demo import split_test_records, to_record
from config import MODEL_PATH, PROC_DIR
from pipeline.common import analyze_table, load_table

NAP = auth.User("nap", "nạp dữ liệu", auth.ROLE_PROCESS, "")
KT = auth.User("kiemthu", "kiểm thử", auth.ROLE_PROCESS, "")

needs_artifacts = pytest.mark.skipif(
    not (MODEL_PATH.exists() and (PROC_DIR / "encounters_injected.csv").exists()),
    reason="Chưa chạy pipeline (cần models/anomaly_model.joblib và data/processed)",
)


@needs_artifacts
def test_database_path_matches_pipeline(tmp_path):
    model = load_model()
    test_recs = split_test_records()
    patients = []
    for r in test_recs:
        if r["PATIENT"] not in patients:
            patients.append(r["PATIENT"])
        if len(patients) == 40:
            break
    subset = [r for r in test_recs if r["PATIENT"] in set(patients)]

    analyses = analyze_table(subset, DEFAULT_RULES_CONFIG)
    pipe = score_batch(analyses, model)
    pipe_status = [decide_status(a, m["ml_flag"]) for a, m in zip(analyses, pipe)]

    conn = db.connect(tmp_path / "check.sqlite")
    db_status, db_scores, db_codes = [], [], []
    for r in subset:
        result = service.score_and_store(conn, model, to_record(r), source="seed", actor=NAP)
        db_status.append(result["status"])
        db_scores.append(result["anomaly_score"])
        db_codes.append(sorted(f["code"] for f in result["rule_flags"]))

    assert db_status == pipe_status
    assert db_codes == [sorted(f["code"] for f in a["rule_flags"]) for a in analyses]
    for a, b in zip(db_scores, [m["anomaly_score"] for m in pipe]):
        if b is None:
            assert a is None
        else:
            assert a == pytest.approx(b, rel=1e-9, abs=1e-12)


@needs_artifacts
def test_single_record_api_equals_batch():
    """score_record (đường một bản ghi) phải cho cùng kết quả với score_batch (đường pipeline)."""
    model = load_model()
    sample = split_test_records()[:300]
    analyses = analyze_table(sample, DEFAULT_RULES_CONFIG)
    batch = score_batch(analyses, model)
    history_by_patient = {}
    for r, a, m in zip(sample, analyses, batch):
        history = history_by_patient.setdefault(r["PATIENT"], [])
        single = score_record(to_record(r), [dict(h) for h in history], model)
        assert single["status"] == decide_status(a, m["ml_flag"])
        assert single["anomaly_score"] == m["anomaly_score"] or (
            single["anomaly_score"] is None and m["anomaly_score"] is None)
        history.append(r)


@needs_artifacts
def test_model_file_contents():
    model = load_model()
    for key in ["model_version", "sklearn_version", "feature_names", "groups", "fallback", "rules_config"]:
        assert key in model
    assert model["feature_names"] == ["age_years", "duration_hours", "log_cost", "encounters_30d", "log_days_since_prev"]
    for g, entry in model["groups"].items():
        assert {"scaler", "model", "threshold", "threshold_grid", "reference"} <= set(entry)


@needs_artifacts
def test_rescore_same_version_is_stable_and_new_version_keeps_workflow(tmp_path):
    model = load_model()
    conn = db.connect(tmp_path / "rescore.sqlite")
    target = None
    for r in split_test_records()[:400]:
        service.score_and_store(conn, model, to_record(r), source="seed", actor=NAP)
        if target is None and db.get_workflow(conn, r["Id"]) is not None:
            target = r["Id"]
    assert target is not None, "Không có lượt khám cảnh báo trong 400 bản ghi đầu"

    _, created = service.rescore(conn, model, target)
    assert created is False

    service.start_processing(conn, target, actor=KT)
    newer = dict(model, model_version="v-kiểm-thử")
    _, created = service.rescore(conn, newer, target)
    assert created is True
    assert db.get_workflow(conn, target)["trang_thai"] == "đang xử lý"
    versions = [r[0] for r in conn.execute(
        "SELECT model_version FROM ket_qua_cham_diem WHERE encounter_id=? ORDER BY id", (target,))]
    assert versions[-1] == "v-kiểm-thử" and len(versions) == len(set(versions))


@needs_artifacts
def test_edit_then_rescore_creates_new_version_only_when_record_changed(tmp_path):
    """Sửa hồ sơ rồi chấm lại với mô hình thật: tạo kết quả mới đúng một lần, không tạo bản sao khi không đổi."""
    from app import service as svc
    model = load_model()
    conn = db.connect(tmp_path / "edit.sqlite")
    target = None
    for r in split_test_records()[:400]:
        svc.score_and_store(conn, model, to_record(r), source="seed", actor=NAP)
        if target is None and db.get_workflow(conn, r["Id"]) is not None:
            target = r["Id"]
    assert target is not None

    svc.start_processing(conn, target, actor=KT)
    row = db.get_encounter(conn, target)
    svc.update_emr(conn, model, target, {"CITY": "Thành phố kiểm thử"}, "kiểm thử chỉnh sửa", actor=KT)

    new_rev = row["revision"] + 1
    assert db.get_encounter(conn, target)["revision"] == new_rev
    assert db.get_score(conn, target, model["model_version"], new_rev) is not None
    _, created_again = svc.rescore(conn, model, target)
    assert created_again is False
    scores = conn.execute("SELECT emr_revision FROM ket_qua_cham_diem WHERE encounter_id=? ORDER BY id",
                          (target,)).fetchall()
    assert [s[0] for s in scores][-1] == new_rev
    assert any(a["hanh_dong"] == "chấm_lại" for a in db.audit_log(conn, target))


@needs_artifacts
def test_seed_loads_conditions_once_and_links_to_test_encounters(tmp_path):
    from app import seed_demo
    from app import service as svc
    model = load_model()
    conn = db.connect(tmp_path / "seed.sqlite")
    test_pats = seed_demo.split_test_patients()
    for r in split_test_records()[:50]:
        svc.score_and_store(conn, model, seed_demo.to_record(r), source="seed", actor=NAP)
    rows = seed_demo.load_conditions(test_pats, skip_patients=db.patients_with_conditions(conn))
    with conn:
        db.insert_conditions(conn, rows, source="seed")
    first = db.count_conditions(conn)
    assert first > 0
    again = seed_demo.load_conditions(test_pats, skip_patients=db.patients_with_conditions(conn))
    assert again == []
    assert db.count_conditions(conn) == first
