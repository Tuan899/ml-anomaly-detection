# ANOMALY LAB — Giám sát hoạt động hệ quản trị CSDL

**NGHIÊN CỨU THUẬT TOÁN PHÁT HIỆN BẤT THƯỜNG TRONG HOẠT ĐỘNG CỦA HỆ QUẢN TRỊ CƠ SỞ DỮ LIỆU**

Ứng dụng Streamlit/FastAPI phân tích năm chỉ số MySQL: QPS, kết nối, thời gian
phản hồi, truy vấn chậm và kết nối thất bại. Nguồn dữ liệu là CSV ngoại tuyến
hoặc thu theo đợt từ MySQL bằng tài khoản chỉ đọc. Giữ đủ MAD, Isolation Forest,
LOF và One-Class SVM; mô hình chỉ học train và dự đoán test theo thời gian.

**Bắt đầu tại [hướng dẫn giao diện mới](docs/INTERFACE_GUIDE.md)**: chọn dữ liệu,
bấm **Bắt đầu phân tích**, đọc kết quả và so sánh hai bộ mẫu. Chế độ **Cơ bản**
là mặc định; chế độ **Nâng cao** giữ các cấu hình và chức năng nghiên cứu.

[Quy trình demo kỹ thuật MySQL](docs/DEMO_MYSQL.md) hướng dẫn cài đặt, chạy ứng dụng,
nhập hai bộ kiểm thử, đọc cảnh báo và đánh giá Precision/Recall/F1/confusion matrix.
[Thiết lập MySQL ít quyền và TLS](docs/MYSQL_SETUP.md) giải thích chính xác số đo
thực tế, bao gồm độ trễ thăm dò `SELECT 1` và giới hạn diễn giải.

Giao diện mặc định kiểm tra MySQL theo ba bước: chọn dữ liệu, phân tích tự động,
xem kết quả. Có màn hình so sánh hai bộ bằng cùng mô hình tham chiếu.
Hai CSV tổng hợp có nhãn nằm tại
`data/mysql_normal.csv` và `data/mysql_anomalous.csv`; manifest lưu seed, hash và
kịch bản chèn. Lệnh `python scripts/evaluate_mysql_demo.py` tính lại kết quả thật,
không đọc bảng điểm chép sẵn. Không dùng dữ liệu tổng hợp để khẳng định chất lượng
trên máy chủ thực.

Cảnh báo vận hành có bộ lọc dao động nhỏ với ngưỡng train và dung sai demo công
khai; giữ riêng dự đoán, điểm số và đánh giá gốc của từng thuật toán. Không tự coi
50 → 51 là bất thường. Giao diện hiển thị trạng thái ổn định/cần kiểm tra, cả năm
giá trị ở điểm cảnh báo và chỉ số lệch nền; chưa kết luận nguyên nhân.

Các chức năng CSV một chỉ số, NAB, notebook và API trước đây vẫn được giữ trong
**Nâng cao → CSV một chỉ số / notebook NAB**. Phần bên dưới ghi chi tiết luồng cũ.

**Luồng notebook tham chiếu (chế độ giữ lại):** dùng dữ liệu CPU EC2 NAB đầy đủ
4.032 điểm, baseline MAD trên toàn bộ chuỗi, Isolation Forest và LOF học 3.550
điểm đầu rồi dự đoán 482 điểm cuối. Hai mốc bất thường lấy từ nhãn gốc NAB.
Chế độ CSV tùy chỉnh vẫn có bốn thuật toán, trong đó mọi mô hình chỉ fit train.

Luồng notebook/CSV một chỉ số phân tích ngoại tuyến. Chế độ MySQL hỗ trợ thu số
liệu thật theo đợt; chưa phải dịch vụ cảnh báo chạy liên tục. Một cảnh báo của
mô hình cần được người dùng kiểm tra theo ngữ cảnh thực tế.

## Chạy trên Windows từ thư mục gốc

Các lệnh dưới đây chạy trong PowerShell tại `C:\Users\User\DACN`. Cần Python
3.10 trở lên và Streamlit 1.65 trở lên theo `requirements.txt`. Nếu đã có môi
trường `.venv`, bỏ qua lệnh tạo môi trường.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\DACN\ml-anomaly-detection\requirements.txt
```

**Terminal 1 — chạy BE FastAPI:**

```powershell
cd C:\Users\User\DACN
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --app-dir .\DACN\ml-anomaly-detection --reload
```

Đợi dòng `Application startup complete.`. Mở `http://127.0.0.1:8000/health`
để kiểm tra BE; trang thử API ở `http://127.0.0.1:8000/docs`.

