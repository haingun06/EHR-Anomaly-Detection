import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db, portal  # noqa: E402
from config import DB_PATH  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    conn = db.connect(DB_PATH)
    profile, rows, errors = portal.prepare(conn, args.profile)
    out = Path(args.out)
    if errors:
        err_path = out.with_name(out.stem + "_loi.csv")
        with open(err_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["Id", "truong", "loi"])
            w.writeheader()
            w.writerows(errors)
        print(f"Chưa đạt: {len(errors)} lỗi trên {len({e['Id'] for e in errors})} hồ sơ. Xem {err_path}")
        return 1
    out.write_text(portal.to_csv_text(rows, profile), encoding="utf-8-sig")
    print(f"Đạt: {len(rows)} hồ sơ. Đã ghi {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
