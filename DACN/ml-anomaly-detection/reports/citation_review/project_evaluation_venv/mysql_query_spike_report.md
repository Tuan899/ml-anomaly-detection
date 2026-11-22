# ANOMALY LAB — Báo cáo giám sát hoạt động MySQL

Nguồn dữ liệu: mysql_query_spike.csv

Dữ liệu mẫu tổng hợp phục vụ kiểm thử kịch bản; các kết quả này không xác nhận hiệu quả trên máy chủ thật.

## Phạm vi phân tích

- Tổng số bản ghi: 1,440.
- Bản ghi huấn luyện: 1,008.
- Bản ghi kiểm tra đã phân tích: 432.
- Thuật toán: MAD, Isolation Forest, LOF, One-Class SVM.
- Chia theo thứ tự thời gian; số liệu kết quả chỉ thuộc phần kiểm tra. Nhãn không được dùng làm đặc trưng học.
- Khoảng kiểm tra: 2026-10-01 16:48:00 → 2026-10-01 23:59:00 UTC.

## Kết quả

Trạng thái: **Cảnh báo cao**.

Số bản ghi được mô hình đánh dấu ban đầu (hợp các thuật toán): 85.
Số bản ghi cảnh báo sau cấu hình vận hành (mỗi thời điểm chỉ tính một lần): 44 (10.19%).

Phát hiện 44/432 bản ghi kiểm tra có cảnh báo (10.2%). Dấu hiệu đo được liên quan đến số truy vấn mỗi giây. Đối chiếu các thời điểm được đánh dấu trước khi kết luận nguyên nhân.

## Vì sao hệ thống cảnh báo?

Các chỉ số là dấu hiệu có thể kiểm chứng, chưa phải nguyên nhân đã xác minh. Dữ liệu kết nối thất bại không phải tỷ lệ truy vấn lỗi; chưa có số truy vấn lỗi để tính tỷ lệ này.

Quy tắc mức cảnh báo của bản demo: chỉ xét các bản ghi đã được mô hình cảnh báo sau cấu hình vận hành. Một điểm có mức Cảnh báo cao khi ít nhất hai chỉ số vượt khoảng tham chiếu học từ tập huấn luyện; hoặc độ lệch của một chỉ số lớn hơn hai lần dung sai dương; hoặc kết nối thất bại tăng từ mức tham chiếu bằng 0. Toàn bộ lần phân tích có mức Cảnh báo cao nếu có điểm như trên hoặc ít nhất 10% bản ghi kiểm tra được cảnh báo. Có cảnh báo còn lại là Cần chú ý; không có cảnh báo là Bình thường. Đây là quy ước vận hành minh họa, không phải giới hạn MySQL hay SLA đã được xác nhận; bản thân quy tắc này không tạo dự đoán mô hình.

Điểm hiển thị = âm điểm quyết định gốc; điểm càng lớn càng nghi ngờ trong cùng thuật toán. Không so sánh trực tiếp điểm giữa các thuật toán.