**Terminal 2 — chạy FE Streamlit:**

```powershell
cd C:\Users\User\DACN
.\.venv\Scripts\python.exe -m streamlit run .\DACN\ml-anomaly-detection\frontend\app.py
```

Mở địa chỉ Streamlit in trong terminal, thường là `http://localhost:8501`.
Cần giữ cả hai terminal mở để phân tích dữ liệu. Cách gọi Python trực tiếp
ở trên không yêu cầu kích hoạt môi trường ảo. Nhấn `Ctrl + C` trong từng
terminal để dừng dịch vụ tương ứng.

FE gửi CSV và cấu hình đến BE qua `POST /detect`; chỉ BE huấn luyện và chạy
mô hình. Nếu BE tắt, FE vẫn mở được và cho xem trước CSV, nhưng bấm **Bắt đầu
phân tích** (Cơ bản) hoặc **Chạy phát hiện** (Nâng cao) sẽ hiện hướng dẫn kết nối
BE, không tạo kết quả phân tích mới.

```text
Trình duyệt → FE Streamlit → HTTP POST /detect → BE FastAPI → pipeline dùng chung
                    ↑                              |
                    └──────── kết quả JSON ────────┘
```

Theo mặc định, FE gọi `http://127.0.0.1:8000`. Nếu chạy BE ở địa chỉ khác,
đặt `ANOMALY_API_URL` trong **terminal chạy FE**, trước khi khởi động Streamlit.
Ví dụ BE chạy ở cổng 8001:

```powershell
# Terminal BE: thay lệnh chạy BE ở trên bằng lệnh này.
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --app-dir .\DACN\ml-anomaly-detection --reload --port 8001
```

```powershell
# Terminal FE: đặt địa chỉ BE rồi chạy giao diện.
$env:ANOMALY_API_URL = "http://127.0.0.1:8001"
.\.venv\Scripts\python.exe -m streamlit run .\DACN\ml-anomaly-detection\frontend\app.py
```

Biến này là địa chỉ mà máy chủ Streamlit dùng để gọi FastAPI. Thay đổi biến
cần khởi động lại FE; trình duyệt vẫn truy cập địa chỉ Streamlit cổng 8501.

Để minh chứng tích hợp khi báo cáo: chạy một lần phân tích và chỉ dòng
`POST /detect` trong terminal BE; dừng BE, bấm chạy lại để thấy thông báo
không kết nối được; bật BE và chạy lại để nhận kết quả mới. FE không tự chạy
thuật toán khi mất kết nối BE.

## Cách sử dụng giao diện

Mặc định giao diện mở **Cơ bản**: chọn một trong hai bộ mẫu hoặc so sánh cả hai,
bấm **Bắt đầu phân tích**, đọc trạng thái và các thời điểm cần kiểm tra, rồi tải
báo cáo. Xem [hướng dẫn mới](docs/INTERFACE_GUIDE.md) để demo từ đầu đến đánh giá.
Nguồn CSV và kết nối MySQL vẫn có trong lựa chọn nguồn dữ liệu.

Các bước notebook/CSV một chỉ số dưới đây bắt đầu bằng chọn **Nâng cao** ở thanh
bên, rồi chọn **CSV một chỉ số / notebook NAB**. Xem [demo MySQL Nâng cao](docs/DEMO_MYSQL.md)
để điều chỉnh thuật toán và đối chiếu đánh giá gốc/sau lọc.

Để chạy theo notebook bạn cung cấp:

1. Chọn **Dữ liệu mẫu có sẵn** → **NAB CPU đầy đủ · 4.032 điểm**.
2. Giữ **Áp dụng cấu hình notebook tham chiếu**. Cấu hình được cố định để tái lập:
   chỉ dùng `value` gốc, không StandardScaler hay đặc trưng lịch, train/test
   3.550/482, `contamination=1/3550`, IF có `random_state=42`, LOF có `novelty=True`.
