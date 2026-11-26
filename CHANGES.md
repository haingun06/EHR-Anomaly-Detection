# Ghi chú thay đổi

## Điều chỉnh theo bối cảnh Việt Nam và bổ sung luật

### Đã thực hiện
- **Ngày giờ kiểu Việt Nam** (`anomaly/features.py: to_ts_vn`, `app/service.py`): chấp nhận DD/MM/YYYY; luôn hiểu dạng có dấu gạch chéo là ngày-tháng-năm; từ chối ngày không tồn tại và giờ ngoài 00–23 hoặc phút/giây ngoài 00–59.
- **Chép dữ liệu từ lịch sử có ghi nhận** (`service._fill_from_history` trả thêm danh sách trường đã chép; `service.score_and_store` ghi nhật ký `chép_từ_lịch_sử`; giao diện hiển thị cảnh báo yêu cầu đối chiếu). Không tạo quy trình xử lý, để tránh làm đầy danh sách cảnh báo với mọi bệnh nhân tái khám.
- **Luật danh tính** (`anomaly/rules.py: identity_checks`): giới tính khác lịch sử là cờ cứng; họ tên khác lịch sử là cờ thông tin (`INFO_RULE_CODES`), không đổi trạng thái và không tính vào `rule_hit`. Có thể tắt bằng `identity_check = False`.
- **Luật mã** (`code_checks`): `code_missing`, `code_format` (theo `PROCEDURE_CODE_PATTERN`), `diagnosis_code_missing`, `diagnosis_code_format` (ICD-10, theo `DIAGNOSIS_CODE_PATTERN`). Mã chẩn đoán được lưu vào `chan_doan.CODE` (nguồn `manual`) và được dùng lại khi chấm lại.
- **Luật phiếu và ký số** (`document_checks`): `document_missing`, `signature_missing`. Cột mới `PHIEU_DAY_DU`, `DA_KY_SO` trong `luot_kham`. `SCHEMA_VERSION` = 6.
- **Cổng liên thông** (`app/portal.py`, `app/portal_profiles.json`, `app/portal_check.py`): kiểm tra trường bắt buộc, trường số, định dạng ngày, thứ tự thời gian và trạng thái chấm điểm; xuất CSV theo tên cột và định dạng của cổng.
- **Sửa lỗi cờ tuổi:** `age_range` nay là cờ cứng. Trước đây lượt khám chỉ có cờ này bị ghi nhận là "bình thường" và giao diện báo "không có lỗi bất thường".
- **Tương thích mô hình cũ:** `load_model` bổ sung các khóa cấu hình mới vào `rules_config` từ mặc định, nên file `.joblib` huấn luyện trước đó vẫn nạp được.
- **Giao diện:** thêm ô Mã ICD-10, hai ô chọn Phiếu và Ký số, nhãn "Quận/Huyện/Phường/Xã", mục kiểm tra cổng trên trang "Mô hình và dữ liệu". Bỏ import trùng.

### Đã kiểm chứng
- Toàn bộ test: 129 test đạt (101 test cũ, trong đó một test được cập nhật theo kiểu trả về mới của `_fill_from_history`; 28 test mới trong `tests/test_vn_context.py`, gồm một test giao diện AppTest).
- Huấn luyện và đánh giá lại: số liệu không đổi (TP/FP/FN/TN và bảng theo loại lỗi giống hệt trước khi sửa). Lý do: dữ liệu Synthea không có mã thiếu, mã không phải số, hay thay đổi danh tính giữa các lượt khám (đã kiểm tra).

### Chưa đánh giá trên dữ liệu
- Các luật `code_missing`, `code_format`, `diagnosis_code_*`, `document_missing`, `signature_missing`, `identity_*` **đã triển khai nhưng chưa đánh giá** bằng nhãn lỗi. Muốn đưa số liệu vào báo cáo, cần thêm các kiểu lỗi tương ứng vào `pipeline/02_inject_errors.py` và đánh giá lại.
- Các hồ sơ cổng là giả định, chưa đối chiếu với đặc tả thật.

### Chủ ý không làm
- **Kiểm tra định dạng ZIP/mã bưu chính:** Việt Nam không dùng mã bưu chính theo kiểu Hoa Kỳ, nên luật định dạng sẽ sai. Trường này chỉ còn là thông tin tùy chọn.
- **Kiểm tra STATE:** giá trị hợp lệ là danh sách đơn vị hành chính, cần danh mục chính thức để kiểm tra. Chưa làm.