| Thời gian | Chỉ số có thay đổi đáng chú ý | Giá trị quan sát | Giá trị tham chiếu | Điểm bất thường | Thuật toán (điểm) | Mức cảnh báo | Giải thích ngắn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 17:39:00 | Số truy vấn mỗi giây | 329.835 | 50.0685 | 44.7615 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 329.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:40:00 | Số truy vấn mỗi giây | 332.01 | 50.0685 | 45.1367 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 332 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:41:00 | Số truy vấn mỗi giây | 332.34 | 50.0685 | 45.1936 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 332.3 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:42:00 | Số truy vấn mỗi giây | 327.875 | 50.0685 | 44.4234 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 327.9 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:43:00 | Số truy vấn mỗi giây | 323.275 | 50.0685 | 43.6299 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 323.3 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:44:00 | Số truy vấn mỗi giây | 328.925 | 50.0685 | 44.6045 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 328.9 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:45:00 | Số truy vấn mỗi giây | 322.385 | 50.0685 | 43.4763 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 322.4 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:46:00 | Số truy vấn mỗi giây | 318.905 | 50.0685 | 42.876 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 318.9 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:47:00 | Số truy vấn mỗi giây | 328.75 | 50.0685 | 44.5743 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 328.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:48:00 | Số truy vấn mỗi giây | 328.095 | 50.0685 | 44.4613 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 328.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:49:00 | Số truy vấn mỗi giây | 327.05 | 50.0685 | 44.2811 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 327.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:50:00 | Số truy vấn mỗi giây | 327.75 | 50.0685 | 44.4018 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 327.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:51:00 | Số truy vấn mỗi giây | 331.095 | 50.0685 | 44.9789 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 331.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:52:00 | Số truy vấn mỗi giây | 330.11 | 50.0685 | 44.8089 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 330.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:53:00 | Số truy vấn mỗi giây | 331.34 | 50.0685 | 45.0211 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 331.3 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:54:00 | Số truy vấn mỗi giây | 333.87 | 50.0685 | 45.4576 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 333.9 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:55:00 | Số truy vấn mỗi giây | 334.265 | 50.0685 | 45.5257 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 334.3 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:56:00 | Số truy vấn mỗi giây | 341.775 | 50.0685 | 46.8212 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 341.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:57:00 | Số truy vấn mỗi giây | 339.23 | 50.0685 | 46.3822 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 339.2 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:58:00 | Số truy vấn mỗi giây | 348.06 | 50.0685 | 47.9054 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 348.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 17:59:00 | Số truy vấn mỗi giây | 344.505 | 50.0685 | 47.2922 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 344.5 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:00:00 | Số truy vấn mỗi giây | 349.82 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 349.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:01:00 | Số truy vấn mỗi giây | 353.565 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 353.6 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:02:00 | Số truy vấn mỗi giây | 351.015 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 351 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:03:00 | Số truy vấn mỗi giây | 357.095 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 357.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:04:00 | Số truy vấn mỗi giây | 364.81 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 364.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:05:00 | Số truy vấn mỗi giây | 368.505 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 368.5 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:06:00 | Số truy vấn mỗi giây | 362.985 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 363 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:07:00 | Số truy vấn mỗi giây | 366.04 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 366 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:08:00 | Số truy vấn mỗi giây | 371.745 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 371.7 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:09:00 | Số truy vấn mỗi giây | 374.24 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 374.2 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:10:00 | Số truy vấn mỗi giây | 376.8 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 376.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:11:00 | Số truy vấn mỗi giây | 373.7 | 50.0685 | 1.92754e+12 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 373.7 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:12:00 | Số truy vấn mỗi giây | 374.64 | 50.0685 | 52.4907 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 374.6 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:13:00 | Số truy vấn mỗi giây | 374.775 | 50.0685 | 52.5139 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 374.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:14:00 | Số truy vấn mỗi giây | 375.845 | 50.0685 | 52.6985 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 375.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:15:00 | Số truy vấn mỗi giây | 377.23 | 50.0685 | 52.9375 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 377.2 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:16:00 | Số truy vấn mỗi giây | 372.82 | 50.0685 | 52.1767 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 372.8 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:17:00 | Số truy vấn mỗi giây | 370.495 | 50.0685 | 51.7756 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 370.5 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:18:00 | Số truy vấn mỗi giây | 370.19 | 50.0685 | 51.723 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 370.2 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:19:00 | Số truy vấn mỗi giây | 368.34 | 50.0685 | 51.4039 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 368.3 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:20:00 | Số truy vấn mỗi giây | 370.135 | 50.0685 | 51.7135 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 370.1 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:21:00 | Số truy vấn mỗi giây | 369.525 | 50.0685 | 51.6083 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 369.5 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 18:22:00 | Số truy vấn mỗi giây | 367.175 | 50.0685 | 51.2029 | MAD | Cảnh báo cao | Số truy vấn mỗi giây tăng: 367.2 truy vấn/giây; trung vị học 50.07; dung sai ±20.4. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |

### Giá trị các chỉ số tại thời điểm cảnh báo