3. Bấm **Chạy phát hiện**. Mở **Theo notebook** để xem nhãn NAB, KDE và MAD toàn chuỗi.
4. Mở **Đánh giá**, đọc số phát hiện đúng, cảnh báo nhầm, bỏ sót và phạm vi chấm.
5. Tải CSV/JSON hoặc tạo bộ ảnh báo cáo bằng script ở mục bên dưới.

Để dùng CSV của bạn: chọn **Tải CSV của bạn** (tối đa 10 MiB), chọn cột thời
gian, cột giá trị và nhãn nếu có. Chọn thuật toán, tỷ lệ train/test và cấu hình
rồi chạy. Mặc định chế độ tùy chỉnh học 70% dữ liệu đầu, dự đoán 30% cuối; có
bốn thuật toán MAD, Isolation Forest, LOF và One-Class SVM.

**Mẫu ngắn · 19 điểm** chỉ dùng thử thao tác; không thay thế dữ liệu NAB đầy đủ
khi báo cáo. Bỏ chọn cấu hình notebook trên mẫu NAB nếu muốn tự chọn tham số.

Kết quả có các tab tổng quan, chi tiết, đánh giá và hướng dẫn. Chế độ tham
chiếu có thêm tab **Theo notebook**, tách MAD toàn chuỗi khỏi kết quả test.
Sau khi đổi dữ liệu hoặc cấu hình, kết quả cũ được ẩn; chạy lại để cập nhật.
Tùy chọn giao diện sáng/tối áp dụng cho cả trang và biểu đồ.

Ảnh giao diện đã chạy với BE trên dữ liệu NAB:
[tổng quan](../../reports/notebook_reference/ui_desktop_overview.png),
[MAD toàn chuỗi](../../reports/notebook_reference/ui_desktop_mad.png),
[đánh giá](../../reports/notebook_reference/ui_desktop_evaluation.png),
[chế độ tối](../../reports/notebook_reference/ui_desktop_dark.png),
[điện thoại](../../reports/notebook_reference/ui_mobile_reference.png).

## CSV cần có gì?

CSV dùng dấu phẩy phân cách và có dòng tên cột. Tối thiểu cần một cột thời gian
và một cột giá trị có thể chuyển thành số. Ví dụ:

```csv
timestamp,value
2026-01-01 08:00:00,10.2
2026-01-01 08:05:00,10.5
2026-01-01 08:10:00,10.1
2026-01-01 08:15:00,10.3
2026-01-01 08:20:00,18.7
2026-01-01 08:25:00,10.4
```

Ví dụ này minh họa định dạng. Một vài dòng chỉ đủ kiểm tra thao tác, chưa đủ
đánh giá chất lượng phát hiện.

| Trường | Yêu cầu |
|---|---|
| Cột thời gian | Ví dụ `timestamp`; mỗi dòng có thời điểm hợp lệ và không trùng. |
| Cột chỉ số | Ví dụ `value`; chứa giá trị số, tên khác được chọn trên giao diện. |
| Cột nhãn, tùy chọn | Ví dụ `is_anomaly`; `1` = bình thường, `-1` = bất thường. |

Nhãn `0/1` cần được đổi sang đúng quy ước trước khi chọn làm nhãn thật. Nhãn
chỉ phục vụ đánh giá, không được dùng làm đầu vào học máy. Nếu chưa có nhãn
đáng tin cậy, giữ lựa chọn **Không dùng nhãn**.

Ứng dụng sắp xếp theo thời gian trước khi chia dữ liệu. Timestamp có múi giờ
được quy về UTC; timestamp không ghi múi giờ được diễn giải theo UTC. Dòng có
giá trị chỉ số bị thiếu, không phải số hoặc vô hạn bị loại và được thống kê
trong thông tin làm sạch. Timestamp lỗi hoặc trùng khiến lần chạy dừng để
người dùng sửa dữ liệu. Sau làm sạch cần ít nhất ba dòng huấn luyện và một
dòng kiểm tra.

Đơn vị của chỉ số do nguồn dữ liệu quy định. Ứng dụng giữ thang đo gốc trên
biểu đồ và trong file xuất; không tự suy diễn giá trị CPU là phần trăm.

## Hiểu thuật toán và kết quả

Phần dưới mô tả chế độ CSV tùy chỉnh. Chế độ notebook có khác biệt được ghi
rõ trong mục **Thực nghiệm theo notebook tham chiếu**, nhất là phạm vi fit MAD.

