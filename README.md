# Phát hiện dữ liệu bất thường trong hồ sơ bệnh án

Đồ án xây dựng hệ thống phát hiện dữ liệu bất thường trong hồ sơ bệnh án điện tử (EHR), kết hợp **Rule-based** và **Isolation Forest**, đồng thời cung cấp ứng dụng MVP để nhập liệu, xem cảnh báo, xác minh và cập nhật hồ sơ.

Dự án gồm hai phần chính:

1. **Pipeline thực nghiệm:** chuẩn hóa dữ liệu Synthea, tạo lỗi có kiểm soát, huấn luyện mô hình và đánh giá kết quả.
2. **Ứng dụng Streamlit:** chấm điểm lượt khám, hiển thị lý do cảnh báo, quản lý hồ sơ theo các mục EMR và theo dõi quy trình xử lý.

> **Lưu ý:** Dữ liệu sử dụng là dữ liệu mô phỏng từ Synthea, không phải dữ liệu bệnh nhân thật hay dữ liệu của bệnh viện Việt Nam. Kết quả chỉ có ý nghĩa minh họa tính khả thi kỹ thuật, không dùng để hỗ trợ quyết định y khoa.

## 1. Công nghệ sử dụng

- Python 3.14
- Pandas, NumPy
- Scikit-learn – Isolation Forest
- Streamlit – giao diện ứng dụng
- SQLite – lưu hồ sơ, kết quả chấm điểm và nhật ký
- Pytest – kiểm thử

## 2. Yêu cầu đầu vào

- Windows 10/11, macOS hoặc Linux.
- Python 3.14. Trên Windows có thể sử dụng Python Launcher với lệnh `py -3.14`.
- Ba tệp dữ liệu CSV từ Synthea:
  - `patients.csv`
  - `encounters.csv`
  - `conditions.csv`

Đặt ba tệp CSV vào thư mục `data/raw/`. Dữ liệu gốc không được đóng gói cùng mã nguồn.

## 3. Cài đặt môi trường

Mở terminal tại thư mục gốc của dự án.

### Windows (PowerShell)

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
```

Trong các bước tiếp theo, nên tiếp tục dùng `\.venv\Scripts\python.exe` để tránh nhầm phiên bản Python hoặc lỗi PATH.

### macOS/Linux

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### PyCharm

Mở thư mục dự án trong PyCharm, chọn **Settings → Python Interpreter → Add Interpreter**, tạo virtual environment mới bằng Python 3.14 và trỏ đến thư mục `.venv`. Sau đó cài các thư viện trong `requirements.txt` bằng Terminal của PyCharm.

## 4. Chạy pipeline thực nghiệm

Sau khi đặt đủ ba tệp CSV vào `data/raw/`, chạy lần lượt các lệnh sau từ thư mục gốc dự án.

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe pipeline\01_prepare.py
.\.venv\Scripts\python.exe pipeline\eda.py --stage clean
.\.venv\Scripts\python.exe pipeline\02_inject_errors.py
.\.venv\Scripts\python.exe pipeline\eda.py --stage injected
.\.venv\Scripts\python.exe pipeline\03_train.py
.\.venv\Scripts\python.exe pipeline\04_evaluate.py
```

### macOS/Linux hoặc Git Bash

Có thể chạy toàn bộ pipeline, kiểm thử và nạp dữ liệu demo bằng:

```bash
./run_all.sh
```

`run_all.sh` không chạy trực tiếp trên PowerShell.

### Các bước trong pipeline

