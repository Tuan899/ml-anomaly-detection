# Thu thập hoạt động MySQL bằng tài khoản giám sát

Ứng dụng thu một đợt mẫu thực tế, sau đó phân tích theo thời gian. CSV vẫn là lựa chọn demo ngoại tuyến. Không có máy chủ/tài khoản MySQL được cung cấp trong source; các unit test dùng giao thức giả lập để kiểm tra công thức và lỗi, không chứng minh đã kết nối một máy chủ thực.

## 1. Chuẩn bị tài khoản ít quyền

DBA thực hiện thủ công trên MySQL, thay địa chỉ máy chạy Streamlit và mật khẩu mẫu:

```sql
CREATE USER 'anomaly_monitor'@'10.0.0.12'
  IDENTIFIED BY 'THAY_BANG_MAT_KHAU_RIENG' REQUIRE SSL;
GRANT USAGE ON *.* TO 'anomaly_monitor'@'10.0.0.12';
SHOW GRANTS FOR 'anomaly_monitor'@'10.0.0.12';
```

`USAGE` không cấp quyền truy cập bảng. Với MySQL thông thường, `SHOW GLOBAL STATUS` và `SELECT 1` không cần quyền đọc các bảng ứng dụng. Không cấp mặc định `SELECT ON *.*`, `PROCESS`, `SUPER`, `SYSTEM_VARIABLES_ADMIN` hoặc các quyền ghi. Nếu dịch vụ MySQL được quản lý có chính sách riêng, DBA kiểm tra đúng quyền đọc trạng thái được nhà cung cấp yêu cầu; ứng dụng báo lỗi và không tự xin/cấp thêm quyền. Không dùng tài khoản quản trị chỉ để khắc phục lỗi thu thập.

Để trống trường **CSDL** khi dùng tài khoản chỉ có `USAGE`: các chỉ số là trạng thái toàn máy chủ, không bị giới hạn theo CSDL. Chọn một CSDL mà tài khoản không có quyền truy cập có thể làm đăng nhập thất bại dù `SHOW GLOBAL STATUS` vẫn dùng được khi không chọn CSDL.

Ứng dụng chỉ thực thi ba câu SQL cố định:

```sql
SET SESSION TRANSACTION READ ONLY;
SELECT 1;
SHOW GLOBAL STATUS;
```

Câu `SET SESSION` chỉ đặt chế độ giao dịch cho phiên giám sát, không thay cấu hình toàn máy chủ. Kết nối bật autocommit, không giữ giao dịch trong lúc chờ mẫu. Driver có thể thực thi cấu hình phiên như `SET NAMES utf8mb4` khi khởi tạo. Ứng dụng không chạy SQL do người dùng nhập, không ghi bảng, không tạo tài khoản và không cấp quyền. Cài đặt phiên này không thay thế việc DBA kiểm tra quyền thực tế của tài khoản.

## 2. TLS và kết nối

```powershell
python -m pip install -r requirements.txt
```

Driver yêu cầu `PyMySQL[rsa]>=1.2.3,<2`. Từ PyMySQL 1.2.0, truyền `ssl.SSLContext` yêu cầu TLS thay vì tự hạ xuống kết nối không mã hóa; dự án yêu cầu 1.2.3 trở lên và kiểm tra phiên bản lúc chạy. Extra `rsa` hỗ trợ xác thực `caching_sha2_password` trong trường hợp demo cục bộ không dùng TLS.

Mặc định ứng dụng tạo SSLContext xác minh chứng chỉ máy chủ và tên máy. Nhập đường dẫn tệp CA PEM trên **máy chạy Streamlit** nếu dùng CA nội bộ; nếu để trống, dùng kho CA tin cậy của Python/hệ điều hành. Host phải khớp tên/IP trong chứng chỉ. Không bỏ xác minh chứng chỉ chỉ để vượt lỗi cấu hình CA.

