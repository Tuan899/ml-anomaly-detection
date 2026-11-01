# Dữ liệu kiểm thử: lỗi đầu vào và điểm bất thường

Các CSV trong thư mục này là dữ liệu giả lập, được tạo để thử chương trình.
Chúng không phải số đo thực tế và không chứng minh độ chính xác trên dữ liệu thực.
Cột `value` là một chỉ số giả lập chung, không phải CPU phần trăm từ nguồn thực.

## Làm sao biết dữ liệu có sai?

Trước hết, cần phân biệt hai tình huống:

- **Dữ liệu đầu vào bị lỗi:** ngày giờ không hợp lệ, thời gian trùng, thiếu giá trị,
  chữ trong cột số hoặc cấu trúc CSV sai. Chương trình kiểm tra được các lỗi này.
  Một số lỗi khiến phân tích dừng; dòng có giá trị thiếu, không phải số hoặc vô hạn
  sẽ bị loại và được thống kê.
- **Giá trị hợp lệ nhưng khác thường:** chẳng hạn chuỗi thường quanh 50 nhưng
  xuất hiện 95 hoặc 8. Mô hình có thể cảnh báo điểm này. Để biết đó là lỗi nhập liệu,
  lỗi cảm biến hay sự kiện thực tế, cần đối chiếu nguồn gốc, đơn vị, quy tắc nghiệp
  vụ và các số đo liên quan.

Ứng dụng hiện kiểm tra định dạng và phát hiện khác thường theo thống kê. Nó không
tự biết giới hạn nghiệp vụ của từng chỉ số. Ví dụ, nếu đơn vị được xác nhận là CPU
phần trăm thì số đo ngoài 0–100 cần kiểm tra, còn CPU 95 có thể là tải cao thực sự.
Một điểm không được cảnh báo cũng chưa bảo đảm dữ liệu đúng.

Khi có số liệu đã được xác minh, thêm cột `is_anomaly`: **`1` = bình thường,
`-1` = bất thường**. Nhãn này dùng để đối chiếu kết quả, không đưa vào huấn luyện.
Không nên gắn nhãn chỉ vì chính mô hình đã cảnh báo, vì như vậy sẽ không có căn cứ
độc lập để đánh giá.

## Thử phát hiện bất thường trước

1. Mở ứng dụng. Trong **1. Chọn dữ liệu**, chọn **Tải CSV của bạn** và tải
   [02_bat_thuong_co_nhan.csv](./02_bat_thuong_co_nhan.csv).
2. Ở thanh bên, chọn **Cột thời gian** = `timestamp`, **Cột giá trị** = `value`,
   **Nhãn tham chiếu (tùy chọn)** = `is_anomaly`. Mặc định không dùng nhãn,
   nên cần chọn cột này để có bảng đánh giá.
3. Trong **Thuật toán**, chỉ giữ **MAD · độ lệch so với trung vị** cho lần thử đầu.
   Đặt **Dữ liệu dùng huấn luyện (%)** = **70**; giữ **Tỷ lệ bất thường dự kiến (%)**
   = **1**. Trong **Tùy chọn nâng cao**, bỏ chọn **Thêm đặc trưng chu kỳ thời gian**.
4. Bấm **Chạy phát hiện**. Bộ này có 200 dòng: 140 dòng đầu để học trạng thái
   thường gặp, 60 dòng cuối để kiểm tra. Ba điểm bất thường được chèn đều ở phần
   kiểm tra, tại điểm thứ **152, 173, 186** nếu đếm từ 1 và không tính dòng tên cột;
   giá trị tương ứng là **95, 8, 90**. Chúng mang nhãn `-1`, còn các điểm khác mang
   nhãn `1`. Các thời điểm trong tệp là:
   - `2026-10-01 12:35:00` → `95` (dòng CSV 153, tính cả dòng tên cột).
   - `2026-10-01 14:20:00` → `8` (dòng CSV 174).
   - `2026-10-01 15:25:00` → `90` (dòng CSV 187).
5. Trong **Tổng quan**, xem biểu đồ và mở **Chất lượng dữ liệu và cách chia tập**.
   Trong **Chi tiết**, chọn MAD và bộ lọc **Chỉ cảnh báo** để xem từng điểm. Đối chiếu
   thời gian, giá trị đo và nhãn tham chiếu; có thể tải **Tải dự đoán CSV** để kiểm tra.
6. Mở **Đánh giá**: **Cảnh báo đúng** là điểm có nhãn `-1` được phát hiện;
   **Cảnh báo nhầm** là điểm có nhãn `1` nhưng bị cảnh báo; **Bỏ sót** là điểm có
   nhãn `-1` không được phát hiện. Bảng này chỉ xét 60 điểm kiểm tra.
   Với cấu hình trên, MAD đã được chạy kiểm tra: **3 cảnh báo đúng, 0 cảnh báo nhầm,
   0 bỏ sót**; Precision, Recall và F1 đều **100%** trên bộ giả lập này.
7. Chạy lại với [01_binh_thuong.csv](./01_binh_thuong.csv) theo cùng cấu hình.
   Tệp này không có điểm bất thường được chèn, giúp kiểm tra cảnh báo nhầm.
   Với cấu hình trên, MAD đã được chạy kiểm tra và cho **0 cảnh báo**. Vì không có
   nhãn `-1`, F1 hiển thị **0%** theo cách tính hiện tại; điều đó không có nghĩa mô
   hình sai. Không dùng Recall/F1 của riêng tệp này để kết luận khả năng tìm bất thường.