| Thời gian | Chỉ số | Quan sát | Trung vị học | Độ lệch | Dung sai | Đơn vị | Vượt dung sai |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 17:39:00 | Số truy vấn mỗi giây | 329.835 | 50.0685 | 279.766 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:39:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:39:00 | Thời gian phản hồi | 13.683 | 15.037 | -1.354 | 6.73536 | ms | Không |
| 2026-10-01 17:39:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:39:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:40:00 | Số truy vấn mỗi giây | 332.01 | 50.0685 | 281.942 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:40:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:40:00 | Thời gian phản hồi | 13.272 | 15.037 | -1.765 | 6.73536 | ms | Không |
| 2026-10-01 17:40:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:40:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:41:00 | Số truy vấn mỗi giây | 332.34 | 50.0685 | 282.271 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:41:00 | Số kết nối đang mở | 26 | 30 | -4 | 15.5673 | kết nối | Không |
| 2026-10-01 17:41:00 | Thời gian phản hồi | 14.1 | 15.037 | -0.937 | 6.73536 | ms | Không |
| 2026-10-01 17:41:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:41:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:42:00 | Số truy vấn mỗi giây | 327.875 | 50.0685 | 277.807 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:42:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:42:00 | Thời gian phản hồi | 13.311 | 15.037 | -1.726 | 6.73536 | ms | Không |
| 2026-10-01 17:42:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:42:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:43:00 | Số truy vấn mỗi giây | 323.275 | 50.0685 | 273.207 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:43:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:43:00 | Thời gian phản hồi | 13.492 | 15.037 | -1.545 | 6.73536 | ms | Không |
| 2026-10-01 17:43:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:43:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:44:00 | Số truy vấn mỗi giây | 328.925 | 50.0685 | 278.856 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:44:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:44:00 | Thời gian phản hồi | 12.895 | 15.037 | -2.142 | 6.73536 | ms | Không |
| 2026-10-01 17:44:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:44:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:45:00 | Số truy vấn mỗi giây | 322.385 | 50.0685 | 272.317 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:45:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:45:00 | Thời gian phản hồi | 13.136 | 15.037 | -1.901 | 6.73536 | ms | Không |
| 2026-10-01 17:45:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:45:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:46:00 | Số truy vấn mỗi giây | 318.905 | 50.0685 | 268.837 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:46:00 | Số kết nối đang mở | 26 | 30 | -4 | 15.5673 | kết nối | Không |
| 2026-10-01 17:46:00 | Thời gian phản hồi | 13.212 | 15.037 | -1.825 | 6.73536 | ms | Không |
| 2026-10-01 17:46:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:46:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:47:00 | Số truy vấn mỗi giây | 328.75 | 50.0685 | 278.682 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:47:00 | Số kết nối đang mở | 26 | 30 | -4 | 15.5673 | kết nối | Không |
| 2026-10-01 17:47:00 | Thời gian phản hồi | 12.915 | 15.037 | -2.122 | 6.73536 | ms | Không |
| 2026-10-01 17:47:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:47:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:48:00 | Số truy vấn mỗi giây | 328.095 | 50.0685 | 278.027 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:48:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:48:00 | Thời gian phản hồi | 13.938 | 15.037 | -1.099 | 6.73536 | ms | Không |
| 2026-10-01 17:48:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:48:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:49:00 | Số truy vấn mỗi giây | 327.05 | 50.0685 | 276.981 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:49:00 | Số kết nối đang mở | 26 | 30 | -4 | 15.5673 | kết nối | Không |
| 2026-10-01 17:49:00 | Thời gian phản hồi | 13.338 | 15.037 | -1.699 | 6.73536 | ms | Không |
| 2026-10-01 17:49:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:49:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:50:00 | Số truy vấn mỗi giây | 327.75 | 50.0685 | 277.682 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:50:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:50:00 | Thời gian phản hồi | 13.005 | 15.037 | -2.032 | 6.73536 | ms | Không |
| 2026-10-01 17:50:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:50:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:51:00 | Số truy vấn mỗi giây | 331.095 | 50.0685 | 281.027 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:51:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:51:00 | Thời gian phản hồi | 13.997 | 15.037 | -1.04 | 6.73536 | ms | Không |
| 2026-10-01 17:51:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:51:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:52:00 | Số truy vấn mỗi giây | 330.11 | 50.0685 | 280.042 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:52:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:52:00 | Thời gian phản hồi | 14.095 | 15.037 | -0.942 | 6.73536 | ms | Không |
| 2026-10-01 17:52:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:52:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:53:00 | Số truy vấn mỗi giây | 331.34 | 50.0685 | 281.271 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:53:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:53:00 | Thời gian phản hồi | 14.237 | 15.037 | -0.8 | 6.73536 | ms | Không |
| 2026-10-01 17:53:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:53:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:54:00 | Số truy vấn mỗi giây | 333.87 | 50.0685 | 283.802 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:54:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 17:54:00 | Thời gian phản hồi | 13.471 | 15.037 | -1.566 | 6.73536 | ms | Không |
| 2026-10-01 17:54:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:54:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:55:00 | Số truy vấn mỗi giây | 334.265 | 50.0685 | 284.197 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:55:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:55:00 | Thời gian phản hồi | 14.071 | 15.037 | -0.966 | 6.73536 | ms | Không |
| 2026-10-01 17:55:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:55:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:56:00 | Số truy vấn mỗi giây | 341.775 | 50.0685 | 291.707 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:56:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:56:00 | Thời gian phản hồi | 14.015 | 15.037 | -1.022 | 6.73536 | ms | Không |
| 2026-10-01 17:56:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:56:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:57:00 | Số truy vấn mỗi giây | 339.23 | 50.0685 | 289.162 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:57:00 | Số kết nối đang mở | 29 | 30 | -1 | 15.5673 | kết nối | Không |
| 2026-10-01 17:57:00 | Thời gian phản hồi | 14.105 | 15.037 | -0.932 | 6.73536 | ms | Không |
| 2026-10-01 17:57:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:57:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:58:00 | Số truy vấn mỗi giây | 348.06 | 50.0685 | 297.991 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:58:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 17:58:00 | Thời gian phản hồi | 14.573 | 15.037 | -0.464 | 6.73536 | ms | Không |
| 2026-10-01 17:58:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:58:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 17:59:00 | Số truy vấn mỗi giây | 344.505 | 50.0685 | 294.437 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 17:59:00 | Số kết nối đang mở | 30 | 30 | 0 | 15.5673 | kết nối | Không |
| 2026-10-01 17:59:00 | Thời gian phản hồi | 15.411 | 15.037 | 0.374 | 6.73536 | ms | Không |
| 2026-10-01 17:59:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 17:59:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:00:00 | Số truy vấn mỗi giây | 349.82 | 50.0685 | 299.751 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:00:00 | Số kết nối đang mở | 31 | 30 | 1 | 15.5673 | kết nối | Không |
| 2026-10-01 18:00:00 | Thời gian phản hồi | 14.455 | 15.037 | -0.582 | 6.73536 | ms | Không |
| 2026-10-01 18:00:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:00:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:01:00 | Số truy vấn mỗi giây | 353.565 | 50.0685 | 303.496 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:01:00 | Số kết nối đang mở | 30 | 30 | 0 | 15.5673 | kết nối | Không |
| 2026-10-01 18:01:00 | Thời gian phản hồi | 14.731 | 15.037 | -0.306 | 6.73536 | ms | Không |
| 2026-10-01 18:01:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:01:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:02:00 | Số truy vấn mỗi giây | 351.015 | 50.0685 | 300.947 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:02:00 | Số kết nối đang mở | 31 | 30 | 1 | 15.5673 | kết nối | Không |
| 2026-10-01 18:02:00 | Thời gian phản hồi | 15.13 | 15.037 | 0.093 | 6.73536 | ms | Không |
| 2026-10-01 18:02:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:02:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:03:00 | Số truy vấn mỗi giây | 357.095 | 50.0685 | 307.027 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:03:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:03:00 | Thời gian phản hồi | 15.545 | 15.037 | 0.508 | 6.73536 | ms | Không |
| 2026-10-01 18:03:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:03:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:04:00 | Số truy vấn mỗi giây | 364.81 | 50.0685 | 314.741 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:04:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:04:00 | Thời gian phản hồi | 15.236 | 15.037 | 0.199 | 6.73536 | ms | Không |
| 2026-10-01 18:04:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:04:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:05:00 | Số truy vấn mỗi giây | 368.505 | 50.0685 | 318.437 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:05:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:05:00 | Thời gian phản hồi | 15.306 | 15.037 | 0.269 | 6.73536 | ms | Không |
| 2026-10-01 18:05:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:05:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:06:00 | Số truy vấn mỗi giây | 362.985 | 50.0685 | 312.917 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:06:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:06:00 | Thời gian phản hồi | 15.958 | 15.037 | 0.921 | 6.73536 | ms | Không |
| 2026-10-01 18:06:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:06:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:07:00 | Số truy vấn mỗi giây | 366.04 | 50.0685 | 315.971 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:07:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:07:00 | Thời gian phản hồi | 15.786 | 15.037 | 0.749 | 6.73536 | ms | Không |
| 2026-10-01 18:07:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:07:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:08:00 | Số truy vấn mỗi giây | 371.745 | 50.0685 | 321.677 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:08:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:08:00 | Thời gian phản hồi | 16.772 | 15.037 | 1.735 | 6.73536 | ms | Không |
| 2026-10-01 18:08:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:08:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:09:00 | Số truy vấn mỗi giây | 374.24 | 50.0685 | 324.172 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:09:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:09:00 | Thời gian phản hồi | 16.671 | 15.037 | 1.634 | 6.73536 | ms | Không |
| 2026-10-01 18:09:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:09:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:10:00 | Số truy vấn mỗi giây | 376.8 | 50.0685 | 326.731 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:10:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:10:00 | Thời gian phản hồi | 16.447 | 15.037 | 1.41 | 6.73536 | ms | Không |
| 2026-10-01 18:10:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:10:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:11:00 | Số truy vấn mỗi giây | 373.7 | 50.0685 | 323.631 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:11:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:11:00 | Thời gian phản hồi | 17.171 | 15.037 | 2.134 | 6.73536 | ms | Không |
| 2026-10-01 18:11:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:11:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:12:00 | Số truy vấn mỗi giây | 374.64 | 50.0685 | 324.572 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:12:00 | Số kết nối đang mở | 34 | 30 | 4 | 15.5673 | kết nối | Không |
| 2026-10-01 18:12:00 | Thời gian phản hồi | 16.245 | 15.037 | 1.208 | 6.73536 | ms | Không |
| 2026-10-01 18:12:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:12:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:13:00 | Số truy vấn mỗi giây | 374.775 | 50.0685 | 324.707 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:13:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:13:00 | Thời gian phản hồi | 16.747 | 15.037 | 1.71 | 6.73536 | ms | Không |
| 2026-10-01 18:13:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:13:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:14:00 | Số truy vấn mỗi giây | 375.845 | 50.0685 | 325.777 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:14:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:14:00 | Thời gian phản hồi | 16.169 | 15.037 | 1.132 | 6.73536 | ms | Không |
| 2026-10-01 18:14:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:14:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:15:00 | Số truy vấn mỗi giây | 377.23 | 50.0685 | 327.162 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:15:00 | Số kết nối đang mở | 34 | 30 | 4 | 15.5673 | kết nối | Không |
| 2026-10-01 18:15:00 | Thời gian phản hồi | 17.289 | 15.037 | 2.252 | 6.73536 | ms | Không |
| 2026-10-01 18:15:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:15:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:16:00 | Số truy vấn mỗi giây | 372.82 | 50.0685 | 322.751 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:16:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:16:00 | Thời gian phản hồi | 16.078 | 15.037 | 1.041 | 6.73536 | ms | Không |
| 2026-10-01 18:16:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:16:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:17:00 | Số truy vấn mỗi giây | 370.495 | 50.0685 | 320.427 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:17:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:17:00 | Thời gian phản hồi | 16.298 | 15.037 | 1.261 | 6.73536 | ms | Không |
| 2026-10-01 18:17:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:17:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:18:00 | Số truy vấn mỗi giây | 370.19 | 50.0685 | 320.121 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:18:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 18:18:00 | Thời gian phản hồi | 17.12 | 15.037 | 2.083 | 6.73536 | ms | Không |
| 2026-10-01 18:18:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:18:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:19:00 | Số truy vấn mỗi giây | 368.34 | 50.0685 | 318.271 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:19:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:19:00 | Thời gian phản hồi | 16.825 | 15.037 | 1.788 | 6.73536 | ms | Không |
| 2026-10-01 18:19:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:19:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:20:00 | Số truy vấn mỗi giây | 370.135 | 50.0685 | 320.067 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:20:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:20:00 | Thời gian phản hồi | 16.254 | 15.037 | 1.217 | 6.73536 | ms | Không |
| 2026-10-01 18:20:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:20:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:21:00 | Số truy vấn mỗi giây | 369.525 | 50.0685 | 319.457 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:21:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:21:00 | Thời gian phản hồi | 16.363 | 15.037 | 1.326 | 6.73536 | ms | Không |
| 2026-10-01 18:21:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:21:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 18:22:00 | Số truy vấn mỗi giây | 367.175 | 50.0685 | 317.106 | 20.3987 | truy vấn/giây | Có |
| 2026-10-01 18:22:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 18:22:00 | Thời gian phản hồi | 15.851 | 15.037 | 0.814 | 6.73536 | ms | Không |
| 2026-10-01 18:22:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 18:22:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |

