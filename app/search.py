import unicodedata


def normalize(text):
    if text is None:
        return ""
    s = unicodedata.normalize("NFD", str(text))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("đ", "d")
    return " ".join(s.split())


def haystack(item):
    parts = [item.get(k) for k in ("Id", "PATIENT", "FIRST", "LAST")]
    return normalize(" ".join(str(p) for p in parts if p not in (None, "")))


def _matches(token, words):
    return any(w.startswith(token) for w in words)


def filter_items(items, keyword):
    """Mỗi từ trong từ khóa phải là đầu của một từ trong mã lượt khám, mã bệnh nhân hoặc họ tên."""
    tokens = normalize(keyword).split()
    if not tokens:
        return list(items)
    return [it for it in items if all(_matches(t, haystack(it).split()) for t in tokens)]