# ANOMALY LAB — Báo cáo giám sát hoạt động MySQL

Nguồn dữ liệu: mysql_connection_spike.csv

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

Số bản ghi được mô hình đánh dấu ban đầu (hợp các thuật toán): 95.
Số bản ghi cảnh báo sau cấu hình vận hành (mỗi thời điểm chỉ tính một lần): 44 (10.19%).

Phát hiện 44/432 bản ghi kiểm tra có cảnh báo (10.2%). Dấu hiệu đo được liên quan đến số kết nối đang mở, kết nối thất bại mỗi khoảng lấy mẫu. Đối chiếu các thời điểm được đánh dấu trước khi kết luận nguyên nhân.

## Vì sao hệ thống cảnh báo?

Các chỉ số là dấu hiệu có thể kiểm chứng, chưa phải nguyên nhân đã xác minh. Dữ liệu kết nối thất bại không phải tỷ lệ truy vấn lỗi; chưa có số truy vấn lỗi để tính tỷ lệ này.

Quy tắc mức cảnh báo của bản demo: chỉ xét các bản ghi đã được mô hình cảnh báo sau cấu hình vận hành. Một điểm có mức Cảnh báo cao khi ít nhất hai chỉ số vượt khoảng tham chiếu học từ tập huấn luyện; hoặc độ lệch của một chỉ số lớn hơn hai lần dung sai dương; hoặc kết nối thất bại tăng từ mức tham chiếu bằng 0. Toàn bộ lần phân tích có mức Cảnh báo cao nếu có điểm như trên hoặc ít nhất 10% bản ghi kiểm tra được cảnh báo. Có cảnh báo còn lại là Cần chú ý; không có cảnh báo là Bình thường. Đây là quy ước vận hành minh họa, không phải giới hạn MySQL hay SLA đã được xác nhận; bản thân quy tắc này không tạo dự đoán mô hình.

Điểm hiển thị = âm điểm quyết định gốc; điểm càng lớn càng nghi ngờ trong cùng thuật toán. Không so sánh trực tiếp điểm giữa các thuật toán.

| Thời gian | Chỉ số có thay đổi đáng chú ý | Giá trị quan sát | Giá trị tham chiếu | Điểm bất thường | Thuật toán (điểm) | Mức cảnh báo | Giải thích ngắn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 19:40:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:41:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:42:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:43:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:44:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:45:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:46:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:47:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:48:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:49:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:50:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:51:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:52:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:53:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:54:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:55:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:56:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:57:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:58:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 19:59:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:00:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:01:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:02:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:03:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:04:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:05:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:06:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:07:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:08:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:09:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:10:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:11:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:12:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:13:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:14:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:15:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:16:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:17:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:18:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:19:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:20:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:21:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:22:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 20:23:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 2.0235e+12 | MAD | Cảnh báo cao | Kết nối thất bại mỗi khoảng lấy mẫu tăng: 3 lỗi/khoảng; trung vị học 0; dung sai ±0. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |

### Giá trị các chỉ số tại thời điểm cảnh báo