| Tệp | Chức năng | Kết quả chính |
|---|---|---|
| `pipeline/01_prepare.py` | Đọc và chuẩn hóa dữ liệu Synthea, ghép thông tin bệnh nhân và lượt khám, xuất dữ liệu chẩn đoán | `encounters_clean.csv`, `conditions_clean.csv`, `manifest_clean.json` |
| `pipeline/eda.py --stage clean` | Phân tích dữ liệu sau chuẩn hóa | `data/processed/eda/clean/` |
| `pipeline/02_inject_errors.py` | Tạo các trường hợp bất thường có kiểm soát và nhãn tương ứng | `encounters_injected.csv`, `labels.csv`, `injection_summary.json` |
| `pipeline/eda.py --stage injected` | Phân tích dữ liệu sau khi chèn lỗi | `data/processed/eda/injected/` |
| `pipeline/03_train.py` | Huấn luyện Isolation Forest theo nhóm loại lượt khám và chọn ngưỡng | `models/anomaly_model.joblib`, `split_patients.csv`, `train_report.json` |
| `pipeline/04_evaluate.py` | Đánh giá Rule-based, Isolation Forest và phương pháp kết hợp | `eval_metrics.json`, `error_cases.csv`, `test_predictions.csv` |

Pipeline có sử dụng cùng một module chấm điểm với ứng dụng để bảo đảm logic phát hiện bất thường nhất quán giữa thực nghiệm và vận hành.

## 5. Chạy kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Hoặc khi đã kích hoạt môi trường ảo:

```bash
python -m pytest -q
```

Bộ kiểm thử hiện tại bao gồm:

- Kiểm tra các đặc trưng và luật phát hiện bất thường.
- Kiểm tra định dạng dữ liệu hiển thị trên giao diện.
- Kiểm tra tính nhất quán giữa pipeline và đường chấm điểm qua CSDL.
- Kiểm tra quy trình xử lý: bắt đầu, cập nhật hồ sơ, chấm lại, hoàn tất và mở lại.
- Kiểm tra giao diện Streamlit bằng `AppTest`.

Một số kiểm thử tích hợp và giao diện cần có mô hình đã huấn luyện. Nếu thiếu tệp mô hình, các kiểm thử phụ thuộc mô hình có thể được đánh dấu `skipped`.

## 6. Nạp dữ liệu demo và khởi chạy ứng dụng

Sau khi hoàn tất pipeline và có tệp mô hình, chạy:

```powershell
.\.venv\Scripts\python.exe -m app.seed_demo --reset
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

Trên macOS/Linux:

```bash
python -m app.seed_demo --reset
python -m streamlit run app/streamlit_app.py
```

Mở địa chỉ hiển thị trong terminal, mặc định là `http://127.0.0.1:8501`.

Lệnh `seed_demo --reset` tạo lại cơ sở dữ liệu demo từ dữ liệu đã xử lý. Thao tác này sẽ xóa dữ liệu demo hiện có trong CSDL ứng dụng, vì vậy không chạy nếu cần giữ lại dữ liệu đang sử dụng.

## 7. Các chức năng của ứng dụng

Ứng dụng hiện có bốn khu vực chính:

### 7.1. Nhập và chấm điểm

- Nhập thông tin bệnh nhân và lượt khám, bao gồm thông tin hành chính, bảo hiểm, lý do khám và chẩn đoán.
- Với bệnh nhân mới, cần cung cấp họ, tên, giới tính và ngày sinh.
- Với bệnh nhân đã có hồ sơ, các trường hành chính có thể được lấy từ lượt khám gần nhất khi để trống.
- Sau khi kiểm tra dữ liệu đầu vào, hệ thống chấm điểm và lưu lượt khám.
- Các lỗi logic như thời điểm kết thúc trước thời điểm bắt đầu có thể được ghi nhận thành cảnh báo để người dùng xác minh.
- Hồ sơ vừa lưu được hiển thị ngay bên dưới biểu mẫu.

### 7.2. Danh sách cảnh báo

- Hiển thị các lượt khám được hệ thống đánh dấu bất thường.
- Lọc danh sách theo trạng thái xử lý và loại lượt khám.
- Phân trang danh sách và mở chi tiết từng lượt khám để xem lý do cảnh báo, kiểm tra hồ sơ và thực hiện xử lý.

### 7.3. Nhật ký