Sau đó có thể chọn thêm Isolation Forest, LOF và One-Class SVM để so sánh.
Chúng có thể cảnh báo thêm hoặc bỏ sót; nhiều cảnh báo hơn không đồng nghĩa chính
xác hơn. Tham số tỷ lệ 1% không bảo đảm số cảnh báo bằng đúng 1% tập kiểm tra;
MAD dùng ngưỡng robust Z-score riêng là 3,5.

Kết quả đã chạy trên cùng bộ dữ liệu và cấu hình mặc định nêu trên:

| Thuật toán | CSV 01: cảnh báo nhầm | CSV 02: cảnh báo đúng / cảnh báo nhầm / bỏ sót |
|---|---:|---:|
| MAD | 0 | 3 / 0 / 0 |
| Isolation Forest | 1 | 3 / 1 / 0 |
| LOF | 1 | 3 / 1 / 0 |
| One-Class SVM | 2 | 3 / 2 / 0 |

Bảng này xác nhận chương trình tìm được ba giá trị đã chèn trong bộ minh họa;
không dùng tỷ lệ 100% của MAD để suy ra kết quả trên dữ liệu thực hoặc bộ khác.

Nếu đổi tệp, nhãn hoặc cấu hình, cần bấm **Chạy phát hiện** lại. Kết quả cũ bị ẩn
để tránh nhầm lẫn giữa các lần thử.

## Các tệp lỗi để kiểm tra xử lý đầu vào

Dùng lần lượt từng tệp bên dưới, với `timestamp` làm cột thời gian và `value`
làm cột giá trị. Chỉ tệp thử nhãn yêu cầu chọn `is_anomaly` để kích hoạt lỗi nhãn.

| Tệp | Điều cần kiểm tra | Kết quả mong đợi |
|---|---|---|
| [01_binh_thuong.csv](./01_binh_thuong.csv) | 200 số đo giả lập trong vùng thường gặp, nhãn đều `1`. | Đọc và phân tích được; dùng để kiểm tra cảnh báo nhầm theo từng mô hình. |
| [02_bat_thuong_co_nhan.csv](./02_bat_thuong_co_nhan.csv) | 200 số đo, có 3 giá trị bất thường đã gắn nhãn `-1` trong phần kiểm tra. | Đọc được; khi chọn nhãn, có bảng đối chiếu phát hiện đúng, cảnh báo nhầm và bỏ sót. |
| [03_thoi_gian_sai.csv](./03_thoi_gian_sai.csv) | Một timestamp không phải ngày giờ hợp lệ. | Báo lỗi thời gian và chặn phân tích; sửa timestamp trong nguồn dữ liệu. |
| [04_trung_thoi_gian.csv](./04_trung_thoi_gian.csv) | Hai dòng có cùng timestamp. | Báo lỗi trùng thời gian và chặn phân tích; xác minh, loại dòng trùng hoặc tổng hợp theo quy tắc phù hợp trước khi tải lại. |
| [05_gia_tri_loi.csv](./05_gia_tri_loi.csv) | 20 dòng, gồm 6 giá trị lỗi: trống, chữ, `inf`, `-inf`, `NaN`, sai cách ghi số thập phân. | Cảnh báo loại 6 dòng, còn 14 dòng hợp lệ. Với tỷ lệ 70%: 9 dòng học, 5 dòng kiểm tra; phân tích được phần còn lại. |
| [06_nhan_sai.csv](./06_nhan_sai.csv) | Giá trị và thời gian hợp lệ, nhưng nhãn dùng `0/1`. | Nếu chọn `is_anomaly` rồi chạy: báo lỗi vì nhãn phải là `1/-1`. Nếu giữ **Không dùng nhãn**, vẫn phân tích giá trị được và không có đánh giá nhãn. |
| [07_sai_so_cot.csv](./07_sai_so_cot.csv) | Các dòng dữ liệu có nhiều trường hơn dòng tên cột. | Báo lỗi định dạng CSV và chặn phân tích; sửa dấu phân cách hoặc số trường. |
| [08_ten_cot_trung.csv](./08_ten_cot_trung.csv) | Tên cột bị lặp. | Báo lỗi tên cột trùng và chặn phân tích; đặt tên riêng cho từng cột. |
| [09_qua_it_du_lieu.csv](./09_qua_it_du_lieu.csv) | Chỉ có 3 dòng hợp lệ. | Báo chưa đủ dữ liệu để chia tập; nút **Chạy phát hiện** bị vô hiệu. Cần ít nhất 3 dòng huấn luyện và 1 dòng kiểm tra. |

Các tệp nhỏ dùng để kiểm tra thông báo và thao tác, không dùng để đánh giá độ
chính xác. Cảnh báo ít dữ liệu ở các tệp này là hành vi dự kiến.

## Tự kiểm tra dữ liệu thật

Trước khi phân tích, xác nhận nguồn và đơn vị đo; kiểm tra ngày giờ, khoảng lấy
mẫu, dòng trùng, ô trống và giới hạn hợp lý của chỉ số. Sau khi chạy, kiểm tra
số dòng bị loại để tránh bỏ qua nhiều lỗi nguồn. Với mỗi điểm được gắn cờ, so
sánh với log hoặc sự kiện cùng thời điểm và người phụ trách dữ liệu.

Muốn đánh giá chất lượng, cần thêm nhiều dữ liệu thực đã được xác minh, bao gồm
cả giai đoạn bình thường và các sự cố đã biết. Dùng các sự cố có nhãn trong phần
kiểm tra và xem cả cảnh báo nhầm lẫn bỏ sót; không chỉ nhìn số điểm được cảnh báo.