| Thời gian | Chỉ số | Quan sát | Trung vị học | Độ lệch | Dung sai | Đơn vị | Vượt dung sai |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 19:40:00 | Số truy vấn mỗi giây | 42.819 | 50.0685 | -7.2495 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:40:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:40:00 | Thời gian phản hồi | 12.543 | 15.037 | -2.494 | 6.73536 | ms | Không |
| 2026-10-01 19:40:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:40:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:41:00 | Số truy vấn mỗi giây | 43.667 | 50.0685 | -6.4015 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:41:00 | Số kết nối đang mở | 190 | 30 | 160 | 15.5673 | kết nối | Có |
| 2026-10-01 19:41:00 | Thời gian phản hồi | 12.876 | 15.037 | -2.161 | 6.73536 | ms | Không |
| 2026-10-01 19:41:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 1 | 0 | 1 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:41:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:42:00 | Số truy vấn mỗi giây | 43.582 | 50.0685 | -6.4865 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:42:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:42:00 | Thời gian phản hồi | 12.493 | 15.037 | -2.544 | 6.73536 | ms | Không |
| 2026-10-01 19:42:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:42:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:43:00 | Số truy vấn mỗi giây | 43.738 | 50.0685 | -6.3305 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:43:00 | Số kết nối đang mở | 190 | 30 | 160 | 15.5673 | kết nối | Có |
| 2026-10-01 19:43:00 | Thời gian phản hồi | 12.695 | 15.037 | -2.342 | 6.73536 | ms | Không |
| 2026-10-01 19:43:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:43:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:44:00 | Số truy vấn mỗi giây | 42.268 | 50.0685 | -7.8005 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:44:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:44:00 | Thời gian phản hồi | 12.827 | 15.037 | -2.21 | 6.73536 | ms | Không |
| 2026-10-01 19:44:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:44:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:45:00 | Số truy vấn mỗi giây | 42.442 | 50.0685 | -7.6265 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:45:00 | Số kết nối đang mở | 190 | 30 | 160 | 15.5673 | kết nối | Có |
| 2026-10-01 19:45:00 | Thời gian phản hồi | 12.878 | 15.037 | -2.159 | 6.73536 | ms | Không |
| 2026-10-01 19:45:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:45:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:46:00 | Số truy vấn mỗi giây | 43.224 | 50.0685 | -6.8445 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:46:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:46:00 | Thời gian phản hồi | 12.94 | 15.037 | -2.097 | 6.73536 | ms | Không |
| 2026-10-01 19:46:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:46:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:47:00 | Số truy vấn mỗi giây | 43.392 | 50.0685 | -6.6765 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:47:00 | Số kết nối đang mở | 190 | 30 | 160 | 15.5673 | kết nối | Có |
| 2026-10-01 19:47:00 | Thời gian phản hồi | 12.47 | 15.037 | -2.567 | 6.73536 | ms | Không |
| 2026-10-01 19:47:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:47:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:48:00 | Số truy vấn mỗi giây | 42.947 | 50.0685 | -7.1215 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:48:00 | Số kết nối đang mở | 190 | 30 | 160 | 15.5673 | kết nối | Có |
| 2026-10-01 19:48:00 | Thời gian phản hồi | 12.34 | 15.037 | -2.697 | 6.73536 | ms | Không |
| 2026-10-01 19:48:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:48:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:49:00 | Số truy vấn mỗi giây | 44.874 | 50.0685 | -5.1945 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:49:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:49:00 | Thời gian phản hồi | 13.276 | 15.037 | -1.761 | 6.73536 | ms | Không |
| 2026-10-01 19:49:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:49:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:50:00 | Số truy vấn mỗi giây | 44.103 | 50.0685 | -5.9655 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:50:00 | Số kết nối đang mở | 190 | 30 | 160 | 15.5673 | kết nối | Có |
| 2026-10-01 19:50:00 | Thời gian phản hồi | 12.872 | 15.037 | -2.165 | 6.73536 | ms | Không |
| 2026-10-01 19:50:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:50:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:51:00 | Số truy vấn mỗi giây | 44.148 | 50.0685 | -5.9205 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:51:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:51:00 | Thời gian phản hồi | 13.688 | 15.037 | -1.349 | 6.73536 | ms | Không |
| 2026-10-01 19:51:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:51:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:52:00 | Số truy vấn mỗi giây | 44.645 | 50.0685 | -5.4235 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:52:00 | Số kết nối đang mở | 198 | 30 | 168 | 15.5673 | kết nối | Có |
| 2026-10-01 19:52:00 | Thời gian phản hồi | 13.916 | 15.037 | -1.121 | 6.73536 | ms | Không |
| 2026-10-01 19:52:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:52:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:53:00 | Số truy vấn mỗi giây | 44.74 | 50.0685 | -5.3285 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:53:00 | Số kết nối đang mở | 194 | 30 | 164 | 15.5673 | kết nối | Có |
| 2026-10-01 19:53:00 | Thời gian phản hồi | 13.6 | 15.037 | -1.437 | 6.73536 | ms | Không |
| 2026-10-01 19:53:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:53:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:54:00 | Số truy vấn mỗi giây | 46.84 | 50.0685 | -3.2285 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:54:00 | Số kết nối đang mở | 198 | 30 | 168 | 15.5673 | kết nối | Có |
| 2026-10-01 19:54:00 | Thời gian phản hồi | 13.678 | 15.037 | -1.359 | 6.73536 | ms | Không |
| 2026-10-01 19:54:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:54:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:55:00 | Số truy vấn mỗi giây | 46.264 | 50.0685 | -3.8045 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:55:00 | Số kết nối đang mở | 198 | 30 | 168 | 15.5673 | kết nối | Có |
| 2026-10-01 19:55:00 | Thời gian phản hồi | 14.247 | 15.037 | -0.79 | 6.73536 | ms | Không |
| 2026-10-01 19:55:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:55:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:56:00 | Số truy vấn mỗi giây | 47.958 | 50.0685 | -2.1105 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:56:00 | Số kết nối đang mở | 202 | 30 | 172 | 15.5673 | kết nối | Có |
| 2026-10-01 19:56:00 | Thời gian phản hồi | 14.333 | 15.037 | -0.704 | 6.73536 | ms | Không |
| 2026-10-01 19:56:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:56:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:57:00 | Số truy vấn mỗi giây | 47.445 | 50.0685 | -2.6235 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:57:00 | Số kết nối đang mở | 206 | 30 | 176 | 15.5673 | kết nối | Có |
| 2026-10-01 19:57:00 | Thời gian phản hồi | 14.196 | 15.037 | -0.841 | 6.73536 | ms | Không |
| 2026-10-01 19:57:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:57:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:58:00 | Số truy vấn mỗi giây | 49.133 | 50.0685 | -0.9355 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:58:00 | Số kết nối đang mở | 206 | 30 | 176 | 15.5673 | kết nối | Có |
| 2026-10-01 19:58:00 | Thời gian phản hồi | 14.766 | 15.037 | -0.271 | 6.73536 | ms | Không |
| 2026-10-01 19:58:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:58:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 19:59:00 | Số truy vấn mỗi giây | 48.594 | 50.0685 | -1.4745 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 19:59:00 | Số kết nối đang mở | 210 | 30 | 180 | 15.5673 | kết nối | Có |
| 2026-10-01 19:59:00 | Thời gian phản hồi | 14.708 | 15.037 | -0.329 | 6.73536 | ms | Không |
| 2026-10-01 19:59:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 19:59:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:00:00 | Số truy vấn mỗi giây | 50.515 | 50.0685 | 0.4465 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:00:00 | Số kết nối đang mở | 206 | 30 | 176 | 15.5673 | kết nối | Có |
| 2026-10-01 20:00:00 | Thời gian phản hồi | 15.315 | 15.037 | 0.278 | 6.73536 | ms | Không |
| 2026-10-01 20:00:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:00:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:01:00 | Số truy vấn mỗi giây | 50.269 | 50.0685 | 0.2005 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:01:00 | Số kết nối đang mở | 214 | 30 | 184 | 15.5673 | kết nối | Có |
| 2026-10-01 20:01:00 | Thời gian phản hồi | 15.661 | 15.037 | 0.624 | 6.73536 | ms | Không |
| 2026-10-01 20:01:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:01:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:02:00 | Số truy vấn mỗi giây | 50.798 | 50.0685 | 0.7295 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:02:00 | Số kết nối đang mở | 210 | 30 | 180 | 15.5673 | kết nối | Có |
| 2026-10-01 20:02:00 | Thời gian phản hồi | 15.545 | 15.037 | 0.508 | 6.73536 | ms | Không |
| 2026-10-01 20:02:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:02:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:03:00 | Số truy vấn mỗi giây | 51.217 | 50.0685 | 1.1485 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:03:00 | Số kết nối đang mở | 214 | 30 | 184 | 15.5673 | kết nối | Có |
| 2026-10-01 20:03:00 | Thời gian phản hồi | 15.572 | 15.037 | 0.535 | 6.73536 | ms | Không |
| 2026-10-01 20:03:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:03:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:04:00 | Số truy vấn mỗi giây | 52.12 | 50.0685 | 2.0515 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:04:00 | Số kết nối đang mở | 218 | 30 | 188 | 15.5673 | kết nối | Có |
| 2026-10-01 20:04:00 | Thời gian phản hồi | 15.726 | 15.037 | 0.689 | 6.73536 | ms | Không |
| 2026-10-01 20:04:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:04:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:05:00 | Số truy vấn mỗi giây | 52.501 | 50.0685 | 2.4325 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:05:00 | Số kết nối đang mở | 222 | 30 | 192 | 15.5673 | kết nối | Có |
| 2026-10-01 20:05:00 | Thời gian phản hồi | 16.192 | 15.037 | 1.155 | 6.73536 | ms | Không |
| 2026-10-01 20:05:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:05:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:06:00 | Số truy vấn mỗi giây | 53.666 | 50.0685 | 3.5975 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:06:00 | Số kết nối đang mở | 222 | 30 | 192 | 15.5673 | kết nối | Có |
| 2026-10-01 20:06:00 | Thời gian phản hồi | 16.497 | 15.037 | 1.46 | 6.73536 | ms | Không |
| 2026-10-01 20:06:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:06:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:07:00 | Số truy vấn mỗi giây | 54.149 | 50.0685 | 4.0805 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:07:00 | Số kết nối đang mở | 222 | 30 | 192 | 15.5673 | kết nối | Có |
| 2026-10-01 20:07:00 | Thời gian phản hồi | 16.885 | 15.037 | 1.848 | 6.73536 | ms | Không |
| 2026-10-01 20:07:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:07:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:08:00 | Số truy vấn mỗi giây | 54.216 | 50.0685 | 4.1475 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:08:00 | Số kết nối đang mở | 222 | 30 | 192 | 15.5673 | kết nối | Có |
| 2026-10-01 20:08:00 | Thời gian phản hồi | 16.592 | 15.037 | 1.555 | 6.73536 | ms | Không |
| 2026-10-01 20:08:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:08:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:09:00 | Số truy vấn mỗi giây | 55.474 | 50.0685 | 5.4055 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:09:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:09:00 | Thời gian phản hồi | 16.787 | 15.037 | 1.75 | 6.73536 | ms | Không |
| 2026-10-01 20:09:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:09:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:10:00 | Số truy vấn mỗi giây | 56.091 | 50.0685 | 6.0225 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:10:00 | Số kết nối đang mở | 222 | 30 | 192 | 15.5673 | kết nối | Có |
| 2026-10-01 20:10:00 | Thời gian phản hồi | 16.67 | 15.037 | 1.633 | 6.73536 | ms | Không |
| 2026-10-01 20:10:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:10:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:11:00 | Số truy vấn mỗi giây | 55.333 | 50.0685 | 5.2645 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:11:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:11:00 | Thời gian phản hồi | 17.314 | 15.037 | 2.277 | 6.73536 | ms | Không |
| 2026-10-01 20:11:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:11:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:12:00 | Số truy vấn mỗi giây | 55.651 | 50.0685 | 5.5825 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:12:00 | Số kết nối đang mở | 230 | 30 | 200 | 15.5673 | kết nối | Có |
| 2026-10-01 20:12:00 | Thời gian phản hồi | 17.328 | 15.037 | 2.291 | 6.73536 | ms | Không |
| 2026-10-01 20:12:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:12:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:13:00 | Số truy vấn mỗi giây | 56.107 | 50.0685 | 6.0385 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:13:00 | Số kết nối đang mở | 230 | 30 | 200 | 15.5673 | kết nối | Có |
| 2026-10-01 20:13:00 | Thời gian phản hồi | 17.449 | 15.037 | 2.412 | 6.73536 | ms | Không |
| 2026-10-01 20:13:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:13:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:14:00 | Số truy vấn mỗi giây | 57.441 | 50.0685 | 7.3725 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:14:00 | Số kết nối đang mở | 230 | 30 | 200 | 15.5673 | kết nối | Có |
| 2026-10-01 20:14:00 | Thời gian phản hồi | 17.178 | 15.037 | 2.141 | 6.73536 | ms | Không |
| 2026-10-01 20:14:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:14:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:15:00 | Số truy vấn mỗi giây | 57.626 | 50.0685 | 7.5575 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:15:00 | Số kết nối đang mở | 230 | 30 | 200 | 15.5673 | kết nối | Có |
| 2026-10-01 20:15:00 | Thời gian phản hồi | 17.374 | 15.037 | 2.337 | 6.73536 | ms | Không |
| 2026-10-01 20:15:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:15:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:16:00 | Số truy vấn mỗi giây | 56.944 | 50.0685 | 6.8755 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:16:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:16:00 | Thời gian phản hồi | 17.179 | 15.037 | 2.142 | 6.73536 | ms | Không |
| 2026-10-01 20:16:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:16:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:17:00 | Số truy vấn mỗi giây | 56.635 | 50.0685 | 6.5665 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:17:00 | Số kết nối đang mở | 230 | 30 | 200 | 15.5673 | kết nối | Có |
| 2026-10-01 20:17:00 | Thời gian phản hồi | 17.725 | 15.037 | 2.688 | 6.73536 | ms | Không |
| 2026-10-01 20:17:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:17:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:18:00 | Số truy vấn mỗi giây | 57.005 | 50.0685 | 6.9365 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:18:00 | Số kết nối đang mở | 230 | 30 | 200 | 15.5673 | kết nối | Có |
| 2026-10-01 20:18:00 | Thời gian phản hồi | 16.866 | 15.037 | 1.829 | 6.73536 | ms | Không |
| 2026-10-01 20:18:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:18:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:19:00 | Số truy vấn mỗi giây | 57.119 | 50.0685 | 7.0505 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:19:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:19:00 | Thời gian phản hồi | 16.839 | 15.037 | 1.802 | 6.73536 | ms | Không |
| 2026-10-01 20:19:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:19:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:20:00 | Số truy vấn mỗi giây | 55.351 | 50.0685 | 5.2825 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:20:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:20:00 | Thời gian phản hồi | 17.657 | 15.037 | 2.62 | 6.73536 | ms | Không |
| 2026-10-01 20:20:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:20:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:21:00 | Số truy vấn mỗi giây | 56.205 | 50.0685 | 6.1365 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:21:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:21:00 | Thời gian phản hồi | 16.743 | 15.037 | 1.706 | 6.73536 | ms | Không |
| 2026-10-01 20:21:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:21:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:22:00 | Số truy vấn mỗi giây | 55.639 | 50.0685 | 5.5705 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:22:00 | Số kết nối đang mở | 222 | 30 | 192 | 15.5673 | kết nối | Có |
| 2026-10-01 20:22:00 | Thời gian phản hồi | 17.166 | 15.037 | 2.129 | 6.73536 | ms | Không |
| 2026-10-01 20:22:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:22:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |
| 2026-10-01 20:23:00 | Số truy vấn mỗi giây | 54.599 | 50.0685 | 4.5305 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 20:23:00 | Số kết nối đang mở | 226 | 30 | 196 | 15.5673 | kết nối | Có |
| 2026-10-01 20:23:00 | Thời gian phản hồi | 16.269 | 15.037 | 1.232 | 6.73536 | ms | Không |
| 2026-10-01 20:23:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 0 | 0 | 0 | 1 | truy vấn/khoảng | Không |
| 2026-10-01 20:23:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 3 | 0 | 3 | 0 | lỗi/khoảng | Có |

