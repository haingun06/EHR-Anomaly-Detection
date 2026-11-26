
from anomaly.detector import analyze_record, decide_status
from anomaly.rules import DEFAULT_RULES_CONFIG as CFG


def rec(**kw):
    base = {"Id": "L1", "PATIENT": "P1", "ENCOUNTERCLASS": "ambulatory", "CODE": "410620009",
            "START": "2020-01-10 08:00", "STOP": "2020-01-10 08:30", "BIRTHDATE": "1990-01-10",
            "BASE_ENCOUNTER_COST": "100", "TOTAL_CLAIM_COST": "250"}
    base.update(kw)
    return base


def codes(a):
    return {f["code"] for f in a["rule_flags"]}


def test_clean_record_has_no_flags_and_is_normal():
    a = analyze_record(rec(), [], CFG)
    assert a["rule_flags"] == []
    assert decide_status(a, ml_flag=False) == "bình thường"


def test_missing_required_field():
    a = analyze_record(rec(TOTAL_CLAIM_COST=""), [], CFG)
    assert "missing" in codes(a)
    assert "TOTAL_CLAIM_COST" in a["missing_fields"]
    assert decide_status(a, False) == "thiếu thông tin"


def test_new_patient_without_birthdate_is_missing():
    a = analyze_record(rec(BIRTHDATE=""), [], CFG)
    assert "BIRTHDATE" in a["missing_fields"]


def test_existing_patient_can_omit_birthdate():
    history = [rec(Id="L0", START="2019-01-01 08:00", STOP="2019-01-01 08:30")]
    a = analyze_record(rec(BIRTHDATE="", START="2020-01-10 08:00"), history, CFG)
    assert "BIRTHDATE" not in a["missing_fields"]
    assert "birthdate_mismatch" not in codes(a)


def test_stop_before_start_is_date_logic_error():
    a = analyze_record(rec(STOP="2020-01-09 08:00"), [], CFG)
    assert codes(a) == {"date_logic"}
    assert decide_status(a, False) == "bất thường"


def test_age_out_of_range_negative_and_over_120():
    neg = analyze_record(rec(BIRTHDATE="2030-01-01"), [], CFG)
    assert "age_range" in codes(neg)
    old = analyze_record(rec(BIRTHDATE="1880-01-01"), [], CFG)
    assert "age_range" in codes(old)


def test_duplicate_of_history_row():
    history = [rec(Id="L0")]
    a = analyze_record(rec(Id="L0-dup"), history, CFG)
    assert "duplicate" in codes(a)
    assert decide_status(a, False) == "trùng lặp"


def test_same_time_but_different_cost_is_not_duplicate():
    history = [rec(Id="L0", TOTAL_CLAIM_COST="999")]
    a = analyze_record(rec(Id="L1"), history, CFG)
    assert "duplicate" not in codes(a)


def test_birthdate_mismatch_against_history_majority():
    history = [rec(Id="L0", START="2019-01-01 08:00", STOP="2019-01-01 08:30"),
               rec(Id="L1", START="2019-06-01 08:00", STOP="2019-06-01 08:30")]
    a = analyze_record(rec(START="2020-01-10 08:00", BIRTHDATE="1991-01-10"), history, CFG)
    assert "birthdate_mismatch" in codes(a)
    assert decide_status(a, False) == "bất thường"


def test_ml_flag_alone_gives_abnormal_status():
    a = analyze_record(rec(), [], CFG)
    assert decide_status(a, ml_flag=True) == "bất thường"
