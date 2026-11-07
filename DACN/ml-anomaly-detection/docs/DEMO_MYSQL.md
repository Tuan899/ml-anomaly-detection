# Demo nghiên cứu phát hiện bất thường trong hoạt động hệ quản trị CSDL

Đề tài: **NGHIÊN CỨU THUẬT TOÁN PHÁT HIỆN BẤT THƯỜNG TRONG HOẠT ĐỘNG CỦA HỆ QUẢN TRỊ CƠ SỞ DỮ LIỆU**.

Ứng dụng hỗ trợ DBA tìm dấu hiệu quá tải, truy vấn bất thường, kết nối tăng và suy giảm hiệu năng. Cảnh báo là dấu hiệu cần kiểm tra, không xác nhận lỗi hoặc nguyên nhân.

Giao diện mặc định mới là **Cơ bản** với ba bước và chức năng so sánh hai bộ dữ liệu;
xem [hướng dẫn giao diện mới](INTERFACE_GUIDE.md) để demo nhanh. Các thao tác cấu hình
thuật toán và đánh giá chi tiết ở mục 2–6 bên dưới bắt đầu bằng chọn **Nâng cao**
trên thanh bên; luồng nghiên cứu và dữ liệu kiểm thử vẫn được giữ.

## 1. Cài đặt và khởi động

Mở PowerShell tại thư mục `ml-anomaly-detection`. Dùng Python 3.10 trở lên:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Terminal thứ nhất, cùng thư mục:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Terminal thứ hai:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Mở `http://localhost:8501`. API kiểm tra: `http://127.0.0.1:8000/health`; tài liệu API: `http://127.0.0.1:8000/docs`. Nếu dùng môi trường ảo có sẵn thì dùng đường dẫn Python của môi trường đó cho cả hai terminal.

Mô hình chạy ở FastAPI. Nếu backend tắt hoặc lỗi, giao diện báo lỗi, xóa kết quả lần chạy trước và không tạo dự đoán thay thế. CSV vẫn xem trước được khi backend tắt. Nếu API dùng cổng khác, đặt `ANOMALY_API_URL` trong terminal Streamlit trước khi khởi động.

## 2. Demo bộ hoạt động bình thường

1. Giữ chế độ **Giám sát hệ quản trị CSDL MySQL**, chọn **Dữ liệu kiểm thử MySQL → Hoạt động bình thường**.
2. Mở **Xem trước và tải dữ liệu đầu vào**. Có thể tải CSV rồi thử lại qua **Tải CSV MySQL** để minh chứng luồng nhập tệp.
3. Chọn thời gian `timestamp`, nhãn `label`, đủ bốn thuật toán; train **70%**, tỷ lệ bất thường dự kiến **1%**, bật lọc dao động, ngưỡng **3,5**.
4. Bấm **Chạy phát hiện**. Đọc trạng thái theo cấu hình hiện tại, biểu đồ từng chỉ số và bảng so sánh số cảnh báo gốc/sau lọc.
5. Trong tab **Đánh giá**, xem số **FP** trên bộ bình thường. Không có bất thường thật nên Recall/F1 không đo được khả năng phát hiện; giá trị 0 theo quy ước không có nghĩa mô hình bỏ sót sự cố.

Tệp `data/mysql_normal.csv` có 1.440 mẫu cách nhau một phút, dao động chu kỳ và nhiễu tự nhiên được tạo với seed cố định. Không có sự kiện bất thường được chèn. Tên `normal` chỉ mô tả nhãn thiết kế, không ép mô hình phải trả kết quả bình thường.

## 3. Demo bộ có bất thường

1. Chuyển sang **Hoạt động bất thường**. Kết quả cũ được ẩn cho đến khi chạy lại.
2. Giữ nguyên cấu hình và bấm **Chạy phát hiện**. Mô hình học 1.008 mẫu đầu, dự đoán 432 mẫu cuối. Hai bộ có cùng phần nền huấn luyện bình thường; 146 mẫu sự kiện chỉ xuất hiện trong phần kiểm tra.
3. Trong **Tổng quan**, lần lượt chọn bốn thuật toán và các chỉ số. Rê chuột tại điểm × đỏ để đọc cả năm giá trị thực tế, kể cả khi chỉ số đang vẽ chưa tăng.
4. Trong **Chi tiết**, chọn thời điểm cảnh báo. Đọc giá trị thực tế, độ lệch so với trung vị train và chỉ số vượt ngưỡng. Đối chiếu thời gian với các sự kiện sau:

| Tình huống tổng hợp | Thời gian UTC ngày 01/10/2026 | Chỉ số được tác động |
|---|---|---|
| `query_spike` | 17:31–18:04 | QPS |
| `connection_spike` | 18:57–19:31 | Kết nối |
| `latency_spike` | 20:24–20:57 | Thời gian phản hồi |
| `combined_pressure` | 21:59–22:41 | Cả năm chỉ số |

5. Mở **Đánh giá**, so sánh **Cảnh báo sau lọc** với **Dự đoán mô hình gốc**. Đọc Precision, Recall, F1-score và TP/FP/FN/TN cùng confusion matrix cho từng thuật toán. Thuật toán bỏ sót vẫn phải hiển thị đúng FN; không thay nhãn hay điều chỉnh kết quả để có chỉ số đẹp.
6. Tải dự đoán CSV và kết quả/cấu hình JSON. CSV có toàn bộ 432 mẫu test, giá trị thật, dự đoán gốc, cảnh báo sau lọc và bằng chứng; không bị giới hạn theo bộ lọc bảng.

Hai tệp là **dữ liệu tổng hợp kiểm thử**, không phải số đo từ máy chủ thật. Các đợt tăng được cố ý tách rõ để kiểm tra luồng hoạt động; điểm tốt trên dữ liệu này chưa chứng minh khả năng tổng quát. Khoảng thời gian và nhãn được ghi trong `data/mysql_demo_manifest.json`; không suy ra từ dự đoán của mô hình.

Biểu đồ mặc định chỉ hiện **Giai đoạn kiểm tra** để dễ đọc. Đường xanh là giá trị đo thực tế; vùng xanh lá là khoảng tham chiếu đã học từ train, không phải khoảng tin cậy hoặc ngưỡng quyết định riêng của thuật toán. Dòng trạng thái ghi rõ thuật toán đang chọn có bao nhiêu cảnh báo; không có dấu đỏ nghĩa là thuật toán đó chưa cảnh báo trên phần kiểm tra. Chọn **Toàn bộ dữ liệu** để xem thêm giai đoạn học và vạch chia có ghi tên. Bật **Hiện nhãn kiểm thử** khi muốn đối chiếu với sự kiện đã gắn nhãn.

## 4. Hiểu cơ sở cảnh báo và tránh nhầm dao động nhỏ

Bốn thuật toán gốc được giữ nguyên. Tất cả học năm chỉ số từ train, chuẩn hóa theo train rồi dự đoán test theo thời gian; `label` và `scenario` không là đặc trưng. Không học trung vị, thang đo hoặc ngưỡng từ phần test.

Trong chế độ MySQL, khi bật bộ lọc, cảnh báo yêu cầu **mô hình dự đoán bất thường và ít nhất một chỉ số vượt dung sai nền huấn luyện**:

```text
sigma = max(1,4826 × MAD_train, IQR_train / 1,349)
dung_sai = max(ngưỡng × sigma, dung_sai_tối_thiểu, 5% × |trung_vị_train|)
cảnh_báo = dự_đoán_gốc_bất_thường AND có |giá_trị − trung_vị_train| > dung_sai
```

Dung sai tối thiểu cho demo: QPS **2**, kết nối **2**, phản hồi **5 ms**, truy vấn chậm **1 sự kiện/khoảng**, kết nối thất bại **0**. Nếu nền không có lỗi, xuất hiện lỗi mới là một quy tắc cần xem xét rõ ràng; vẫn cần mô hình gắn cờ để thành cảnh báo. Với nền 50 ổn định, tăng lên 51 không vượt dung sai mặc định. Thay đổi vượt ngưỡng có thể là tăng hoặc giảm.

Mở bảng nền train để xem median, MAD, sigma và biên cụ thể. Điểm lệch theo ngưỡng là chỉ số giải thích chính sách vận hành, không phải xác suất hay điểm gốc của mô hình. Mức dung sai là giả định demo, cần hiệu chỉnh theo đơn vị, khoảng lấy mẫu và hệ thống thật. Thanh ngưỡng cho phép thay độ nhạy; tắt lọc để nghiên cứu kết quả gốc. Lọc có thể làm bỏ sót bất thường nhỏ hoặc bất thường chỉ thể hiện qua tương quan đa chỉ số, vì vậy phải báo cáo cả kết quả gốc.

