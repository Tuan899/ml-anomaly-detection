# Hướng dẫn giao diện ANOMALY LAB

ANOMALY LAB kiểm tra hoạt động MySQL qua năm chỉ số: truy vấn mỗi giây, kết nối đang mở, thời gian phản hồi, truy vấn chậm và kết nối thất bại. Ứng dụng giúp tìm thời điểm cần kiểm tra; một cảnh báo chưa chứng minh được nguyên nhân sự cố.

## Chạy ứng dụng

Mở hai terminal PowerShell tại thư mục `ml-anomaly-detection`. Dùng Python từ môi trường đã cài `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

Terminal thứ nhất:

```powershell
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Terminal thứ hai:

```powershell
python -m streamlit run frontend/app.py
```

Mở địa chỉ Streamlit in trong terminal, thường là `http://localhost:8501`. Giữ cả hai terminal đang chạy. Nếu dùng môi trường ảo, thay `python` trong cả hai lệnh bằng đường dẫn Python của môi trường đó. Xem [README](../README.md) nếu đã có môi trường ảo tại `C:\Users\User\DACN\.venv`.

## Demo nhanh: ba bước

Giao diện mặc định là **Cơ bản**. Người dùng không cần chọn thuật toán, cột dữ liệu hoặc tỷ lệ huấn luyện.

1. **Chọn dữ liệu.** Giữ **Dùng dữ liệu mẫu**, chọn **Hoạt động bình thường**.
2. **Phân tích.** Bấm **Bắt đầu phân tích** và đợi các bước đọc dữ liệu, chuẩn bị, phân tích và tổng hợp hoàn tất.
3. **Đọc kết quả.** Xem trạng thái, số bản ghi cần chú ý, biểu đồ và các thời điểm được đánh dấu. Bấm **Tải báo cáo** để lưu phần giải thích và kết quả của lần chạy.

Tiếp theo, bấm **Phân tích dữ liệu khác**, chọn **Hoạt động bất thường** rồi chạy lại. Rê chuột lên biểu đồ để đọc thời điểm và giá trị thực tế. Mở bảng thời điểm đáng chú ý để đối chiếu chỉ số thay đổi với mức tham chiếu.

Hai bộ mẫu là dữ liệu tổng hợp tái lập được trong `data/mysql_normal.csv` và `data/mysql_anomalous.csv`. Nhãn ghi nhận các sự kiện được chèn vào dữ liệu, không phải dự đoán của thuật toán. Hiệu quả trên bộ mẫu không bảo đảm hiệu quả trên máy chủ thực.

## Đọc ba câu trả lời trên màn hình

| Câu hỏi | Nơi xem |
|---|---|
| MySQL có dấu hiệu bất thường không? | Thẻ trạng thái và câu kết luận ở đầu kết quả. |
| Bất thường xuất hiện khi nào, biểu hiện gì? | Điểm đánh dấu trên biểu đồ và bảng thời điểm đáng chú ý. |
| Cần kiểm tra gì tiếp theo? | Mục **Vì sao hệ thống đưa ra cảnh báo?** và gợi ý kiểm tra tương ứng. |

**Bình thường** nghĩa là chưa có cảnh báo theo cấu hình và phạm vi dữ liệu đang phân tích. **Cần chú ý** nghĩa là có dấu hiệu đáng kiểm tra. **Cảnh báo cao** dựa trên quy tắc vận hành được giải thích trong kết quả; màu sắc luôn đi kèm chữ mô tả.

Đường biểu đồ nhấp nhô là giá trị đo thay đổi theo thời gian. Một thay đổi nhỏ như 50 lên 51 không tự động trở thành sự cố. Mô hình học đặc điểm hoạt động từ giai đoạn tham chiếu; bộ lọc cảnh báo vận hành là một chính sách riêng, được trình bày trong phần kỹ thuật.

Điểm bất thường là điểm quyết định của mô hình, không phải xác suất máy chủ đang lỗi. Điểm của các thuật toán khác nhau không có cùng thang đo. Các chỉ số lệch nền là dấu hiệu có thể kiểm chứng, chưa phải nguyên nhân đã xác minh. Quản trị viên cần đối chiếu log truy vấn, lịch tác vụ, phiên kết nối, khóa và tài nguyên máy chủ.

## So sánh hai bộ dữ liệu

Chọn **So sánh hai bộ dữ liệu** trên trang hoặc **So sánh dữ liệu** ở thanh bên, giữ dữ liệu mẫu rồi bấm **Bắt đầu phân tích**.

