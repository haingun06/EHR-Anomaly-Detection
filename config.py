from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "anomaly_model.joblib"
DB_PATH = ROOT / "data" / "app.sqlite"

MODEL_VERSION = "v1.0.0"
SEED = 42

TEST_SIZE = 0.20
ERROR_RATE = 0.05
ERROR_TYPES = ["missing", "duplicate", "date_logic", "age", "duration", "cost", "frequency"]
VALUE_ERROR_TYPES = ["age", "duration", "cost", "frequency"]

MIN_GROUP_TRAIN_N = 1000
IF_N_ESTIMATORS = 200
IF_MAX_SAMPLES = 256
CONTAMINATION_GRID = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]
DEFAULT_CONTAMINATION = 0.05

# ---- Chuẩn mã và bối cảnh Việt Nam ----
# Mã thủ tục/dịch vụ. Dữ liệu Synthea dùng SNOMED (chuỗi số). Khi áp dụng với danh mục
# dịch vụ kỹ thuật của bệnh viện, thay bằng mẫu đúng định dạng của danh mục đó.
PROCEDURE_CODE_PATTERN = r"^\d+$"
# Mã chẩn đoán nhập tay theo ICD-10 (bản tiếng Việt do Bộ Y tế ban hành).
# Mẫu bao quát dạng A00, A00.0, A00.01. Kiểm tra định dạng, không kiểm tra mã có tồn tại.
DIAGNOSIS_CODE_PATTERN = r"^[A-Z]\d{2}(\.[0-9A-Z]{1,4})?$"
# Hồ sơ cấu hình cổng liên thông (có thể chỉnh sửa, xem app/portal.py)
PORTAL_PROFILES_PATH = ROOT / "app" / "portal_profiles.json"
