# ANOMALY LAB — Báo cáo giám sát hoạt động MySQL

Nguồn dữ liệu: mysql_latency_spike.csv

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

Số bản ghi được mô hình đánh dấu ban đầu (hợp các thuật toán): 96.
Số bản ghi cảnh báo sau cấu hình vận hành (mỗi thời điểm chỉ tính một lần): 43 (9.95%).

Phát hiện 43/432 bản ghi kiểm tra có cảnh báo (10.0%). Dấu hiệu đo được liên quan đến thời gian phản hồi, truy vấn chậm mỗi khoảng lấy mẫu. Đối chiếu các thời điểm được đánh dấu trước khi kết luận nguyên nhân.

## Vì sao hệ thống cảnh báo?

Các chỉ số là dấu hiệu có thể kiểm chứng, chưa phải nguyên nhân đã xác minh. Dữ liệu kết nối thất bại không phải tỷ lệ truy vấn lỗi; chưa có số truy vấn lỗi để tính tỷ lệ này.

Quy tắc mức cảnh báo của bản demo: chỉ xét các bản ghi đã được mô hình cảnh báo sau cấu hình vận hành. Một điểm có mức Cảnh báo cao khi ít nhất hai chỉ số vượt khoảng tham chiếu học từ tập huấn luyện; hoặc độ lệch của một chỉ số lớn hơn hai lần dung sai dương; hoặc kết nối thất bại tăng từ mức tham chiếu bằng 0. Toàn bộ lần phân tích có mức Cảnh báo cao nếu có điểm như trên hoặc ít nhất 10% bản ghi kiểm tra được cảnh báo. Có cảnh báo còn lại là Cần chú ý; không có cảnh báo là Bình thường. Đây là quy ước vận hành minh họa, không phải giới hạn MySQL hay SLA đã được xác nhận; bản thân quy tắc này không tạo dự đoán mô hình.

Điểm hiển thị = âm điểm quyết định gốc; điểm càng lớn càng nghi ngờ trong cùng thuật toán. Không so sánh trực tiếp điểm giữa các thuật toán.

| Thời gian | Chỉ số có thay đổi đáng chú ý | Giá trị quan sát | Giá trị tham chiếu | Điểm bất thường | Thuật toán (điểm) | Mức cảnh báo | Giải thích ngắn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 21:41:00 | Thời gian phản hồi | 208.818 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 208.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:42:00 | Thời gian phản hồi | 212.634 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 212.6 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:43:00 | Thời gian phản hồi | 209.223 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 209.2 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:44:00 | Thời gian phản hồi | 214.839 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 214.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:45:00 | Thời gian phản hồi | 206.253 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 206.3 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:46:00 | Thời gian phản hồi | 210.528 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 210.5 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:47:00 | Thời gian phản hồi | 205.245 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 205.2 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:48:00 | Thời gian phản hồi | 208.791 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 208.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:49:00 | Thời gian phản hồi | 213.795 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 213.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:50:00 | Thời gian phản hồi | 215.496 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 215.5 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:51:00 | Thời gian phản hồi | 216.783 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 216.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:52:00 | Thời gian phản hồi | 215.136 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 215.1 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:53:00 | Thời gian phản hồi | 218.16 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 218.2 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:54:00 | Thời gian phản hồi | 219.159 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 219.2 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:55:00 | Thời gian phản hồi | 216.108 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 216.1 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:56:00 | Thời gian phản hồi | 218.853 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 218.9 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:57:00 | Thời gian phản hồi | 222.048 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 222 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:58:00 | Thời gian phản hồi | 226.467 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 226.5 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 21:59:00 | Thời gian phản hồi | 220.149 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 220.1 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:00:00 | Thời gian phản hồi | 229.788 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 229.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:01:00 | Thời gian phản hồi | 226.161 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 226.2 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:02:00 | Thời gian phản hồi | 231.957 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 232 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:03:00 | Thời gian phản hồi | 232.047 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 232 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:04:00 | Thời gian phản hồi | 231.021 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 231 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:05:00 | Thời gian phản hồi | 231.696 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 231.7 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:06:00 | Thời gian phản hồi | 236.907 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 236.9 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:07:00 | Thời gian phản hồi | 235.062 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 235.1 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:08:00 | Thời gian phản hồi | 237.546 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 237.5 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:09:00 | Thời gian phản hồi | 234.891 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 234.9 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:10:00 | Thời gian phản hồi | 242.046 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 242 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:11:00 | Thời gian phản hồi | 239.805 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 239.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:12:00 | Thời gian phản hồi | 234.891 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 234.9 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:13:00 | Thời gian phản hồi | 242.595 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 242.6 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:14:00 | Thời gian phản hồi | 245.286 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 245.3 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:15:00 | Thời gian phản hồi | 239.814 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 239.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:16:00 | Thời gian phản hồi | 236.403 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 236.4 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:17:00 | Thời gian phản hồi | 235.782 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 235.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:18:00 | Thời gian phản hồi | 240.21 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 240.2 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:19:00 | Thời gian phản hồi | 238.806 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 238.8 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:20:00 | Thời gian phản hồi | 235.395 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 235.4 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:21:00 | Thời gian phản hồi | 231.255 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 231.3 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:22:00 | Thời gian phản hồi | 234.315 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 234.3 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |
| 2026-10-01 22:23:00 | Thời gian phản hồi | 236.556 | 15.037 | 1.54204e+13 | MAD | Cảnh báo cao | Thời gian phản hồi tăng: 236.6 ms; trung vị học 15.04; dung sai ±6.735. Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân. |