Màn hình đặt bộ bình thường bên trái và bộ có dấu hiệu bất thường bên phải. Đối chiếu lượng bản ghi, truy vấn, kết nối, độ trễ, điểm bất thường và các khoảng thời gian đáng chú ý. Bảng so sánh thống kê cùng biểu đồ giúp thấy mức thay đổi.

Hai bộ được đánh giá bằng cùng mô hình và cách chuẩn hóa học từ phần huấn luyện của bộ bình thường. Nhãn kiểm thử không tham gia huấn luyện. Việc một giá trị lớn hơn bộ còn lại chưa đủ để kết luận bất thường; kết luận dựa trên dự đoán và bằng chứng so với nền tham chiếu chung.

## Tải CSV và kết nối MySQL

Chọn **Tải tệp CSV** nếu đã có số đo. Giao diện tự nhận diện cột phổ biến và báo rõ các cột còn thiếu. Định dạng chuẩn:

```csv
timestamp,queries_per_second,connections,response_time_ms,slow_queries,connection_errors
2026-01-01T08:00:00Z,50,20,8.2,0,0
2026-01-01T08:01:00Z,51,21,8.4,0,0
```

Ví dụ hai dòng chỉ minh họa định dạng. Cần chuỗi dữ liệu dài hơn để phân tích, với giai đoạn đầu đại diện cho hoạt động tham chiếu. Giá trị chỉ số phải là số hữu hạn, không âm; thời gian phải hợp lệ, duy nhất. Dùng số sự kiện phát sinh trong khoảng lấy mẫu cho truy vấn chậm và kết nối thất bại. Có thể bổ sung nhãn `label` theo quy ước `1` bình thường, `-1` bất thường khi có bằng chứng độc lập.

Trong chế độ so sánh CSV, tải riêng bộ bình thường và bộ cần đối chiếu. Giữ cùng ý nghĩa chỉ số, đơn vị và chu kỳ lấy mẫu giữa hai tệp để so sánh có ý nghĩa.

Chọn **Kết nối MySQL** để thu một đợt số liệu thực tế. Nhập tài khoản chỉ đọc, thông tin kết nối và cấu hình lấy mẫu, rồi bấm **Bắt đầu phân tích**. Ở chế độ Cơ bản, một lần bấm sẽ thu mẫu rồi phân tích; việc chọn nguồn hoặc nhập mật khẩu chưa tự kết nối. Chế độ so sánh dùng hai bộ mẫu hoặc hai CSV. Xem [thiết lập MySQL](MYSQL_SETUP.md) để chuẩn bị tài khoản và TLS. Độ trễ đo trực tiếp là thời gian khứ hồi của `SELECT 1`, không phải thời gian trung bình của mọi truy vấn nghiệp vụ. Dữ liệu thực không tự có nhãn kiểm thử.

## Nghiên cứu và đánh giá trong chế độ Nâng cao

Chọn **Nâng cao** ở thanh bên để sử dụng toàn bộ luồng nghiên cứu hiện có. Chọn **Giám sát hệ quản trị CSDL MySQL** hoặc **CSV một chỉ số / notebook NAB**.

Trong luồng MySQL, có thể chọn một hoặc nhiều thuật toán MAD, Isolation Forest, LOF, One-Class SVM; thay tỷ lệ huấn luyện, tham số, cột thời gian, nhãn và chính sách cảnh báo. Hãy giữ cùng cấu hình khi so sánh hiệu quả giữa các bộ kiểm thử.

Nếu CSV có tên cột riêng, mở **Cấu hình cột thời gian và cột đặc trưng**, bật **Ánh xạ tên cột nguồn sang các chỉ số MySQL** và chọn một cột thời gian cùng năm cột chỉ số. Mỗi cột nguồn chỉ được chọn một lần. Ánh xạ đổi tên cho lần phân tích; không tự đổi đơn vị, không biến bộ đếm tích lũy thành số phát sinh và không sửa tệp gốc.

Quy trình đánh giá trước giảng viên:

1. Chọn bộ **Hoạt động bình thường**, nhãn `label`, bốn thuật toán và chạy. Trong **Đánh giá**, xem số cảnh báo nhầm. Bộ không có bất thường thật chưa đo được khả năng phát hiện qua Recall.
2. Chọn bộ **Hoạt động bất thường**, giữ nguyên cấu hình và chạy lại. Đối chiếu thời điểm phát hiện với các kịch bản trong `data/mysql_demo_manifest.json`.
3. Trong **Đánh giá**, đọc Precision, Recall, F1-score và confusion matrix. So sánh cả **Dự đoán mô hình gốc** và **Cảnh báo sau lọc** để thấy tác động của chính sách vận hành.
4. Đọc bảng so sánh bốn thuật toán: cảnh báo đúng, cảnh báo nhầm, bỏ sót và thời gian xử lý. Nhiều cảnh báo hơn chưa chứng minh thuật toán tốt hơn.
5. Xuất CSV/JSON để kiểm tra lại từng dự đoán, nhãn, chỉ số và cấu hình thực sự đã chạy.

Precision trả lời “trong các cảnh báo, bao nhiêu cảnh báo đúng”; Recall trả lời “trong các bất thường có nhãn, tìm được bao nhiêu”; F1 cân bằng hai chỉ số này. Confusion matrix ghi số bình thường đúng, cảnh báo nhầm, bỏ sót và cảnh báo đúng. Accuracy có thể rất cao khi dữ liệu có quá ít bất thường, nên cần đọc cùng các chỉ số còn lại.

Khi không có nhãn tham chiếu hợp lệ, giao diện không tạo Precision, Recall, F1, Accuracy hoặc confusion matrix giả. Việc huấn luyện và dự đoán vẫn chạy không giám sát. Nhãn và tên kịch bản không được dùng làm đặc trưng học máy.

Xem [demo kỹ thuật MySQL](DEMO_MYSQL.md) để đọc cách chia theo thời gian, công thức lọc dao động và các lệnh tái lập. Luồng notebook tham chiếu vẫn giữ rõ phạm vi MAD mô tả toàn chuỗi và IF/LOF kiểm thử theo thời gian.

## Khi đổi dữ liệu hoặc có lỗi

Sau khi đổi nguồn hoặc cấu hình, phải chạy phân tích lại. Kết quả cũ được ẩn để tránh hiểu nhầm là kết quả của dữ liệu mới. Nút **Phân tích dữ liệu khác** đưa về bước chọn dữ liệu.

Nếu không kết nối được API, kiểm tra terminal FastAPI và địa chỉ `ANOMALY_API_URL`. Giao diện không thay thế lỗi bằng dự đoán giả hoặc tự huấn luyện cục bộ. Nếu CSV dùng tên cột riêng, đổi tên theo định dạng chuẩn hoặc ánh xạ trong Nâng cao. Nếu thật sự thiếu số đo, cần bổ sung dữ liệu. Chế độ MySQL cần đủ năm chỉ số; Nâng cao có luồng CSV một chỉ số riêng khi dữ liệu chỉ chứa một đại lượng.

## Các phần mã nguồn của giao diện

| Tệp | Chức năng |
|---|---|
| `frontend/app.py` | Chọn Cơ bản/Nâng cao, áp dụng giao diện và giữ luồng nghiên cứu cũ. |
| `frontend/monitoring_workspace.py` | Ba bước Cơ bản, so sánh dữ liệu, kết luận, biểu đồ và tải báo cáo. |
| `frontend/input_data.py` | Nhận diện tên cột CSV và kiểm tra đầu vào cho chế độ Cơ bản. |
| `frontend/monitoring_charts.py` | Biểu đồ điểm bất thường, số bản ghi và đối chiếu hai bộ dữ liệu. |
| `frontend/reporting.py` | Báo cáo tiếng Việt từ dự đoán và bằng chứng thực tế của lần chạy. |
| `frontend/dbms_dashboard.py` | Nghiên cứu MySQL Nâng cao, cấu hình, bằng chứng, đánh giá và xuất kết quả. |
| `frontend/api_client.py` | Gọi API và kiểm tra kết quả trước khi trình bày. |
| `src/dbms_comparison.py`, `backend/api.py` | So sánh hai bộ bằng cùng mô hình và bộ chuẩn hóa học một lần từ phần tham chiếu; cung cấp API `/compare`. |
| `src/monitoring_summary.py` | Tổng hợp trạng thái, mức cảnh báo, bằng chứng và các phép đánh giá. |
| `tests/test_monitoring_workspace.py` | Kiểm tra luồng Cơ bản với API và mô hình thực qua ASGI. |
| `tests/test_input_data.py` | Kiểm tra nhận diện cột, dữ liệu lỗi, nhãn, đơn vị và bảo toàn dữ liệu CSV. |

Thuật toán và pipeline vẫn ở phía backend. Báo cáo chỉ chứa số liệu của lần chạy thành công hiện tại; không sử dụng bảng điểm chép sẵn.
