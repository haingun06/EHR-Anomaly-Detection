from app.search import filter_items, normalize

ITEMS = [
    {"Id": "L100", "PATIENT": "P-001", "FIRST": "An", "LAST": "Nguyễn Văn"},
    {"Id": "L200", "PATIENT": "P-002", "FIRST": "Bình", "LAST": "Trần Thị"},
    {"Id": "L300", "PATIENT": "P-003", "FIRST": "Đào", "LAST": "Lê"},
]


def ids(rows):
    return [r["Id"] for r in rows]


def test_normalize_removes_accents_and_case():
    assert normalize("Nguyễn Văn ÁN") == "nguyen van an"
    assert normalize("Đào") == "dao"
    assert normalize(None) == ""


def test_empty_keyword_returns_all():
    assert ids(filter_items(ITEMS, "   ")) == ["L100", "L200", "L300"]


def test_search_by_name_without_accents():
    assert ids(filter_items(ITEMS, "nguyen")) == ["L100"]
    assert ids(filter_items(ITEMS, "TRAN THI")) == ["L200"]


def test_search_by_patient_code_and_encounter_code():
    assert ids(filter_items(ITEMS, "P-002")) == ["L200"]
    assert ids(filter_items(ITEMS, "l30")) == ["L300"]


def test_multiple_tokens_must_all_match():
    assert ids(filter_items(ITEMS, "an p-001")) == ["L100"]
    assert ids(filter_items(ITEMS, "an p-002")) == []


def test_no_match_returns_empty():
    assert filter_items(ITEMS, "không có") == []