Chỉ đánh dấu tắt TLS khi chủ động demo với máy MySQL cục bộ trong môi trường được kiểm soát. Tài khoản `REQUIRE SSL` ở trên sẽ từ chối chế độ này: muốn demo không TLS, DBA tạo riêng một tài khoản chỉ `USAGE` cho `localhost` theo chính sách của mình. Ứng dụng không tự hạ yêu cầu TLS hoặc sửa tài khoản.

Kiểm tra kết nối thủ công trước khi demo, nhập mật khẩu ở lời nhắc thay vì đưa lên dòng lệnh:

```text
mysql --host=db.example.internal --port=3306 --user=anomaly_monitor --password --ssl-mode=VERIFY_IDENTITY --ssl-ca=ca.pem
```

Trong phiên kiểm tra, chạy ba câu SQL nêu trên. Nếu có lỗi, kiểm tra host/port, firewall, host của tài khoản, chứng chỉ CA, tên máy, mật khẩu và chính sách nhà cung cấp. Giao diện chỉ hiển thị thông báo lỗi đã lược bỏ nội dung nhạy cảm từ driver; dùng nhật ký máy chủ dưới quyền DBA để chẩn đoán sâu hơn. Mật khẩu không được đưa vào CSV kết quả hoặc metadata; Streamlit vẫn cần giữ giá trị trường mật khẩu trong phiên người dùng đang hoạt động.

## 3. Ý nghĩa chính xác của các cột

| Cột | Cách đo | Giới hạn diễn giải |
|---|---|---|
| `timestamp` | Thời điểm phía máy Streamlit nhận snapshot trạng thái, ISO 8601 UTC | Cần đồng bộ đồng hồ máy giám sát nếu đối chiếu nhật ký |
| `queries_per_second` | Chênh lệch `Questions` chia số giây thực giữa hai snapshot, dùng đồng hồ monotonic | Các câu lệnh giám sát cũng đóng góp vào bộ đếm; đây là tốc độ câu lệnh do client thực thi theo định nghĩa `Questions`, không bao gồm toàn bộ câu lệnh nội bộ của stored program |
| `connections` | `Threads_connected` tại snapshot | Có cả một kết nối của ứng dụng giám sát; đây là số kết nối hiện tại, không phải số lần kết nối mới |
| `response_time_ms` | Thời gian khứ hồi từ máy Streamlit cho `SELECT 1`, gồm nhận kết quả | Chỉ là phép thăm dò phản hồi có ảnh hưởng của mạng/lịch chạy; không phải thời gian trung bình của truy vấn nghiệp vụ trên máy chủ |
| `slow_queries` | Chênh lệch `Slow_queries` trong khoảng lấy mẫu | Là số truy vấn vượt cấu hình `long_query_time` của MySQL, không phải bộ đếm tích lũy từ lúc khởi động hoặc tốc độ mỗi giây; ảnh hưởng bởi cấu hình máy chủ |
| `connection_errors` | Chênh lệch `Aborted_connects` trong khoảng lấy mẫu | Số lần thử kết nối thất bại theo bộ đếm MySQL; không bao quát mọi lỗi truyền tải/kết nối ở mọi lớp |

Không cộng `Connection_errors_*` với `Aborted_connects` vì các nhóm chỉ số có phạm vi khác nhau và có thể trùng lặp. Nếu cần điều tra lỗi accept, giới hạn kết nối, bộ nhớ hoặc xác thực, DBA xem riêng các bộ đếm lỗi và nhật ký tương ứng; số đo hiện tại không đủ để kết luận nguyên nhân.

Ứng dụng đọc một snapshot đầu để làm mốc, không dùng các số tích lũy có sẵn như sự kiện vừa xảy ra. Mỗi đợt trả đúng số hàng yêu cầu, nên cần số snapshot nhiều hơn một đơn vị. Chỉ khi máy chủ thực trả `0` hoặc chênh lệch thực bằng `0`, kết quả mới chứa `0`. Thiếu `Questions`, `Threads_connected`, `Slow_queries`, `Aborted_connects` hoặc `Uptime` sẽ báo lỗi; không thay bằng giá trị giả.