## Việc nên kiểm tra tiếp

- Kiểm tra nhóm kết nối ứng dụng, kết nối đang mở và giới hạn max_connections.
- Đối chiếu log lỗi MySQL, giới hạn kết nối và tình trạng mạng; số lỗi kết nối chưa xác định được nguồn lỗi.

## Đánh giá trên nhãn kiểm thử

Các chỉ số dưới đây được tính lại từ nhãn và dự đoán thực tế trên cùng phần kiểm tra. Lớp bất thường là -1; lớp bình thường là 1. Mẫu số bằng 0 được quy ước trả về 0.

### Sau cấu hình vận hành

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 1 | 1 | 1 | 1 | 388 | 0 | 0 | 44 |
| Isolation Forest | 1 | 0.0454545 | 0.0869565 | 0.902778 | 388 | 0 | 42 | 2 |
| LOF | 1 | 1 | 1 | 1 | 388 | 0 | 0 | 44 |
| One-Class SVM | 1 | 1 | 1 | 1 | 388 | 0 | 0 | 44 |

Ma trận nhầm lẫn mỗi thuật toán: hàng là nhãn thật [bình thường, bất thường], cột là dự đoán [bình thường, bất thường], tương ứng [[TN, FP], [FN, TP]].

### Dự đoán gốc của mô hình

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 0.488889 | 1 | 0.656716 | 0.893519 | 342 | 46 | 0 | 44 |
| Isolation Forest | 0.181818 | 0.0454545 | 0.0727273 | 0.881944 | 379 | 9 | 42 | 2 |
| LOF | 0.916667 | 1 | 0.956522 | 0.990741 | 384 | 4 | 0 | 44 |
| One-Class SVM | 0.862745 | 1 | 0.926316 | 0.983796 | 381 | 7 | 0 | 44 |

## Cấu hình và thời gian đo

- Bộ lọc vận hành: bật.
- Contamination/nu cấu hình: 0.01.
- Ngưỡng độ lệch vận hành: 3.5.
- MAD: huấn luyện 0.0001788 giây; dự đoán 6.22e-05 giây.
- Isolation Forest: huấn luyện 0.0979911 giây; dự đoán 0.0125318 giây.
- LOF: huấn luyện 0.0064679 giây; dự đoán 0.0054617 giây.
- One-Class SVM: huấn luyện 0.0013757 giây; dự đoán 0.0013935 giây.

Không suy ra tấn công, quá tải hay nguyên nhân gốc chỉ từ điểm bất thường. Đối chiếu nhật ký, truy vấn, tài nguyên máy chủ và bối cảnh vận hành trước khi kết luận.
