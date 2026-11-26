#!/usr/bin/env bash
# Chạy toàn bộ pipeline, kiểm thử, rồi nạp dữ liệu demo. Yêu cầu: đã đặt CSV Synthea vào data/raw/.
set -euo pipefail
cd "$(dirname "$0")"
python pipeline/01_prepare.py
python pipeline/eda.py --stage clean
python pipeline/02_inject_errors.py
python pipeline/eda.py --stage injected
python pipeline/03_train.py
python pipeline/04_evaluate.py
pytest -q
python -m app.seed_demo --reset
echo "Hoàn tất. Chạy giao diện: streamlit run app/streamlit_app.py"
