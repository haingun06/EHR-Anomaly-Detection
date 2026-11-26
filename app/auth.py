import hashlib
import hmac
import secrets
from dataclasses import dataclass

ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"

ROLE_ENTRY = "nhap_lieu"
ROLE_PROCESS = "xu_ly"
ROLES = [ROLE_ENTRY, ROLE_PROCESS]

ROLE_LABELS = {
    ROLE_ENTRY: "Người nhập liệu",
    ROLE_PROCESS: "Nhân viên kiểm tra và xử lý cảnh báo",
}

PERM_NHAP_BAN_GHI = "nhap_ban_ghi"
PERM_XEM_DANH_SACH = "xem_danh_sach"
PERM_XU_LY = "xu_ly_canh_bao"
PERM_XEM_NHAT_KY = "xem_nhat_ky"
PERM_QUAN_LY_MO_HINH = "quan_ly_mo_hinh"

PERMISSIONS = {
    PERM_NHAP_BAN_GHI: {ROLE_ENTRY, ROLE_PROCESS},
    PERM_XEM_DANH_SACH: {ROLE_PROCESS},
    PERM_XU_LY: {ROLE_PROCESS},
    PERM_XEM_NHAT_KY: {ROLE_PROCESS},
    PERM_QUAN_LY_MO_HINH: {ROLE_PROCESS},
}

@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: str
    khoa: str = ""

    def can(self, perm):
        return self.role in PERMISSIONS.get(perm, set())

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)


# Người dùng nội bộ cho các tác vụ nạp dữ liệu, không đăng nhập qua giao diện.
SYSTEM = User("system", "hệ thống", ROLE_ENTRY, "")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{_ALGO}${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        algo, iters, salt_hex, digest_hex = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algo != _ALGO:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
    return hmac.compare_digest(digest.hex(), digest_hex)


def authenticate(conn, username, password):
    """Trả về User nếu đúng tài khoản và mật khẩu, None nếu sai. Mọi lần thử đều được ghi nhật ký."""
    from app import db  # import tại chỗ để tránh vòng lặp với db

    username = (username or "").strip()
    row = db.get_user(conn, username) if username else None
    ok = bool(row) and row["active"] == 1 and verify_password(password or "", row["password_hash"])
    db.log_login(conn, username, ok)
    if not ok:
        return None
    return User(row["username"], row["ho_ten"], row["vai_tro"], row["khoa"] or "")