| Thuật toán | Cách hiểu ngắn gọn |
|---|---|
| MAD, robust Z-score | Tìm giá trị lệch xa trung vị của dữ liệu huấn luyện, dùng ngưỡng robust Z-score 3.5. |
| Isolation Forest | Tìm điểm dễ bị tách riêng khi phân hoạch dữ liệu bằng nhiều cây ngẫu nhiên. |
| Local Outlier Factor, LOF | Tìm điểm có mật độ thấp hơn vùng dữ liệu lân cận. |
| One-Class SVM | Học một vùng dữ liệu thường gặp, gắn cờ các điểm nằm ngoài vùng đó. |

**Tỷ lệ bất thường dự kiến** là tham số cấu hình cho Isolation Forest/LOF và
được dùng làm `nu` của One-Class SVM. Tham số này không bảo đảm số cảnh báo trên
dữ liệu kiểm tra bằng đúng tỷ lệ đã chọn. MAD dùng ngưỡng riêng.

Mặc định mô hình dùng chỉ số được chọn. Tùy chọn đặc trưng thời gian bổ sung
thông tin chu kỳ giờ và ngày; xem trường `features` và `parameters` trong JSON
để biết đầu vào của lần chạy. Các thống kê chuẩn hóa và tham số mô hình được
học từ tập huấn luyện.

Kết quả dự đoán chỉ gồm phần dữ liệu kiểm tra. Trên biểu đồ, đường thời gian
có thể gồm cả dữ liệu huấn luyện để cung cấp bối cảnh. Trong CSV xuất:

- `*_prediction`: `1` là bình thường, `-1` là điểm được mô hình gắn cờ.
- `*_score`: điểm quyết định; giá trị lớn hơn biểu thị dữ liệu thường gặp hơn
  đối với chính thuật toán đó. Không so sánh trực tiếp điểm số giữa các thuật toán.

Khi có nhãn thật, ứng dụng tính các chỉ số trên cùng tập kiểm tra:

- **Precision:** trong các điểm được cảnh báo, bao nhiêu điểm đúng là bất thường.
- **Recall:** trong các bất thường có nhãn, phát hiện được bao nhiêu điểm.
- **F1:** chỉ số kết hợp Precision và Recall.

Không có nhãn thì không tính các chỉ số này. Nếu tập kiểm tra không có bất
thường có nhãn, Recall/F1 chưa đủ để kết luận khả năng phát hiện. Các chỉ số
được tính theo từng điểm, không phải cơ chế chấm điểm theo cửa sổ thời gian
chính thức của NAB.

## API và tích hợp bằng Python

`POST /detect` nhận file CSV dạng multipart. Các tham số đặt trong query:

| Tham số | Mặc định / ý nghĩa |
|---|---|
| `timestamp_col` | `timestamp` |
| `value_col` | `value` |
| `label_col` | Bỏ trống nếu không dùng nhãn thật. |
| `models` | `mad,isolation_forest,lof,one_class_svm`; phân cách bằng dấu phẩy. |
| `train_fraction` | `0.7`; lớn hơn 0, nhỏ hơn 1. |
| `contamination` | `0.01`; lớn hơn 0, không vượt `0.5`. |
| `include_time` | `false`; bổ sung đặc trưng thời gian khi chọn `true`. |
| `split_index` | Tùy chọn; số dòng huấn luyện, thay cho cách chia bằng tỷ lệ. |
| `include_context` | `false`; đặt `true` để nhận thêm dữ liệu đã làm sạch phục vụ biểu đồ đầy đủ. FE sử dụng tùy chọn này. |
| `analysis_mode` | `chronological` cho CSV một chỉ số (API mặc định), `notebook_reference` cho NAB hoặc `dbms` cho năm chỉ số MySQL. Với `dbms`, `value_col` mặc định là `queries_per_second`. |
| `noise_guard` | `true`; bộ lọc dao động vận hành trong chế độ `dbms`, vẫn giữ kết quả mô hình gốc. |
| `deviation_threshold` | `3.5`, API cho phép từ 1 đến 10; độ nhạy ngưỡng nền của bộ lọc DBMS. |

Ví dụ chạy từ thư mục gốc:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/detect" -F "file=@DACN/ml-anomaly-detection/data/cpu_0.csv"
```

Tái lập notebook qua BE:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/detect?analysis_mode=notebook_reference&include_context=true" -F "file=@DACN/ml-anomaly-detection/data/ec2_cpu_utilization.csv"
```

