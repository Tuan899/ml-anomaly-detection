# Phát hiện bất thường trong chuỗi thời gian

Ứng dụng đọc dữ liệu CSV theo thời gian, học trạng thái thường gặp từ phần dữ
liệu đầu và đánh dấu các điểm có dấu hiệu bất thường ở phần dữ liệu sau. Người
dùng có thể xem biểu đồ, so sánh bốn thuật toán và tải kết quả CSV hoặc JSON.

Phạm vi hiện tại là phân tích CSV ngoại tuyến. Dự án chưa có kết nối trực tiếp
đến hệ quản trị cơ sở dữ liệu hoặc thu thập chỉ số thời gian thực. Một cảnh báo
của mô hình cần được người dùng kiểm tra theo ngữ cảnh thực tế.

## Chạy trên Windows từ thư mục gốc

Các lệnh dưới đây chạy trong PowerShell tại `C:\Users\User\DACN`. Cần Python
3.10 trở lên và Streamlit 1.65 trở lên theo `requirements.txt`. Nếu đã có môi
trường `.venv`, bỏ qua lệnh tạo môi trường.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\DACN\ml-anomaly-detection\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run .\DACN\ml-anomaly-detection\frontend\app.py
```

Mở địa chỉ Streamlit in trong terminal, thường là
`http://localhost:8501`. Cách gọi Python trực tiếp ở trên không yêu cầu kích
hoạt môi trường ảo.

Để chạy API, mở terminal thứ hai tại cùng thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --app-dir .\DACN\ml-anomaly-detection --reload
```

Trang thử API: `http://127.0.0.1:8000/docs`. Endpoint kiểm tra trạng thái:
`GET /health`.

## Cách sử dụng giao diện

1. Chọn dữ liệu mẫu có sẵn hoặc tải CSV của bạn, tối đa 10 MiB.
2. Chọn cột thời gian và cột chỉ số cần phân tích, chẳng hạn CPU hoặc độ trễ.
3. Nếu CSV có nhãn đã xác minh, chọn cột nhãn để đánh giá chất lượng.
4. Chọn thuật toán và tỷ lệ dữ liệu huấn luyện. Mặc định dùng 70% dữ liệu đầu
   để huấn luyện, 30% dữ liệu cuối để kiểm tra.
5. Bấm **Chạy phát hiện**, xem biểu đồ và bảng chi tiết của từng thuật toán.
6. Tải dự đoán CSV hoặc kết quả JSON để lưu lại lần chạy.

Kết quả được chia thành các tab tổng quan, chi tiết, đánh giá và hướng dẫn.
Sau khi đổi dữ liệu hoặc cấu hình, kết quả cũ được ẩn; chạy lại để cập nhật.
Tùy chọn giao diện sáng/tối áp dụng cho cả trang và biểu đồ.

Ảnh giao diện đã kiểm tra trên trình duyệt:
[chế độ sáng](./report_assets/dashboard-light-results.png),
[chế độ tối](./report_assets/dashboard-dark-results.png),
[màn hình điện thoại](./report_assets/dashboard-mobile-results.png).

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

Ví dụ chạy từ thư mục gốc:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/detect" -F "file=@DACN/ml-anomaly-detection/data/cpu_0.csv"
```

JSON trả về gồm `metadata` (cấu hình, làm sạch, cảnh báo, thời gian chạy),
`predictions` (dự đoán trên tập kiểm tra), `anomalies` (điểm được gắn cờ theo
thuật toán) và `metrics` (khi đã chọn nhãn).

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
| `frontend/app.py` | Giao diện Streamlit: chọn dữ liệu, cấu hình, chạy phân tích, xem và tải kết quả. |
| `frontend/helpers.py` | Chọn cột số phù hợp và chuyển thông báo kiểm tra dữ liệu sang hướng dẫn tiếng Việt. |
| `backend/api.py` | Nhận yêu cầu HTTP, giới hạn dung lượng file và trả kết quả JSON. |
| `src/pipeline.py` | Luồng xử lý dùng chung: làm sạch, chia theo thời gian, chạy mô hình, tổng hợp kết quả. |
| `src/data_prep.py` | Kiểm tra CSV, xử lý timestamp, tạo đặc trưng lịch, thống kê MAD và tải dữ liệu NAB. |
| `src/models.py` | Tạo ma trận đặc trưng, chuẩn hóa theo train, chạy mô hình, đánh giá và chọn tham số trên tập validation riêng. |
| `src/eda.py` | Vẽ chuỗi thời gian và thống kê mô tả theo giờ, ngày trong tuần. |
| `src/anomaly_detection.py` | Chạy phân tích NAB CPU từ terminal, dùng cùng pipeline và cách chia theo thời gian. |
| `notebooks/exploratory.ipynb` | Khảo sát dữ liệu, chạy bốn mô hình và giải thích giới hạn đánh giá qua từng bước. |

Luồng chính: **CSV → kiểm tra/làm sạch → chia train/test theo thời gian →
huấn luyện trên train → dự đoán trên test → biểu đồ, đánh giá, xuất kết quả**.

Notebook chạy được khi mở từ thư mục gốc, dự án con hoặc `notebooks/`. Với mẫu
19 dòng hiện có, nó chia 13 dòng huấn luyện và 6 dòng kiểm tra; không hiển thị
bảng đánh giá F1 khi tập kiểm tra thiếu điểm bất thường được chú giải.

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

Từ thư mục gốc, chạy các kiểm thử pipeline, API và luồng thao tác Streamlit:

```powershell
Push-Location .\DACN\ml-anomaly-detection
& ..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
```

Các kiểm thử dùng dữ liệu nhỏ để kiểm tra tính đúng của chương trình, không
đánh giá chất lượng thuật toán trên một bộ dữ liệu thực nghiệm đầy đủ.

## Dữ liệu mẫu và giới hạn thực nghiệm

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

Các hướng dẫn và báo cáo ở thư mục gốc có thể mô tả phiên bản cũ. Trước khi
đưa kết quả notebook hoặc script riêng vào báo cáo, cần xác nhận số dòng,
khoảng thời gian, nguồn nhãn và cách chia tập từ dữ liệu thực tế.