Số QPS/kết nối tăng chỉ **gợi ý** tải tăng; độ trễ/truy vấn chậm tăng chỉ **gợi ý** suy giảm hiệu năng. Kiểm tra log truy vấn, lịch batch, số phiên, khóa, CPU/I/O và sự kiện triển khai trước khi kết luận. Ứng dụng không tự kết luận bị tấn công, lỗi truy vấn hoặc nghẽn tài nguyên từ năm chỉ số này.

## 5. CSV của bạn và dữ liệu thực MySQL

CSV cần cột thời gian cùng năm cột sau. Có thể thêm `label` hoặc `is_anomaly` khi có nhãn được kiểm chứng bên ngoài:

```csv
timestamp,queries_per_second,connections,response_time_ms,slow_queries,connection_errors,label
2026-01-01T08:00:00Z,50,20,8.2,0,0,1
2026-01-01T08:01:00Z,51,21,8.4,0,0,1
```

Ví dụ trên chỉ minh họa cấu trúc; cần nhiều mẫu hơn để chạy. Các số phải hữu hạn, không âm; timestamp duy nhất, hợp lệ. Timestamp không có múi giờ được hiểu là UTC; dữ liệu được sắp xếp trước khi chia. Chế độ MySQL từ chối dữ liệu lỗi thay vì tự điền 0 hoặc bỏ hàng âm thầm. Giới hạn CSV là 10 MiB. Giữ chu kỳ lấy mẫu nhất quán và dùng số phát sinh trong khoảng cho hai cột sự kiện, không dùng bộ đếm tích lũy từ lúc server khởi động.

Để demo trực tiếp, chọn **Kết nối MySQL**, nhập tài khoản giám sát, thu mẫu rồi bấm **Chạy phát hiện**. Mặc định thu 60 mẫu với khoảng 1 giây; nên thu nhiều mẫu/chu kỳ đại diện hơn để nghiên cứu chất lượng. Chuẩn bị tài khoản ít quyền, TLS và hiểu cách đo trong [MYSQL_SETUP.md](MYSQL_SETUP.md).

Thu trực tiếp chỉ đọc `SHOW GLOBAL STATUS` và thăm dò `SELECT 1`; không truy cập bảng nghiệp vụ. Độ trễ là thời gian khứ hồi probe, không phải trung bình mọi truy vấn. Dữ liệu thật không tự có nhãn: giao diện không tạo Precision/Recall/F1 hay confusion matrix nếu chưa có nhãn. Đây là thu theo đợt để phân tích; chưa phải dịch vụ cảnh báo chạy liên tục.

## 6. Tái lập và đánh giá bằng lệnh

Chạy từ thư mục dự án:

```powershell
.\.venv\Scripts\python.exe scripts/generate_mysql_demo.py
.\.venv\Scripts\python.exe scripts/evaluate_mysql_demo.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Lệnh đầu tái tạo đúng hai CSV và manifest bằng seed `20261107`. Lệnh thứ hai thực sự huấn luyện mô hình và ghi `reports/mysql_demo/comparison.csv`, `evaluation.json` cùng dự đoán từng tệp. Không có bảng điểm được chép sẵn. Báo cáo ghi hash tệp, phiên bản thư viện, tham số và thời điểm chạy để đối chiếu. Khi thay seed hoặc tham số, phải chạy lại và báo cáo kết quả mới.

API vẫn giữ chế độ CSV một chỉ số và notebook cũ. Ví dụ thêm chế độ nghiên cứu MySQL:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/detect?analysis_mode=dbms&value_col=queries_per_second&label_col=label&include_context=true" -F "file=@data/mysql_anomalous.csv"
```

Các tham số mới: `analysis_mode=dbms`, `noise_guard=true/false`, `deviation_threshold=3.5` (API cho phép 1–10). `value_col` chọn chỉ số đại diện; mô hình vẫn dùng đủ năm chỉ số. Nhãn chỉ được dùng khi chỉ định `label_col`. `*_raw_prediction` và `*_score` giữ nguyên kết quả mô hình; `*_prediction` là cảnh báo vận hành. Metadata chứa cả hai nhóm kết quả đánh giá và confusion matrix.

Để tiếp tục chức năng cũ, chọn **Nâng cao → CSV một chỉ số / notebook NAB** trên giao diện. Notebook tham chiếu vẫn giữ quy trình gốc và ghi rõ MAD mô tả toàn chuỗi; không dùng kết quả đó thay cho đánh giá độc lập chế độ MySQL.