Nếu bộ đếm giảm (đặt lại bộ đếm/khởi động lại máy chủ), phép thăm dò lỗi, mất kết nối hoặc khoảng thời gian không hợp lệ, toàn bộ đợt thu thập thất bại và cần thu lại. Cơ chế này phát hiện reset khi quan sát được sự giảm, không bảo đảm phát hiện một reset rồi tăng trở lại trên mốc cũ giữa hai mẫu. Không tự nối lại rồi trộn các mốc thời gian khác nhau. Các bộ đếm rất lớn không tự bị chuyển thành số thực trước khi lấy hiệu.

## 4. Demo dữ liệu thực

1. Khởi động backend và Streamlit theo README dự án.
2. Chọn chế độ MySQL; nhập host, port, tài khoản giám sát, mật khẩu và CA nếu cần. Để trống CSDL khi dùng `USAGE`.
3. Chọn số mẫu và khoảng chờ. Giới hạn: 4–600 mẫu, 0,1–60 giây giữa các mẫu; mặc định 60 mẫu × 1 giây. Thời gian thu thực dài hơn tích này vì còn thời gian kết nối và truy vấn. Giao diện cập nhật tiến độ sau mỗi mẫu.
4. Bấm thu thập. Ứng dụng giữ một kết nối trong đợt và đóng khi hoàn tất hoặc lỗi. Không tạo tải bất thường lên máy thật chỉ để có cảnh báo.
5. Xem trước các cột và tải CSV để lưu lại quan sát thực. Dữ liệu thu trực tiếp không tự có nhãn chuẩn; không tạo Precision/Recall/F1 từ dự đoán của chính thuật toán.
6. Chọn phần thời gian đầu đã được quản trị viên xác nhận phù hợp làm nền huấn luyện, chọn các chỉ số và bốn thuật toán. Phần thời gian sau là tập đánh giá. Chỉ gọi trạng thái ổn định theo phạm vi thời gian và thuật toán đang xem.
7. Xem biểu đồ, giá trị tại điểm cảnh báo và các chỉ số lệch nền. Đối chiếu với nhật ký truy vấn, log ứng dụng, giới hạn kết nối và sự kiện triển khai trước khi kết luận nguyên nhân.
8. Muốn đo Precision/Recall/F1/confusion matrix, dùng hai CSV kiểm thử có nhãn được cung cấp hoặc bổ sung nhãn đã được kiểm chứng bằng quan sát bên ngoài; không suy diễn nhãn từ mô hình.

Các lần lấy mẫu ngắn rất dễ bị chi phối bởi hai câu truy vấn của chính công cụ và nhiễu mạng. Khi đánh giá triển khai thực, thu đủ các chu kỳ tải bình thường, dùng chu kỳ phù hợp và tách nền huấn luyện khỏi phần đánh giá theo thời gian.

## Tài liệu gốc

- [MySQL 8.4: SHOW STATUS](https://dev.mysql.com/doc/refman/8.4/en/show-status.html): phạm vi GLOBAL/SESSION và tác động của việc đọc trạng thái.
- [MySQL 8.4: Server Status Variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html): định nghĩa `Questions`, `Threads_connected`, `Slow_queries`, `Aborted_connects` và `Connection_errors_*`.
- [PyMySQL: Connection object](https://pymysql.readthedocs.io/en/latest/modules/connections.html): SSLContext, autocommit, timeout và các tùy chọn kết nối.
- [PyMySQL 1.2.3 changelog](https://github.com/PyMySQL/PyMySQL/blob/v1.2.3/CHANGELOG.md): hành vi bắt buộc TLS khi cung cấp SSLContext từ 1.2.0.
