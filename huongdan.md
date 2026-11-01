# Hướng dẫn chạy ứng dụng phát hiện bất thường

Ứng dụng giúp tải CSV theo thời gian, chọn chỉ số cần phân tích, chạy bốn
thuật toán phát hiện bất thường, xem biểu đồ và xuất kết quả. Dữ liệu được
chia theo thời gian: học từ phần đầu, dự đoán trên phần sau.

Xem [hướng dẫn đầy đủ và giải thích mã nguồn](./DACN/ml-anomaly-detection/README.md)
để hiểu từng module, định dạng CSV, thuật toán, kết quả và API.

## Khởi chạy giao diện trên Windows

Mở PowerShell tại `C:\Users\User\DACN`. Cần Python 3.10 trở lên.
Nếu đã có môi trường `.venv`, bỏ qua lệnh tạo môi trường.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\DACN\ml-anomaly-detection\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run .\DACN\ml-anomaly-detection\frontend\app.py
```

Mở địa chỉ xuất hiện trong terminal, thường là `http://localhost:8501`.
Chọn nguồn dữ liệu, kiểm tra cột thời gian và cột giá trị, rồi bấm
**Chạy phát hiện**. Sau khi đổi dữ liệu hoặc cấu hình, chạy lại để cập nhật.

## Chuẩn bị CSV

Tệp cần một cột thời gian hợp lệ, không trùng và một cột chỉ số dạng số.
Tên cột mặc định là `timestamp` và `value`; có thể chọn tên khác trên
giao diện. Dung lượng tải lên tối đa 10 MiB.

```csv
timestamp,value
2026-01-01 08:00:00,10.2
2026-01-01 08:05:00,10.5
2026-01-01 08:10:00,10.1
2026-01-01 08:15:00,10.3
2026-01-01 08:20:00,18.7
2026-01-01 08:25:00,10.4
```

Chỉ chọn cột nhãn thật khi có dữ liệu đã được xác minh, theo quy ước
**1 = bình thường, -1 = bất thường**. Khi không có nhãn, ứng dụng vẫn phát
hiện và hiển thị cảnh báo; Precision, Recall và F1 không được tính.

Các tệp mẫu `cpu_0.csv` đến `cpu_5.csv` hiện cùng chứa 19 dòng và không
có nhãn. Dữ liệu này phù hợp để thử thao tác; chưa đủ để kết luận chất lượng
phát hiện. Ứng dụng hiện phân tích CSV ngoại tuyến, chưa giám sát cơ sở dữ
liệu thời gian thực.

## Chạy API

Mở terminal thứ hai tại thư mục gốc và chạy:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --app-dir .\DACN\ml-anomaly-detection --reload
```

Mở `http://127.0.0.1:8000/docs` để thử API. Hướng dẫn tham số và ví dụ
tích hợp nằm trong [README của ứng dụng](./DACN/ml-anomaly-detection/README.md).