- Hiển thị lịch sử thay đổi trạng thái và cập nhật hồ sơ.
- Ghi nhận người thực hiện, thời điểm và nội dung thao tác theo dữ liệu ứng dụng.
- Nhật ký được thiết kế theo hướng chỉ thêm; không hỗ trợ sửa hoặc xóa bản ghi nhật ký thông qua ứng dụng.

### 7.4. Mô hình và dữ liệu

- Hiển thị thông tin mô hình, ngưỡng phát hiện theo nhóm và số lượng dữ liệu.
- Cung cấp thao tác nạp lại dữ liệu demo.

## 8. Hồ sơ bệnh án theo các mục EMR

Giao diện tổ chức thông tin theo các nhóm dữ liệu mà bộ Synthea hiện có:

| Nhóm EMR | Nội dung hiển thị | Nguồn dữ liệu |
|---|---|---|
| Thông tin hành chính | Họ tên, ngày sinh, giới tính, địa chỉ, mã bệnh nhân và mã lượt khám | `patients.csv`, `encounters.csv` |
| Thông tin bảo hiểm | Mã đơn vị thanh toán và phần bảo hiểm chi trả | `encounters.csv` |
| Tiền sử và bệnh sử | Lý do khám, tiền sử bệnh cá nhân | `encounters.csv`, `conditions.csv` |
| Thăm khám và chẩn đoán | Loại lượt khám, thời gian khám và chẩn đoán | `encounters.csv`, `conditions.csv` |
| Điều trị và theo dõi | Thủ thuật/thủ tục, chi phí và diễn biến các lượt khám | `encounters.csv` |
| Thông tin xác thực | Mã bác sĩ, thời điểm tạo/chỉnh sửa, phiên bản hồ sơ, người xác nhận và lịch sử truy cập | `encounters.csv` và nhật ký ứng dụng |

Một số thông tin thường có trong hồ sơ bệnh án thực tế như số điện thoại, email, tiền sử gia đình, dị ứng, dấu hiệu sinh tồn, kết quả khám lâm sàng, đơn thuốc, phác đồ điều trị, lời dặn xuất viện và chữ ký số không có trong bộ dữ liệu Synthea đang sử dụng nên không được thể hiện như dữ liệu có sẵn.

Bộ dữ liệu Synthea không xác định đơn vị tiền tệ. Giao diện hiện quy ước hiển thị chi phí theo VND; cần xác nhận lại đơn vị trước khi sử dụng dữ liệu thực tế.

## 9. Quy trình xử lý cảnh báo

Mỗi lượt khám có cảnh báo đi qua ba trạng thái:

| Trạng thái | Thao tác | Mô tả |
|---|---|---|
| Chờ xử lý | Bắt đầu xử lý | Người dùng tiếp nhận lượt khám cần xác minh. |
| Đang xử lý | Cập nhật hồ sơ, hoàn tất | Có thể chỉnh sửa trường dữ liệu được phép; mỗi lần cập nhật cần ghi lý do. Sau khi lưu, hệ thống tự động chấm điểm lại bằng mô hình hiện tại. |
| Đã xử lý | Mở lại xử lý | Lưu kết luận, ghi chú, người hoàn tất và thời điểm. Nếu cần xác minh thêm, người dùng có thể mở lại với lý do cụ thể. |

Khi hoàn tất, người dùng chọn một trong hai kết luận:

- **Đã cập nhật dữ liệu:** chỉ áp dụng khi đã có ít nhất một thay đổi hồ sơ được lưu trong lần xử lý hiện tại.
- **Xác nhận cảnh báo, cần xem xét thêm:** sử dụng khi dữ liệu chưa được chỉnh sửa nhưng cảnh báo cần được ghi nhận hoặc chuyển xem xét tiếp.

Mỗi thay đổi hồ sơ được ghi nhận theo trường, gồm giá trị cũ và giá trị mới. Các thao tác chuyển trạng thái cũng được lưu trong nhật ký. Người thực hiện là tài khoản đăng nhập (xem mục 13 về xác thực và phân quyền).

## 10. Cấu trúc thư mục

