import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import auth, db  # noqa: E402

MIN_PASSWORD_LENGTH = 8


def add_user(args):
    conn = db.connect()
    if db.get_user(conn, args.username):
        raise SystemExit(f"Tên đăng nhập '{args.username}' đã tồn tại")
    password = getpass.getpass("Mật khẩu: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Mật khẩu cần tối thiểu {MIN_PASSWORD_LENGTH} ký tự")
    if getpass.getpass("Nhập lại mật khẩu: ") != password:
        raise SystemExit("Hai lần nhập mật khẩu không khớp")
    db.create_user(conn, args.username, args.name, args.role, args.khoa, auth.hash_password(password))
    print(f"Đã tạo tài khoản {args.username} ({auth.ROLE_LABELS[args.role]})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="Tạo tài khoản mới")
    add.add_argument("--username", required=True)
    add.add_argument("--name", required=True, help="Họ tên hiển thị")
    add.add_argument("--role", required=True, choices=auth.ROLES)
    add.add_argument("--khoa", default="", help="Khoa/phòng công tác")
    add.set_defaults(func=add_user)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