### Giá trị các chỉ số tại thời điểm cảnh báo

| Thời gian | Chỉ số | Quan sát | Trung vị học | Độ lệch | Dung sai | Đơn vị | Vượt dung sai |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 21:41:00 | Số truy vấn mỗi giây | 44.703 | 50.0685 | -5.3655 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:41:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:41:00 | Thời gian phản hồi | 208.818 | 15.037 | 193.781 | 6.73536 | ms | Có |
| 2026-10-01 21:41:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:41:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:42:00 | Số truy vấn mỗi giây | 44.455 | 50.0685 | -5.6135 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:42:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:42:00 | Thời gian phản hồi | 212.634 | 15.037 | 197.597 | 6.73536 | ms | Có |
| 2026-10-01 21:42:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:42:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:43:00 | Số truy vấn mỗi giây | 45.681 | 50.0685 | -4.3875 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:43:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:43:00 | Thời gian phản hồi | 209.223 | 15.037 | 194.186 | 6.73536 | ms | Có |
| 2026-10-01 21:43:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:43:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:44:00 | Số truy vấn mỗi giây | 45.596 | 50.0685 | -4.4725 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:44:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:44:00 | Thời gian phản hồi | 214.839 | 15.037 | 199.802 | 6.73536 | ms | Có |
| 2026-10-01 21:44:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:44:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:45:00 | Số truy vấn mỗi giây | 45.368 | 50.0685 | -4.7005 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:45:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:45:00 | Thời gian phản hồi | 206.253 | 15.037 | 191.216 | 6.73536 | ms | Có |
| 2026-10-01 21:45:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:45:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:46:00 | Số truy vấn mỗi giây | 45.562 | 50.0685 | -4.5065 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:46:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:46:00 | Thời gian phản hồi | 210.528 | 15.037 | 195.491 | 6.73536 | ms | Có |
| 2026-10-01 21:46:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:46:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:47:00 | Số truy vấn mỗi giây | 44.732 | 50.0685 | -5.3365 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:47:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:47:00 | Thời gian phản hồi | 205.245 | 15.037 | 190.208 | 6.73536 | ms | Có |
| 2026-10-01 21:47:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:47:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:48:00 | Số truy vấn mỗi giây | 44.063 | 50.0685 | -6.0055 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:48:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:48:00 | Thời gian phản hồi | 208.791 | 15.037 | 193.754 | 6.73536 | ms | Có |
| 2026-10-01 21:48:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:48:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:49:00 | Số truy vấn mỗi giây | 45.805 | 50.0685 | -4.2635 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:49:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:49:00 | Thời gian phản hồi | 213.795 | 15.037 | 198.758 | 6.73536 | ms | Có |
| 2026-10-01 21:49:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:49:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:50:00 | Số truy vấn mỗi giây | 45.717 | 50.0685 | -4.3515 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:50:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:50:00 | Thời gian phản hồi | 215.496 | 15.037 | 200.459 | 6.73536 | ms | Có |
| 2026-10-01 21:50:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:50:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:51:00 | Số truy vấn mỗi giây | 45.023 | 50.0685 | -5.0455 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:51:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:51:00 | Thời gian phản hồi | 216.783 | 15.037 | 201.746 | 6.73536 | ms | Có |
| 2026-10-01 21:51:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:51:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:52:00 | Số truy vấn mỗi giây | 45.353 | 50.0685 | -4.7155 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:52:00 | Số kết nối đang mở | 27 | 30 | -3 | 15.5673 | kết nối | Không |
| 2026-10-01 21:52:00 | Thời gian phản hồi | 215.136 | 15.037 | 200.099 | 6.73536 | ms | Có |
| 2026-10-01 21:52:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:52:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:53:00 | Số truy vấn mỗi giây | 46.398 | 50.0685 | -3.6705 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:53:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:53:00 | Thời gian phản hồi | 218.16 | 15.037 | 203.123 | 6.73536 | ms | Có |
| 2026-10-01 21:53:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:53:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:54:00 | Số truy vấn mỗi giây | 46.809 | 50.0685 | -3.2595 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:54:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:54:00 | Thời gian phản hồi | 219.159 | 15.037 | 204.122 | 6.73536 | ms | Có |
| 2026-10-01 21:54:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:54:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:55:00 | Số truy vấn mỗi giây | 48.037 | 50.0685 | -2.0315 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:55:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:55:00 | Thời gian phản hồi | 216.108 | 15.037 | 201.071 | 6.73536 | ms | Có |
| 2026-10-01 21:55:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:55:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:56:00 | Số truy vấn mỗi giây | 47.056 | 50.0685 | -3.0125 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:56:00 | Số kết nối đang mở | 29 | 30 | -1 | 15.5673 | kết nối | Không |
| 2026-10-01 21:56:00 | Thời gian phản hồi | 218.853 | 15.037 | 203.816 | 6.73536 | ms | Có |
| 2026-10-01 21:56:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:56:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:57:00 | Số truy vấn mỗi giây | 49.228 | 50.0685 | -0.8405 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:57:00 | Số kết nối đang mở | 28 | 30 | -2 | 15.5673 | kết nối | Không |
| 2026-10-01 21:57:00 | Thời gian phản hồi | 222.048 | 15.037 | 207.011 | 6.73536 | ms | Có |
| 2026-10-01 21:57:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:57:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:58:00 | Số truy vấn mỗi giây | 49.572 | 50.0685 | -0.4965 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:58:00 | Số kết nối đang mở | 29 | 30 | -1 | 15.5673 | kết nối | Không |
| 2026-10-01 21:58:00 | Thời gian phản hồi | 226.467 | 15.037 | 211.43 | 6.73536 | ms | Có |
| 2026-10-01 21:58:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:58:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 21:59:00 | Số truy vấn mỗi giây | 48.844 | 50.0685 | -1.2245 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 21:59:00 | Số kết nối đang mở | 29 | 30 | -1 | 15.5673 | kết nối | Không |
| 2026-10-01 21:59:00 | Thời gian phản hồi | 220.149 | 15.037 | 205.112 | 6.73536 | ms | Có |
| 2026-10-01 21:59:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 21:59:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:00:00 | Số truy vấn mỗi giây | 49.242 | 50.0685 | -0.8265 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:00:00 | Số kết nối đang mở | 29 | 30 | -1 | 15.5673 | kết nối | Không |
| 2026-10-01 22:00:00 | Thời gian phản hồi | 229.788 | 15.037 | 214.751 | 6.73536 | ms | Có |
| 2026-10-01 22:00:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:00:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:01:00 | Số truy vấn mỗi giây | 50.935 | 50.0685 | 0.8665 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:01:00 | Số kết nối đang mở | 30 | 30 | 0 | 15.5673 | kết nối | Không |
| 2026-10-01 22:01:00 | Thời gian phản hồi | 226.161 | 15.037 | 211.124 | 6.73536 | ms | Có |
| 2026-10-01 22:01:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:01:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:02:00 | Số truy vấn mỗi giây | 50.939 | 50.0685 | 0.8705 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:02:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 22:02:00 | Thời gian phản hồi | 231.957 | 15.037 | 216.92 | 6.73536 | ms | Có |
| 2026-10-01 22:02:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:02:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:03:00 | Số truy vấn mỗi giây | 51.841 | 50.0685 | 1.7725 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:03:00 | Số kết nối đang mở | 31 | 30 | 1 | 15.5673 | kết nối | Không |
| 2026-10-01 22:03:00 | Thời gian phản hồi | 232.047 | 15.037 | 217.01 | 6.73536 | ms | Có |
| 2026-10-01 22:03:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:03:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:04:00 | Số truy vấn mỗi giây | 52.57 | 50.0685 | 2.5015 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:04:00 | Số kết nối đang mở | 31 | 30 | 1 | 15.5673 | kết nối | Không |
| 2026-10-01 22:04:00 | Thời gian phản hồi | 231.021 | 15.037 | 215.984 | 6.73536 | ms | Có |
| 2026-10-01 22:04:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:04:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:05:00 | Số truy vấn mỗi giây | 53.301 | 50.0685 | 3.2325 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:05:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 22:05:00 | Thời gian phản hồi | 231.696 | 15.037 | 216.659 | 6.73536 | ms | Có |
| 2026-10-01 22:05:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:05:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:06:00 | Số truy vấn mỗi giây | 52.801 | 50.0685 | 2.7325 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:06:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:06:00 | Thời gian phản hồi | 236.907 | 15.037 | 221.87 | 6.73536 | ms | Có |
| 2026-10-01 22:06:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:06:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:07:00 | Số truy vấn mỗi giây | 53.295 | 50.0685 | 3.2265 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:07:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:07:00 | Thời gian phản hồi | 235.062 | 15.037 | 220.025 | 6.73536 | ms | Có |
| 2026-10-01 22:07:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:07:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:08:00 | Số truy vấn mỗi giây | 53.668 | 50.0685 | 3.5995 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:08:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:08:00 | Thời gian phản hồi | 237.546 | 15.037 | 222.509 | 6.73536 | ms | Có |
| 2026-10-01 22:08:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:08:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:09:00 | Số truy vấn mỗi giây | 53.466 | 50.0685 | 3.3975 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:09:00 | Số kết nối đang mở | 34 | 30 | 4 | 15.5673 | kết nối | Không |
| 2026-10-01 22:09:00 | Thời gian phản hồi | 234.891 | 15.037 | 219.854 | 6.73536 | ms | Có |
| 2026-10-01 22:09:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:09:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:10:00 | Số truy vấn mỗi giây | 54.572 | 50.0685 | 4.5035 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:10:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:10:00 | Thời gian phản hồi | 242.046 | 15.037 | 227.009 | 6.73536 | ms | Có |
| 2026-10-01 22:10:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:10:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:11:00 | Số truy vấn mỗi giây | 54.361 | 50.0685 | 4.2925 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:11:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 22:11:00 | Thời gian phản hồi | 239.805 | 15.037 | 224.768 | 6.73536 | ms | Có |
| 2026-10-01 22:11:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:11:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:12:00 | Số truy vấn mỗi giây | 54.176 | 50.0685 | 4.1075 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:12:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 22:12:00 | Thời gian phản hồi | 234.891 | 15.037 | 219.854 | 6.73536 | ms | Có |
| 2026-10-01 22:12:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:12:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:13:00 | Số truy vấn mỗi giây | 55.69 | 50.0685 | 5.6215 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:13:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:13:00 | Thời gian phản hồi | 242.595 | 15.037 | 227.558 | 6.73536 | ms | Có |
| 2026-10-01 22:13:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:13:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:14:00 | Số truy vấn mỗi giây | 55.804 | 50.0685 | 5.7355 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:14:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:14:00 | Thời gian phản hồi | 245.286 | 15.037 | 230.249 | 6.73536 | ms | Có |
| 2026-10-01 22:14:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:14:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:15:00 | Số truy vấn mỗi giây | 55.401 | 50.0685 | 5.3325 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:15:00 | Số kết nối đang mở | 34 | 30 | 4 | 15.5673 | kết nối | Không |
| 2026-10-01 22:15:00 | Thời gian phản hồi | 239.814 | 15.037 | 224.777 | 6.73536 | ms | Có |
| 2026-10-01 22:15:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:15:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:16:00 | Số truy vấn mỗi giây | 54.465 | 50.0685 | 4.3965 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:16:00 | Số kết nối đang mở | 34 | 30 | 4 | 15.5673 | kết nối | Không |
| 2026-10-01 22:16:00 | Thời gian phản hồi | 236.403 | 15.037 | 221.366 | 6.73536 | ms | Có |
| 2026-10-01 22:16:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:16:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:17:00 | Số truy vấn mỗi giây | 54.967 | 50.0685 | 4.8985 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:17:00 | Số kết nối đang mở | 34 | 30 | 4 | 15.5673 | kết nối | Không |
| 2026-10-01 22:17:00 | Thời gian phản hồi | 235.782 | 15.037 | 220.745 | 6.73536 | ms | Có |
| 2026-10-01 22:17:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:17:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:18:00 | Số truy vấn mỗi giây | 54.21 | 50.0685 | 4.1415 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:18:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:18:00 | Thời gian phản hồi | 240.21 | 15.037 | 225.173 | 6.73536 | ms | Có |
| 2026-10-01 22:18:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:18:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:19:00 | Số truy vấn mỗi giây | 54.197 | 50.0685 | 4.1285 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:19:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:19:00 | Thời gian phản hồi | 238.806 | 15.037 | 223.769 | 6.73536 | ms | Có |
| 2026-10-01 22:19:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:19:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:20:00 | Số truy vấn mỗi giây | 53.24 | 50.0685 | 3.1715 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:20:00 | Số kết nối đang mở | 33 | 30 | 3 | 15.5673 | kết nối | Không |
| 2026-10-01 22:20:00 | Thời gian phản hồi | 235.395 | 15.037 | 220.358 | 6.73536 | ms | Có |
| 2026-10-01 22:20:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:20:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:21:00 | Số truy vấn mỗi giây | 54.558 | 50.0685 | 4.4895 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:21:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 22:21:00 | Thời gian phản hồi | 231.255 | 15.037 | 216.218 | 6.73536 | ms | Có |
| 2026-10-01 22:21:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:21:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:22:00 | Số truy vấn mỗi giây | 53.877 | 50.0685 | 3.8085 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:22:00 | Số kết nối đang mở | 32 | 30 | 2 | 15.5673 | kết nối | Không |
| 2026-10-01 22:22:00 | Thời gian phản hồi | 234.315 | 15.037 | 219.278 | 6.73536 | ms | Có |
| 2026-10-01 22:22:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:22:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |
| 2026-10-01 22:23:00 | Số truy vấn mỗi giây | 51.994 | 50.0685 | 1.9255 | 20.3987 | truy vấn/giây | Không |
| 2026-10-01 22:23:00 | Số kết nối đang mở | 31 | 30 | 1 | 15.5673 | kết nối | Không |
| 2026-10-01 22:23:00 | Thời gian phản hồi | 236.556 | 15.037 | 221.519 | 6.73536 | ms | Có |
| 2026-10-01 22:23:00 | Truy vấn chậm mỗi khoảng lấy mẫu | 8 | 0 | 8 | 1 | truy vấn/khoảng | Có |
| 2026-10-01 22:23:00 | Kết nối thất bại mỗi khoảng lấy mẫu | 0 | 0 | 0 | 0 | lỗi/khoảng | Không |