Chế độ này kiểm tra đúng chuỗi tham chiếu; không áp nhãn NAB hay mốc chia cố
định lên CSV bất kỳ. Trong JSON, `metadata.reference_baseline` chứa kết quả
MAD toàn bộ chuỗi; `predictions`, `metrics` và `metadata.confusion_matrices`
ở mức chính dùng cùng 482 điểm test cho ba thuật toán.

JSON trả về gồm `metadata` (cấu hình, làm sạch, cảnh báo, thời gian chạy),
`predictions` (dự đoán trên tập kiểm tra), `anomalies` (điểm được gắn cờ theo
thuật toán) và `metrics` (khi đã chọn nhãn). Mặc định cấu trúc trả về giữ
nguyên; `include_context=true` bổ sung bối cảnh dữ liệu cho giao diện vẽ cả
phần huấn luyện và kiểm tra.

Để gọi pipeline bằng Python, chạy trong thư mục `DACN/ml-anomaly-detection`:

```python
from src.pipeline import run_detection

run = run_detection("data/cpu_0.csv", train_fraction=0.7)
print(run.metadata)
print(run.predictions.head())
```

## Đọc mã nguồn theo chức năng

| Tệp | Vai trò |
|---|---|
| `frontend/app.py` | Giao diện Streamlit: chọn dữ liệu, xem trước, cấu hình, gọi BE để phân tích, xem và tải kết quả. |
| `frontend/monitoring_workspace.py` | Giao diện Cơ bản mặc định: ba bước tự động, so sánh hai bộ dữ liệu, giải thích và báo cáo. |
| `frontend/input_data.py` | Tự nhận diện tên cột CSV phổ biến và kiểm tra dữ liệu đầu vào cho chế độ Cơ bản. |
| `frontend/dbms_dashboard.py` | Luồng MySQL Nâng cao: CSV/thu mẫu, cả năm chỉ số, trạng thái, bằng chứng và so sánh gốc/sau lọc. |
| `frontend/api_client.py` | Gửi CSV và cấu hình đến FastAPI, đọc JSON thành dữ liệu kết quả và xử lý lỗi kết nối. |
| `frontend/helpers.py` | Chọn cột số phù hợp và chuyển thông báo kiểm tra dữ liệu sang hướng dẫn tiếng Việt. |
| `backend/api.py` | Nhận yêu cầu HTTP, giới hạn dung lượng file và trả kết quả JSON. |
| `src/contracts.py` | Khai báo `DetectionRun`, cấu trúc kết quả dùng chung giữa pipeline và phía đọc kết quả API. |
| `src/pipeline.py` | Luồng xử lý dùng chung: làm sạch, chia theo thời gian, chạy mô hình, tổng hợp kết quả. |
| `src/dbms_monitoring.py` | Pipeline đa chỉ số MySQL; nền train, lọc nhiễu minh bạch, đánh giá và bằng chứng số liệu. |
| `src/mysql_collector.py` | Thu các chỉ số thực bằng truy vấn cố định, tài khoản chỉ đọc, TLS và xử lý reset bộ đếm. |
| `scripts/generate_mysql_demo.py`, `scripts/evaluate_mysql_demo.py` | Tái tạo dữ liệu kiểm thử và thực sự chạy đánh giá, lưu kết quả cùng nguồn và phiên bản. |
| `src/data_prep.py` | Kiểm tra CSV, xử lý timestamp, tạo đặc trưng lịch, thống kê MAD và tải dữ liệu NAB. |
| `src/models.py` | Tạo ma trận đặc trưng, chuẩn hóa theo train, chạy mô hình, đánh giá và chọn tham số trên tập validation riêng. |
| `src/eda.py` | Vẽ chuỗi thời gian và thống kê mô tả theo giờ, ngày trong tuần. |
| `src/anomaly_detection.py` | Chạy phân tích NAB CPU từ terminal, dùng cùng pipeline và cách chia theo thời gian. |
| `src/notebook_reference.py` | Tái lập cấu hình notebook: MAD mô tả toàn bộ chuỗi; IF/LOF học 3.550 điểm, dự đoán 482 điểm. BE và notebook gọi chung hàm này. |
| `notebooks/exploratory.ipynb` | Đọc dữ liệu NAB đầy đủ, biểu đồ nhãn, phân phối, MAD, IF, LOF và giải thích hai phạm vi đánh giá. |
| `../../scripts/run_notebook_reference.py` | Gọi chế độ notebook, tạo ảnh, CSV, JSON và giải thích số liệu thực để báo cáo. |

