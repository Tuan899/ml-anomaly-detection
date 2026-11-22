# Dữ liệu minh họa cho 4 thuật toán

Bốn CSV trong `resources/algorithm_datasets/` là dữ liệu MySQL **giả lập**.
Tên file thể hiện khái niệm muốn minh họa. Cả bốn thuật toán đều có thể chạy
trên từng file, không có cam kết thuật toán cùng tên sẽ đạt kết quả cao nhất.

| File | Dữ liệu bình thường | Bất thường được chèn |
|---|---|---|
| `MAD.csv` | QPS quanh 50, các chỉ số khác ổn định | QPS tăng lên 150–262 hoặc giảm còn 6 hay 8; các chỉ số khác giữ nguyên |
| `Isolation_Forest.csv` | Ba mức tải thông thường với QPS quanh 80, 160 và 260 | QPS, kết nối, độ trễ và số sự kiện cùng tăng mạnh |
| `LOF.csv` | Một cụm dày quanh QPS 100/kết nối 40/độ trễ 15 ms và một cụm thưa quanh 210/85/40 ms | Điểm nằm ngoài cụm dày nhưng chưa vượt khoảng giá trị chung của cả dữ liệu |
| `One_Class_SVM.csv` | QPS và kết nối phụ thuộc mức tải `t`; độ trễ có quan hệ cong `15 + 3*t²` | QPS/kết nối ở mức giữa nhưng độ trễ cao, phá vỡ quan hệ đã mô phỏng |

Mỗi file có **1.000 dòng** cách nhau một phút, bắt đầu lúc 00:00 ngày
01/11/2026 theo UTC+07:00. Đây là thời gian giả định cho mô phỏng.
**700 dòng đầu bình thường** dành cho huấn luyện. **300 dòng cuối** gồm
285 dòng bình thường và **15 điểm bất thường** đã chèn trước khi chạy mô hình.
Không tạo nhãn từ dự đoán của thuật toán.

## Cách dùng trong ứng dụng

1. Chọn **Nâng cao → Giám sát hệ quản trị CSDL → Tải CSV**, rồi tải một CSV trong thư mục trên.
2. Chọn cột thời gian `timestamp`, nhãn `label`, tỷ lệ huấn luyện **70%**.
3. Chọn thuật toán cùng tên file để xem minh họa, hoặc chọn cả bốn để đối chiếu.
4. Giữ tỷ lệ bất thường dự kiến **1%**, không thêm đặc trưng thời gian.
5. Trong **Ngưỡng cảnh báo vận hành**, bỏ chọn **Lọc dao động nhỏ theo thống kê và dung sai** để xem trực tiếp hành vi thuật toán.
   Bộ lọc này yêu cầu từng chỉ số lệch đủ lớn so với mức nền nên có thể che mất
   bất thường cục bộ của LOF hoặc bất thường quan hệ của SVM. Nếu bật bộ lọc,
   hãy xem cả dự đoán gốc và dự đoán sau lọc.

Chế độ MySQL luôn đưa đủ năm chỉ số vào mô hình. Chỉ số được chọn để vẽ biểu đồ
không làm thay đổi đầu vào mô hình. Nếu dùng chế độ CSV một chỉ số trong màn hình
phân tích thông thường, chọn `queries_per_second` cho MAD; cách này không giữ
đủ quan hệ để minh họa hai file LOF/SVM.

## Các cột

| Cột | Ý nghĩa |
|---|---|
| `timestamp` | Thời gian lấy mẫu, có múi giờ `+07:00` |
| `queries_per_second` | Truy vấn/giây trong khoảng lấy mẫu |
| `connections` | Số kết nối đang hoạt động |
| `response_time_ms` | Độ trễ thăm dò giả lập, đơn vị ms |
| `slow_queries` | Số truy vấn chậm trong một phút, không phải bộ đếm tích lũy |
| `connection_errors` | Số kết nối thất bại trong một phút, không phải bộ đếm tích lũy |
| `label` | `1` bình thường; `-1` là điểm được chèn bất thường |
| `scenario` | Mô tả kịch bản của dòng |

Nhãn và kịch bản không phải đặc trưng huấn luyện. Các số đếm sự kiện được giữ
bằng 0 trong file MAD, LOF và SVM để tập trung vào cơ chế đang minh họa.
Nhãn là quy ước của mô phỏng, không phải kết luận từ một hệ thống thực tế.

## Tái tạo và giới hạn

Từ thư mục gốc dự án:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_algorithm_datasets.py
```

Script dùng seed cố định, giữ nguyên file không liên quan và ghi thông tin
nguồn, cấu hình, vị trí chèn và SHA-256 vào `docs/algorithm_datasets_manifest.json`.
Không sử dụng điểm số mô hình để lựa chọn dữ liệu hay sửa nhãn.

15/300 điểm kiểm tra là bất thường, tương đương 5% tập kiểm tra. Tham số 1%
điều khiển ngưỡng của IF/LOF hoặc `nu` của SVM, không phải số cảnh báo bắt buộc.
Không suy rộng độ chính xác trên dữ liệu giả lập thành hiệu quả vận hành thực tế,
và không dùng bốn kịch bản khác nhau để xếp hạng công bằng các thuật toán.
Muốn so sánh, chạy cả bốn trên cùng một file, cùng tập kiểm tra và cấu hình.

Tham khảo nguyên lý thiết kế các ví dụ: [so sánh các thuật toán phát hiện bất thường
của scikit-learn](https://scikit-learn.org/stable/auto_examples/miscellaneous/plot_anomaly_comparison.html).