```text
EHR-Anomaly-Detection/
├── anomaly/
│   ├── detector.py          # Logic chấm điểm và kết hợp kết quả phát hiện
│   ├── features.py          # Trích xuất đặc trưng
│   └── rules.py             # Các luật phát hiện bất thường
├── app/
│   ├── db.py                # SQLite và các thao tác dữ liệu
│   ├── present.py           # Định dạng dữ liệu hiển thị
│   ├── seed_demo.py         # Nạp dữ liệu demo
│   ├── service.py           # Nghiệp vụ và quy trình xử lý
│   └── streamlit_app.py     # Giao diện Streamlit
├── data/
│   ├── raw/                 # CSV đầu vào từ Synthea
│   └── processed/           # Dữ liệu đã xử lý và kết quả đánh giá
├── models/
│   └── anomaly_model.joblib # Mô hình Isolation Forest đã huấn luyện
├── pipeline/
│   ├── 01_prepare.py        # Chuẩn hóa dữ liệu
│   ├── 02_inject_errors.py  # Chèn lỗi có kiểm soát
│   ├── 03_train.py          # Huấn luyện mô hình
│   ├── 04_evaluate.py       # Đánh giá mô hình
│   ├── common.py            # Hàm dùng chung
│   └── eda.py               # Phân tích dữ liệu
├── tests/                   # Kiểm thử đơn vị, tích hợp và giao diện
├── config.py                # Cấu hình chung
├── requirements.txt         # Các thư viện phụ thuộc
├── run_all.sh               # Chạy pipeline, kiểm thử và nạp demo
└── README.md
```

CSDL SQLite của ứng dụng được tạo tại `data/app.sqlite` khi nạp dữ liệu demo.

## 11. Phương pháp phát hiện bất thường

Hệ thống kết hợp hai phương pháp:

- **Rule-based:** kiểm tra các điều kiện nghiệp vụ có thể mô tả bằng quy tắc, ví dụ thiếu trường bắt buộc, trùng lặp, sai logic ngày giờ, bất thường về tuổi và không nhất quán ngày sinh.
- **Isolation Forest:** học mẫu dữ liệu thông qua các đặc trưng số và lịch sử lượt khám để phát hiện các bản ghi khác biệt so với phần lớn dữ liệu.
- **Phương pháp kết hợp:** đánh dấu bất thường nếu luật hoặc Isolation Forest phát hiện vấn đề.

Pipeline và ứng dụng sử dụng chung module `anomaly.detector`. Dữ liệu được chia theo bệnh nhân để các lượt khám của cùng một bệnh nhân không nằm rải rác ở nhiều tập dữ liệu. Mô hình Isolation Forest và ngưỡng được thiết lập theo nhóm loại lượt khám.

## 12. Kết quả đánh giá

Theo `data/processed/eval_metrics.json` hiện có (sau khi huấn luyện lại trên dữ liệu sạch), tập kiểm thử gồm 12.976 lượt khám, trong đó có 634 lượt được gắn nhãn lỗi.

| Phương pháp | Precision | Recall | F1-score |
|---|---:|---:|---:|
| Rule-based | 0,9944 | 0,5631 | 0,7190 |
| Isolation Forest | 0,0765 | 0,2066 | 0,1116 |
| Kết hợp | 0,2216 | 0,7114 | 0,3380 |

Kết quả cho thấy Rule-based có precision cao trên các lỗi được định nghĩa bằng quy tắc; Isolation Forest phát hiện thêm một số bất thường về thời lượng, chi phí và tần suất nhưng cũng tạo nhiều cảnh báo nhầm. Phương pháp kết hợp tăng recall so với từng phương pháp riêng lẻ trong thí nghiệm này.

Các số liệu phụ thuộc vào dữ liệu mô phỏng, cách chèn lỗi và cấu hình thực nghiệm. Khi chạy lại pipeline với dữ liệu hoặc phiên bản thư viện khác, hãy sử dụng số liệu mới trong `eval_metrics.json` thay vì mặc định rằng bảng trên luôn đúng.