Luồng xử lý trên BE: **CSV → kiểm tra/làm sạch → chia train/test theo thời
gian → huấn luyện trên train → dự đoán trên test → JSON trả về FE**. FE chỉ
xem trước dữ liệu, gửi yêu cầu và trình bày biểu đồ, đánh giá, file kết quả.
`DetectionRun` cũng được import lại từ `src.pipeline` để giữ tương thích với
mã Python hiện có.

Notebook chạy được khi mở từ workspace root, thư mục `DACN/`, dự án con hoặc
`notebooks/`. Nó dùng chuỗi NAB 4.032 dòng, không dùng mẫu ngắn 19 dòng. Các ô
mã được lưu với `outputs=[]` và `execution_count=null`; chạy lại để nhận số liệu
từ dữ liệu thực, không sử dụng output được chép sẵn.

Script riêng `DACN/anomaly_detection.py`, tính từ thư mục gốc, tạo dữ liệu
giả lập có nhãn khớp các điểm được chèn, rồi gọi cùng pipeline. Đây là bản
minh họa, không phải dữ liệu NAB và không chứng minh chất lượng trên dữ liệu
thực. Từ thư mục gốc có thể chạy:

```powershell
.\.venv\Scripts\python.exe .\DACN\anomaly_detection.py
```

Thêm `--show` nếu muốn mở biểu đồ Matplotlib. Import script không tự chạy
phân tích hoặc mở cửa sổ biểu đồ.

## Bộ CSV để tự kiểm thử

Tải [bộ 9 tệp CSV kiểm thử](./data/bo_csv_kiem_thu.zip), giải nén rồi tải từng
tệp lên giao diện. Xem [hướng dẫn và kết quả mong đợi](./data/kiem_thu/HUONG_DAN.md)
để phân biệt lỗi định dạng, dòng cần làm sạch và điểm bất thường trong dữ liệu
hợp lệ. Toàn bộ các tệp này là dữ liệu giả lập phục vụ kiểm thử.

Bắt đầu với `02_bat_thuong_co_nhan.csv`: chọn `timestamp`, `value` và nhãn
`is_anomaly`, chỉ chạy MAD, giữ tỷ lệ huấn luyện 70% và tắt đặc trưng chu kỳ.
Trong 60 điểm kiểm tra, kết quả mong đợi là 3 cảnh báo đúng, 0 cảnh báo nhầm,
0 bỏ sót. Kết quả này kiểm tra chức năng trên ví dụ đã biết, không chứng minh
chất lượng trên dữ liệu thực tế.