## Việc nên kiểm tra tiếp

- Đối chiếu lưu lượng ứng dụng và các truy vấn tại thời điểm cảnh báo; kiểm tra có tác vụ định kỳ hay tăng tải dự kiến.

## Đánh giá trên nhãn kiểm thử

Các chỉ số dưới đây được tính lại từ nhãn và dự đoán thực tế trên cùng phần kiểm tra. Lớp bất thường là -1; lớp bình thường là 1. Mẫu số bằng 0 được quy ước trả về 0.

### Sau cấu hình vận hành

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 1 | 1 | 1 | 1 | 388 | 0 | 0 | 44 |
| Isolation Forest | 0 | 0 | 0 | 0.898148 | 388 | 0 | 44 | 0 |
| LOF | 1 | 1 | 1 | 1 | 388 | 0 | 0 | 44 |
| One-Class SVM | 1 | 1 | 1 | 1 | 388 | 0 | 0 | 44 |

Ma trận nhầm lẫn mỗi thuật toán: hàng là nhãn thật [bình thường, bất thường], cột là dự đoán [bình thường, bất thường], tương ứng [[TN, FP], [FN, TP]].

### Dự đoán gốc của mô hình

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 0.55 | 1 | 0.709677 | 0.916667 | 352 | 36 | 0 | 44 |
| Isolation Forest | 0 | 0 | 0 | 0.872685 | 377 | 11 | 44 | 0 |
| LOF | 0.897959 | 1 | 0.946237 | 0.988426 | 383 | 5 | 0 | 44 |
| One-Class SVM | 0.862745 | 1 | 0.926316 | 0.983796 | 381 | 7 | 0 | 44 |

## Cấu hình và thời gian đo

- Bộ lọc vận hành: bật.
- Contamination/nu cấu hình: 0.01.
- Ngưỡng độ lệch vận hành: 3.5.
- MAD: huấn luyện 0.0001718 giây; dự đoán 5.52e-05 giây.
- Isolation Forest: huấn luyện 0.0989414 giây; dự đoán 0.0138749 giây.
- LOF: huấn luyện 0.0080909 giây; dự đoán 0.0059296 giây.
- One-Class SVM: huấn luyện 0.0021685 giây; dự đoán 0.0019114 giây.

Không suy ra tấn công, quá tải hay nguyên nhân gốc chỉ từ điểm bất thường. Đối chiếu nhật ký, truy vấn, tài nguyên máy chủ và bối cảnh vận hành trước khi kết luận.