## 13. Một số quyết định kỹ thuật

- **Một đường chấm điểm:** pipeline đánh giá và ứng dụng cùng gọi `anomaly.detector` để hạn chế sai khác về logic.
- **Đặc trưng theo lịch sử:** dùng các lượt khám bắt đầu trước lượt đang xét. Với lượt cùng thời điểm, bản nhập trước được xác định theo thứ tự ghi vào CSDL (rowid), không theo mã lượt khám, vì mã có thể là UUID ngẫu nhiên.
- **Huấn luyện trên dữ liệu sạch:** mô hình Isolation Forest chỉ được fit trên dữ liệu sạch của bệnh nhân thuộc tập train. Nhãn lỗi chỉ dùng để chọn contamination theo F1 trên tập train đã chèn lỗi. Ngưỡng là phân vị của dữ liệu sạch, nên contamination là tỷ lệ cảnh báo kỳ vọng trên dữ liệu bình thường.
- **Chia tập theo bệnh nhân:** giữ toàn bộ lịch sử của một bệnh nhân trong cùng một tập dữ liệu.
- **Phiên bản hồ sơ:** mỗi lần cập nhật làm tăng `revision`; kết quả chấm điểm gắn với lượt khám, phiên bản mô hình và phiên bản hồ sơ.
- **Tự động chấm lại:** sau khi cập nhật hồ sơ, hệ thống chấm lại bằng mô hình hiện tại.
- **Nhật ký chỉ thêm:** các bảng nhật ký, thay đổi và truy cập được bảo vệ khỏi thao tác cập nhật hoặc xóa thông qua trigger CSDL.
- **Giới hạn trường được sửa:** danh sách trường có thể cập nhật được xác định từ cấu hình CSDL; mã định danh bệnh nhân và lượt khám không được chỉnh sửa.
- **Nạp mô hình:** chỉ sử dụng tệp mô hình do dự án tạo ra. Không nạp mô hình không rõ nguồn gốc vì `joblib` dựa trên cơ chế pickle.

## 14. Giới hạn của dự án

- Dữ liệu Synthea là dữ liệu mô phỏng; kết quả không đại diện trực tiếp cho dữ liệu bệnh viện thực tế.
- Nhãn lỗi được tạo trong phạm vi thí nghiệm nên kết quả đánh giá phụ thuộc vào cách thiết kế lỗi.
- Synthea không có khái niệm khoa bệnh viện; loại lượt khám chỉ được dùng làm nhóm đại diện.
- Ứng dụng có đăng nhập và phân quyền theo vai trò, nhưng chưa phân quyền theo khoa và chưa tích hợp với hệ thống bệnh viện.
- Chưa triển khai nạp CSV hàng loạt và chưa đánh giá khả năng mở rộng trên quy mô lớn.
- Khi chỉnh sửa hồ sơ, các lượt khám sau đó của cùng bệnh nhân không tự động được chấm lại; cần thực hiện chấm lại riêng nếu muốn cập nhật điểm theo lịch sử mới.
- Nếu thêm một lượt khám có thời điểm trong quá khứ, điểm của các lượt khám sau đó không tự động thay đổi.
- Một số trường thông tin EMR không thể hiển thị do bộ dữ liệu nguồn không cung cấp.