## Việc nên kiểm tra tiếp

- Đối chiếu slow query log, kế hoạch thực thi, khóa chờ và tải CPU/I/O trong cùng khoảng thời gian.

## Đánh giá trên nhãn kiểm thử

Các chỉ số dưới đây được tính lại từ nhãn và dự đoán thực tế trên cùng phần kiểm tra. Lớp bất thường là -1; lớp bình thường là 1. Mẫu số bằng 0 được quy ước trả về 0.

### Sau cấu hình vận hành

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 1 | 1 | 1 | 1 | 389 | 0 | 0 | 43 |
| Isolation Forest | 1 | 0.55814 | 0.716418 | 0.956019 | 389 | 0 | 19 | 24 |
| LOF | 1 | 1 | 1 | 1 | 389 | 0 | 0 | 43 |
| One-Class SVM | 1 | 1 | 1 | 1 | 389 | 0 | 0 | 43 |

Ma trận nhầm lẫn mỗi thuật toán: hàng là nhãn thật [bình thường, bất thường], cột là dự đoán [bình thường, bất thường], tương ứng [[TN, FP], [FN, TP]].

### Dự đoán gốc của mô hình

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 0.472527 | 1 | 0.641791 | 0.888889 | 341 | 48 | 0 | 43 |
| Isolation Forest | 0.685714 | 0.55814 | 0.615385 | 0.930556 | 378 | 11 | 19 | 24 |
| LOF | 0.895833 | 1 | 0.945055 | 0.988426 | 384 | 5 | 0 | 43 |
| One-Class SVM | 0.843137 | 1 | 0.914894 | 0.981481 | 381 | 8 | 0 | 43 |

## Cấu hình và thời gian đo

- Bộ lọc vận hành: bật.
- Contamination/nu cấu hình: 0.01.
- Ngưỡng độ lệch vận hành: 3.5.
- MAD: huấn luyện 0.0002005 giây; dự đoán 6.55e-05 giây.
- Isolation Forest: huấn luyện 0.113309 giây; dự đoán 0.0160441 giây.
- LOF: huấn luyện 0.0079989 giây; dự đoán 0.0060049 giây.
- One-Class SVM: huấn luyện 0.001612 giây; dự đoán 0.0015534 giây.

Không suy ra tấn công, quá tải hay nguyên nhân gốc chỉ từ điểm bất thường. Đối chiếu nhật ký, truy vấn, tài nguyên máy chủ và bối cảnh vận hành trước khi kết luận.