## Vòng 2: sửa bảy lỗi còn mở

### Đã sửa
1. **Trùng lặp phụ thuộc thứ tự Id** (`db.history_for`, `pipeline/common.load_table`): thứ tự nhập lấy từ rowid trong CSDL và từ dòng trong file CSV, không dựa vào mã lượt khám. Đã kiểm chứng trước khi sửa: chỉ phát hiện khoảng 40% với UUID. Sau khi sửa: phát hiện đúng bản nhập sau trong mọi thứ tự mã.
2. **Recall 100% của luật trùng lặp là tạo tác của cách đặt tên** (`pipeline/02_inject_errors.py`): bản sao nay có mã ngẫu nhiên (RNG riêng để không làm đổi các lỗi khác). Bản sao vẫn được ghi sau bản gốc và được gắn nhãn, tức là coi bản nhập sau là bản trùng. Đây là giả định có chủ đích, phải nêu trong báo cáo. Recall 100% nay phản ánh đúng luật khi bản trùng là bản nhập sau, không còn phụ thuộc vào cách đặt tên.
3. **Isolation Forest huấn luyện trên dữ liệu có lỗi** (`pipeline/03_train.py`): mô hình chỉ fit trên dữ liệu sạch. Ngưỡng là phân vị dữ liệu sạch. Nhãn chỉ dùng để chọn contamination theo F1 trên tập train đã chèn lỗi.
4. **Ngày sinh của bệnh nhân cũ hiển thị "—"** (`app/streamlit_app.py: _birth_text`, `db.reference_birthdate`): hiển thị ngày sinh tham chiếu kèm ghi chú "theo lịch sử bệnh nhân". Dữ liệu lưu không đổi.
5. **Luồng cập nhật không kiểm tra trường bắt buộc** (`service.required_errors_after_edit`): không cho phép xóa trường bắt buộc đang có giá trị. Có chủ ý không chặn việc bổ sung trường còn thiếu, vì đó là việc cần làm khi xử lý cảnh báo thiếu dữ liệu. Lần sửa đầu tiên của quy tắc này chặn cả việc bổ sung và làm hỏng luồng sửa bản ghi thiếu chi phí. Đã phát hiện qua test và sửa lại.
6. **Kiểm tra không khớp bệnh nhân không bao giờ kích hoạt** (`pipeline/common.count_unmatched_patients`): đếm đúng ô NaN sau khi ghép và ô rỗng.
7. **Kết nối SQLite dùng chung giữa các phiên** (`app/streamlit_app.py: get_conn`): mỗi phiên có kết nối riêng, lưu trong `st.session_state`. Bật WAL và `busy_timeout` (5 giây) trong `db.connect`. Đăng nhập và đăng xuất giữ lại kết nối của phiên.

### Số liệu đánh giá thay đổi (đây là kết quả thật, không phải lỗi)
Sau khi huấn luyện lại trên dữ liệu sạch, Isolation Forest đo được kém hơn trên tập test đã chèn lỗi:

| Phương pháp | Trước (P / R / F1) | Sau (P / R / F1) |
|---|---|---|
| Rule-based | 0,9944 / 0,5631 / 0,7190 | không đổi |
| Isolation Forest | 0,1053 / 0,2618 / 0,1502 | 0,0765 / 0,2066 / 0,1116 |
| Kết hợp | 0,2512 / 0,7476 / 0,3760 | 0,2216 / 0,7114 / 0,3380 |

Nguyên nhân: trước đây mô hình học cả các giá trị bất thường trong dữ liệu huấn luyện, nên một phần khả năng phát hiện đo được trên tập test đến từ việc mô hình đã "thấy" kiểu lỗi đó. Khi huấn luyện trên dữ liệu sạch, phép đo trung thực hơn nhưng thấp hơn. Báo cáo cần nêu rõ điều này và dùng số liệu mới. Số liệu cũ không được giữ làm kết quả chính.

Kiểm tra liên quan: các luật không đổi nên Recall theo loại lỗi Rule-based không đổi.

### Vẫn chưa làm
- Các luật mới của vòng 1 vẫn chưa được đánh giá bằng nhãn lỗi (xem vòng 1).
- Hồ sơ cổng liên thông vẫn là giả định.
- Chưa kiểm tra mã ICD-10 có tồn tại trong danh mục; chỉ kiểm tra định dạng.

