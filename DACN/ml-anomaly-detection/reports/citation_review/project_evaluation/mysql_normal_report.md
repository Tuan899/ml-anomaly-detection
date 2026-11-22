# ANOMALY LAB — Báo cáo giám sát hoạt động MySQL

Nguồn dữ liệu: mysql_normal.csv

Dữ liệu mẫu tổng hợp phục vụ kiểm thử kịch bản; các kết quả này không xác nhận hiệu quả trên máy chủ thật.

## Phạm vi phân tích

- Tổng số bản ghi: 1,440.
- Bản ghi huấn luyện: 1,008.
- Bản ghi kiểm tra đã phân tích: 432.
- Thuật toán: MAD, Isolation Forest, LOF, One-Class SVM.
- Chia theo thứ tự thời gian; số liệu kết quả chỉ thuộc phần kiểm tra. Nhãn không được dùng làm đặc trưng học.
- Khoảng kiểm tra: 2026-10-01 16:48:00 → 2026-10-01 23:59:00 UTC.

## Kết quả

Trạng thái: **Bình thường**.

Số bản ghi được mô hình đánh dấu ban đầu (hợp các thuật toán): 53.
Số bản ghi cảnh báo sau cấu hình vận hành (mỗi thời điểm chỉ tính một lần): 0 (0.00%).

Không có cảnh báo vận hành trong 432 bản ghi kiểm tra theo cấu hình hiện tại. Các dao động nhỏ trong khoảng tham chiếu không tự động trở thành cảnh báo. Mô hình đánh dấu 53 bản ghi ban đầu; bộ lọc vận hành đã loại các điểm này. Kết quả này không bảo đảm máy chủ không có sự cố.

## Vì sao hệ thống cảnh báo?

Các chỉ số là dấu hiệu có thể kiểm chứng, chưa phải nguyên nhân đã xác minh. Dữ liệu kết nối thất bại không phải tỷ lệ truy vấn lỗi; chưa có số truy vấn lỗi để tính tỷ lệ này.

Quy tắc mức cảnh báo của bản demo: chỉ xét các bản ghi đã được mô hình cảnh báo sau cấu hình vận hành. Một điểm có mức Cảnh báo cao khi ít nhất hai chỉ số vượt khoảng tham chiếu học từ tập huấn luyện; hoặc độ lệch của một chỉ số lớn hơn hai lần dung sai dương; hoặc kết nối thất bại tăng từ mức tham chiếu bằng 0. Toàn bộ lần phân tích có mức Cảnh báo cao nếu có điểm như trên hoặc ít nhất 10% bản ghi kiểm tra được cảnh báo. Có cảnh báo còn lại là Cần chú ý; không có cảnh báo là Bình thường. Đây là quy ước vận hành minh họa, không phải giới hạn MySQL hay SLA đã được xác nhận; bản thân quy tắc này không tạo dự đoán mô hình.

Điểm hiển thị = âm điểm quyết định gốc; điểm càng lớn càng nghi ngờ trong cùng thuật toán. Không so sánh trực tiếp điểm giữa các thuật toán.

Không có thời điểm cảnh báo theo cấu hình hiện tại.

## Việc nên kiểm tra tiếp

- Tiếp tục thu thập số liệu và đối chiếu log vận hành; kiểm tra lại khoảng học có đại diện cho hoạt động bình thường hay không.

## Đánh giá trên nhãn kiểm thử

Các chỉ số dưới đây được tính lại từ nhãn và dự đoán thực tế trên cùng phần kiểm tra. Lớp bất thường là -1; lớp bình thường là 1. Mẫu số bằng 0 được quy ước trả về 0.

### Sau cấu hình vận hành

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 0 | 0 | 0 | 1 | 432 | 0 | 0 | 0 |
| Isolation Forest | 0 | 0 | 0 | 1 | 432 | 0 | 0 | 0 |
| LOF | 0 | 0 | 0 | 1 | 432 | 0 | 0 | 0 |
| One-Class SVM | 0 | 0 | 0 | 1 | 432 | 0 | 0 | 0 |

Ma trận nhầm lẫn mỗi thuật toán: hàng là nhãn thật [bình thường, bất thường], cột là dự đoán [bình thường, bất thường], tương ứng [[TN, FP], [FN, TP]].

### Dự đoán gốc của mô hình

| Thuật toán | Precision | Recall | F1-score | Accuracy | TN | FP | FN | TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 0 | 0 | 0 | 0.888889 | 384 | 48 | 0 | 0 |
| Isolation Forest | 0 | 0 | 0 | 0.974537 | 421 | 11 | 0 | 0 |
| LOF | 0 | 0 | 0 | 0.988426 | 427 | 5 | 0 | 0 |
| One-Class SVM | 0 | 0 | 0 | 0.981481 | 424 | 8 | 0 | 0 |

Phần kiểm tra không có nhãn bất thường; Recall/F1 không đủ để đánh giá khả năng phát hiện. Hãy kiểm tra số báo nhầm (FP).

## Cấu hình và thời gian đo

- Bộ lọc vận hành: bật.
- Contamination/nu cấu hình: 0.01.
- Ngưỡng độ lệch vận hành: 3.5.
- MAD: huấn luyện 0.0017952 giây; dự đoán 0.0001174 giây.
- Isolation Forest: huấn luyện 0.108736 giây; dự đoán 0.0135674 giây.
- LOF: huấn luyện 0.0093177 giây; dự đoán 0.005395 giây.
- One-Class SVM: huấn luyện 0.0024921 giây; dự đoán 0.0020924 giây.

Không suy ra tấn công, quá tải hay nguyên nhân gốc chỉ từ điểm bất thường. Đối chiếu nhật ký, truy vấn, tài nguyên máy chủ và bối cảnh vận hành trước khi kết luận.