## 15. Lỗi thường gặp

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| Không chạy được lệnh `python` trên Windows | Thử dùng `py -3.14` hoặc đường dẫn `\.venv\Scripts\python.exe`. Kiểm tra lại Python Launcher và cấu hình PATH. |
| `No matching distribution found` khi cài thư viện | Phiên bản thư viện có thể chưa hỗ trợ phiên bản Python đang dùng. Kiểm tra phiên bản Python và các ràng buộc trong `requirements.txt`. |
| Không nhận diện lệnh `pytest` | Chạy `python -m pytest -q` bằng Python thuộc môi trường ảo. |
| Thiếu `models/anomaly_model.joblib` | Chạy `pipeline/03_train.py` sau khi hoàn thành bước chuẩn hóa và chèn lỗi. |
| Thiếu tệp trong `data/raw/` | Kiểm tra đã đặt đủ `patients.csv`, `encounters.csv` và `conditions.csv` vào đúng thư mục hay chưa. |
| Thiếu `conditions_clean.csv` | Chạy lại `pipeline/01_prepare.py`. |
| CSDL được tạo bởi phiên bản cũ | Chạy `python -m app.seed_demo --reset` để tạo lại CSDL demo. Lưu ý thao tác này xóa dữ liệu demo hiện tại. |
| Danh sách cảnh báo trống | Kiểm tra đã có mô hình, dữ liệu đã xử lý và đã chạy lệnh nạp demo hay chưa. |
| Cổng 8501 đang được sử dụng | Chạy Streamlit với cổng khác, ví dụ `python -m streamlit run app/streamlit_app.py --server.port 8502`. |

---

## 16. Điều chỉnh theo bối cảnh Việt Nam

Phiên bản này bổ sung các điều chỉnh sau. Xem thêm `CHANGES.md` để biết chi tiết từng thay đổi.

- **Ngày giờ:** ô nhập chấp nhận `DD/MM/YYYY` và `DD/MM/YYYY HH:MM`, đồng thời vẫn chấp nhận `YYYY-MM-DD`. Dạng có dấu gạch chéo luôn được hiểu là ngày-tháng-năm. Trước đây `pd.Timestamp` đoán tháng-ngày-năm nên `03/04/2024` bị đọc thành 4 tháng 3.
- **Mã chẩn đoán ICD-10:** khi nhập chẩn đoán bằng chữ, cần nhập kèm mã ICD-10 (ví dụ `J45.9`). Luật kiểm tra thiếu mã và định dạng mã. Mẫu định dạng nằm trong `config.py` (`DIAGNOSIS_CODE_PATTERN`).
- **Mã thủ tục:** luật `code_missing` báo lỗi khi có tên thủ tục nhưng thiếu mã. Luật `code_format` kiểm tra mã theo `PROCEDURE_CODE_PATTERN`. Mặc định là chuỗi số để khớp Synthea. Khi áp dụng với danh mục dịch vụ kỹ thuật của bệnh viện, cần đổi mẫu này.
- **Phiếu, biểu mẫu và ký số:** người nhập khai báo `Đầy đủ` hoặc `Thiếu`. Chỉ khi khai báo là `Thiếu` mới gắn cờ. Để trống nghĩa là chưa khai báo, không bị coi là lỗi.
- **Danh tính:** giới tính khác lịch sử là cờ cứng. Họ tên khác lịch sử là cờ thông tin: hiển thị để xác nhận, không đổi trạng thái và không tính là phát hiện. So sánh họ tên không phân biệt dấu tiếng Việt.
- **Chép dữ liệu từ lịch sử:** khi bệnh nhân cũ để trống các trường hành chính, hệ thống vẫn chép như trước nhưng ghi nhật ký và hiển thị cảnh báo yêu cầu đối chiếu với giấy tờ.
- **Cổng liên thông:** `app/portal.py` kiểm tra hồ sơ theo một hồ sơ cổng khai báo trong `app/portal_profiles.json`. Hồ sơ đang có cảnh báo chưa xử lý không đạt. Dùng `python -m app.portal_check --profile emch_gia_dinh --out <file.csv>` hoặc trang "Mô hình và dữ liệu" trên giao diện.

**Lưu ý quan trọng về cổng liên thông:** các hồ sơ trong `portal_profiles.json` là giả định để minh họa cơ chế. Tên cột, định dạng và trường bắt buộc phải được đối chiếu với đặc tả chính thức của từng cổng trước khi dùng thật.

**Lưu ý nâng cấp:** phiên bản này tăng `SCHEMA_VERSION` lên 6 (thêm cột phiếu và ký số). Cần chạy `python -m app.seed_demo --reset` để tạo lại CSDL.