Có thể tạo lại các tệp bằng lệnh sau, chạy từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe .\scripts\create_test_samples.py
```

Lệnh chỉ ghi các tệp trong bộ kiểm thử và tệp ZIP; không thay đổi dữ liệu NAB.

## Kiểm tra sau khi sửa mã nguồn

Từ thư mục gốc, chạy các kiểm thử pipeline, API, giao tiếp HTTP FE–BE và
luồng thao tác Streamlit:

```powershell
Push-Location .\DACN\ml-anomaly-detection
& ..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
```

Các kiểm thử dùng dữ liệu nhỏ để kiểm tra tính đúng của chương trình, không
đánh giá chất lượng thuật toán trên một bộ dữ liệu thực nghiệm đầy đủ.
Các ca tích hợp kiểm tra cách gửi CSV/cấu hình, đọc kết quả API và thông báo
khi BE không kết nối được; FE không dùng pipeline cục bộ để thay thế BE.

## Thực nghiệm theo notebook tham chiếu

Dữ liệu chính là chuỗi [EC2 CPU của NAB](https://github.com/numenta/NAB/blob/master/data/realAWSCloudwatch/ec2_cpu_utilization_24ae8d.csv),
có 4.032 điểm cách nhau 5 phút. Tệp `data/ec2_cpu_utilization.csv` giữ dữ liệu
gốc; `data/nab_cpu_labeled.csv` thêm nhãn `is_anomaly` theo
[combined_labels.json](https://github.com/numenta/NAB/blob/master/labels/combined_labels.json).
Nguồn cố định theo commit và mã băm nằm ở `data/nab_provenance.json`; giấy phép
ở `data/NAB_LICENSE.txt`. Nhãn không phải đầu vào của mô hình.

| Mốc nhãn gốc | Vị trí trong cách chia 3.550/482 |
|---|---|
| `2014-02-26 22:05:00` | Tập huấn luyện |
| `2014-02-27 17:15:00` | Tập kiểm tra |

Theo notebook tham chiếu, baseline MAD lấy median/MAD từ **toàn bộ 4.032
điểm**, đánh dấu khi `abs(0.6745 * (value - median) / MAD) >= 3.5`, rồi đánh
giá trên toàn bộ chuỗi có hai nhãn. Đây là phân tích mô tả chuỗi đã quan sát,
có dùng dữ liệu test khi tính thống kê, không phải phép thử chỉ học quá khứ.

Isolation Forest và LOF chỉ fit **3.550 điểm đầu**, dự đoán **482 điểm cuối**
có một nhãn. Giữ giá trị gốc, không StandardScaler, không thêm đặc trưng lịch;
`contamination=1/3550`, IF dùng `random_state=42`, LOF dùng `novelty=True`.

Không xếp hạng trực tiếp MAD toàn bộ chuỗi với IF/LOF trên test vì khác phạm
vi chấm. Bảng so sánh thêm trên cùng 482 điểm có ghi rõ MAD vẫn dùng thống kê
toàn bộ dữ liệu; không gọi đó là ba mô hình đều chỉ fit train. Khi cần quy
trình fit train chung, chọn chế độ CSV tùy chỉnh của ứng dụng.

Để tạo ảnh và số liệu có thể đưa vào báo cáo, chạy từ workspace root:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_notebook_reference.py
```

Kết quả trong [reports/notebook_reference](../../reports/notebook_reference/README.md):
biểu đồ hai nhãn, KDE và median tính thực tế, ma trận nhầm lẫn MAD/IF/LOF, CSV
dự đoán và `summary.json`. Script gọi cùng hàm của BE, không nhập sẵn số liệu.

Khi báo cáo, chỉ dữ liệu/nhãn gốc → mốc chia train/test → điểm được cảnh báo →
ma trận nhầm lẫn và Precision/Recall/F1. Ma trận có hàng nhãn thật, cột dự đoán,
thứ tự `[1, -1]`, tương ứng `[[TN, FP], [FN, TP]]`. Test chỉ có một bất thường
được chú giải; chưa đủ suy rộng độ chính xác trên các chuỗi thực tế khác.
Đánh giá này theo từng điểm, không phải cách chấm NAB theo cửa sổ. Dữ liệu CPU
EC2 chưa xác lập tải cơ sở dữ liệu và ứng dụng chưa giám sát thời gian thực.

## Các mẫu ngắn và giới hạn

Các tệp `data/cpu_0.csv` đến `data/cpu_5.csv` hiện có cùng nội dung, mỗi tệp 19
dòng. Chúng giúp kiểm tra thao tác và luồng chạy; sáu tệp này không đại diện
cho sáu chuỗi độc lập. Chúng không có cột nhãn, cũng không bao phủ hai timestamp
NAB được khai báo trong mã. Vì vậy không dùng chúng để khẳng định độ chính xác
của thuật toán.

Có thể tải thêm dữ liệu NAB bằng hàm bên dưới, chạy trong thư mục dự án con.
Thao tác cần Internet; file tải về chưa có nhãn đánh giá đi kèm.

```python
from src.data_prep import download_nab_dataset

path = download_nab_dataset("ec2_cpu_utilization")
print(path)
```

Tên dữ liệu được hỗ trợ: `ec2_cpu_utilization`, `machine_temperature`,
`network_traffic`. Mỗi chuỗi cần nhãn đúng với nguồn và khoảng thời gian của
nó. Hai nhãn điểm mặc định của CPU không áp dụng cho các chuỗi khác.

Các hướng dẫn và báo cáo cũ ở thư mục gốc có thể dùng cấu hình khác. Khi trình
bày theo notebook hiện tại, dùng bộ `reports/notebook_reference/` và nêu rõ
phạm vi MAD toàn bộ chuỗi so với IF/LOF chỉ trên test.
