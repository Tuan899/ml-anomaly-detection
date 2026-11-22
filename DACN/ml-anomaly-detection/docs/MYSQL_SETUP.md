# Thu thập hoạt động MySQL bằng tài khoản giám sát

Mô-đun `src/mysql_collector.py` có thể được gọi riêng từ Python để thu một đợt mẫu thực tế và lưu CSV. Giao diện nhận dữ liệu mẫu hoặc CSV để phân tích theo thời gian. Không có máy chủ/tài khoản MySQL được cung cấp trong source; các unit test dùng giao thức giả lập để kiểm tra công thức và lỗi, không chứng minh đã kết nối một máy chủ thực.

## 1. Chuẩn bị tài khoản ít quyền

DBA thực hiện thủ công trên MySQL, thay địa chỉ máy thu thập và mật khẩu mẫu:

```sql
CREATE USER 'anomaly_monitor'@'10.0.0.12'
  IDENTIFIED BY 'THAY_BANG_MAT_KHAU_RIENG' REQUIRE SSL;
GRANT USAGE ON *.* TO 'anomaly_monitor'@'10.0.0.12';
SHOW GRANTS FOR 'anomaly_monitor'@'10.0.0.12';
```

`USAGE` không cấp quyền truy cập bảng. Với MySQL thông thường, `SHOW GLOBAL STATUS` và `SELECT 1` không cần quyền đọc các bảng ứng dụng. Không cấp mặc định `SELECT ON *.*`, `PROCESS`, `SUPER`, `SYSTEM_VARIABLES_ADMIN` hoặc các quyền ghi. Nếu dịch vụ MySQL được quản lý có chính sách riêng, DBA kiểm tra đúng quyền đọc trạng thái được nhà cung cấp yêu cầu; ứng dụng báo lỗi và không tự xin/cấp thêm quyền. Không dùng tài khoản quản trị chỉ để khắc phục lỗi thu thập.

Không truyền tham số `database` khi dùng tài khoản chỉ có `USAGE`: các chỉ số là trạng thái toàn máy chủ, không bị giới hạn theo CSDL. Chọn một CSDL mà tài khoản không có quyền truy cập có thể làm đăng nhập thất bại dù `SHOW GLOBAL STATUS` vẫn dùng được khi không chọn CSDL.

Mô-đun thu thập chỉ thực thi ba câu SQL cố định:

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

Mặc định mô-đun thu thập tạo SSLContext xác minh chứng chỉ máy chủ và tên máy. Truyền đường dẫn tệp CA PEM trên **máy thu thập** qua tham số `ssl_ca` nếu dùng CA nội bộ; nếu để `None`, dùng kho CA tin cậy của Python/hệ điều hành. Host phải khớp tên/IP trong chứng chỉ. Không bỏ xác minh chứng chỉ chỉ để vượt lỗi cấu hình CA.

Chỉ đặt `ssl_disabled=True` khi chủ động demo với máy MySQL cục bộ trong môi trường được kiểm soát. Tài khoản `REQUIRE SSL` ở trên sẽ từ chối chế độ này: muốn demo không TLS, DBA tạo riêng một tài khoản chỉ `USAGE` cho `localhost` theo chính sách của mình. Mô-đun không tự hạ yêu cầu TLS hoặc sửa tài khoản.

Kiểm tra kết nối thủ công trước khi demo, nhập mật khẩu ở lời nhắc thay vì đưa lên dòng lệnh:

```text
mysql --host=db.example.internal --port=3306 --user=anomaly_monitor --password --ssl-mode=VERIFY_IDENTITY --ssl-ca=ca.pem
```

Trong phiên kiểm tra, chạy ba câu SQL nêu trên. Nếu có lỗi, kiểm tra host/port, firewall, host của tài khoản, chứng chỉ CA, tên máy, mật khẩu và chính sách nhà cung cấp. Mô-đun trả thông báo lỗi đã lược bỏ nội dung nhạy cảm từ driver; dùng nhật ký máy chủ dưới quyền DBA để chẩn đoán sâu hơn. Mật khẩu không được đưa vào CSV kết quả hoặc metadata.

## 3. Ý nghĩa chính xác của các cột

| Cột | Cách đo | Giới hạn diễn giải |
|---|---|---|
| `timestamp` | Thời điểm phía máy thu thập nhận snapshot trạng thái, ISO 8601 UTC | Cần đồng bộ đồng hồ máy giám sát nếu đối chiếu nhật ký |
| `queries_per_second` | Chênh lệch `Questions` chia số giây thực giữa hai snapshot, dùng đồng hồ monotonic | Các câu lệnh giám sát cũng đóng góp vào bộ đếm; đây là tốc độ câu lệnh do client thực thi theo định nghĩa `Questions`, không bao gồm toàn bộ câu lệnh nội bộ của stored program |
| `connections` | `Threads_connected` tại snapshot | Có cả một kết nối của ứng dụng giám sát; đây là số kết nối hiện tại, không phải số lần kết nối mới |
| `response_time_ms` | Thời gian khứ hồi từ máy thu thập cho `SELECT 1`, gồm nhận kết quả | Chỉ là phép thăm dò phản hồi có ảnh hưởng của mạng/lịch chạy; không phải thời gian trung bình của truy vấn nghiệp vụ trên máy chủ |
| `slow_queries` | Chênh lệch `Slow_queries` trong khoảng lấy mẫu | Là số truy vấn vượt cấu hình `long_query_time` của MySQL, không phải bộ đếm tích lũy từ lúc khởi động hoặc tốc độ mỗi giây; ảnh hưởng bởi cấu hình máy chủ |
| `connection_errors` | Chênh lệch `Aborted_connects` trong khoảng lấy mẫu | Số lần thử kết nối thất bại theo bộ đếm MySQL; không bao quát mọi lỗi truyền tải/kết nối ở mọi lớp |

Không cộng `Connection_errors_*` với `Aborted_connects` vì các nhóm chỉ số có phạm vi khác nhau và có thể trùng lặp. Nếu cần điều tra lỗi accept, giới hạn kết nối, bộ nhớ hoặc xác thực, DBA xem riêng các bộ đếm lỗi và nhật ký tương ứng; số đo hiện tại không đủ để kết luận nguyên nhân.

Ứng dụng đọc một snapshot đầu để làm mốc, không dùng các số tích lũy có sẵn như sự kiện vừa xảy ra. Mỗi đợt trả đúng số hàng yêu cầu, nên cần số snapshot nhiều hơn một đơn vị. Chỉ khi máy chủ thực trả `0` hoặc chênh lệch thực bằng `0`, kết quả mới chứa `0`. Thiếu `Questions`, `Threads_connected`, `Slow_queries`, `Aborted_connects` hoặc `Uptime` sẽ báo lỗi; không thay bằng giá trị giả.

Nếu bộ đếm giảm (đặt lại bộ đếm/khởi động lại máy chủ), phép thăm dò lỗi, mất kết nối hoặc khoảng thời gian không hợp lệ, toàn bộ đợt thu thập thất bại và cần thu lại. Cơ chế này phát hiện reset khi quan sát được sự giảm, không bảo đảm phát hiện một reset rồi tăng trở lại trên mốc cũ giữa hai mẫu. Không tự nối lại rồi trộn các mốc thời gian khác nhau. Các bộ đếm rất lớn không tự bị chuyển thành số thực trước khi lấy hiệu.

## 4. Thu bằng Python rồi tải CSV vào giao diện

Từ thư mục gốc dự án, gọi mô-đun bằng Python đã cài `requirements.txt`. Thay host và đường dẫn CA cho máy chủ của bạn; đọc mật khẩu ở lời nhắc:

```python
from getpass import getpass
from src.mysql_collector import collect_mysql_metrics

frame = collect_mysql_metrics(
    host="db.example.internal",
    user="anomaly_monitor",
    password=getpass("Mật khẩu MySQL: "),
    samples=60,
    interval_seconds=1.0,
    ssl_ca="ca.pem",
)
frame.to_csv("mysql_real_metrics.csv", index=False)
```

Giới hạn của mô-đun: 4–600 mẫu, 0,1–60 giây giữa các mẫu; mặc định 60 mẫu × 1 giây. Thời gian thu thực dài hơn tích này vì còn thời gian kết nối và truy vấn. Mô-đun giữ một kết nối trong đợt và đóng khi hoàn tất hoặc lỗi. Bộ thu không tự tạo tải. Để diễn tập tạo tải trên máy chủ thử nghiệm, dùng tài khoản và công cụ riêng theo [hướng dẫn demo trực tiếp](DEMO_MONITORING.md#diễn-tập-bằng-tải-thật-trên-mysql-thử-nghiệm).

1. Khởi động backend và Streamlit theo README dự án.
2. Trong Cơ bản, chọn **Tải tệp CSV**; hoặc chọn **Nâng cao → Giám sát hệ quản trị CSDL → Tải CSV**. Tải `mysql_real_metrics.csv` và xem trước các cột.
3. Chọn phần thời gian đầu đã được quản trị viên xác nhận phù hợp làm nền huấn luyện; phần thời gian sau là tập đánh giá. Trong Nâng cao có thể chọn bốn thuật toán và tỷ lệ huấn luyện.
4. Chạy phân tích, xem biểu đồ, giá trị tại điểm cảnh báo và các chỉ số lệch nền. Đối chiếu với nhật ký truy vấn, log ứng dụng, giới hạn kết nối và sự kiện triển khai trước khi kết luận nguyên nhân.
5. Dữ liệu thực không tự có nhãn chuẩn. Muốn đo Precision/Recall/F1/confusion matrix, dùng CSV kiểm thử có nhãn được cung cấp hoặc bổ sung nhãn đã được kiểm chứng bằng quan sát bên ngoài; không suy diễn nhãn từ mô hình.

Các lần lấy mẫu ngắn rất dễ bị chi phối bởi hai câu truy vấn của chính công cụ và nhiễu mạng. Khi đánh giá triển khai thực, thu đủ các chu kỳ tải bình thường, dùng chu kỳ phù hợp và tách nền huấn luyện khỏi phần đánh giá theo thời gian.

## Tài liệu gốc

- [MySQL 8.4: SHOW STATUS](https://dev.mysql.com/doc/refman/8.4/en/show-status.html): phạm vi GLOBAL/SESSION và tác động của việc đọc trạng thái.
- [MySQL 8.4: Server Status Variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html): định nghĩa `Questions`, `Threads_connected`, `Slow_queries`, `Aborted_connects` và `Connection_errors_*`.
- [PyMySQL: Connection object](https://pymysql.readthedocs.io/en/latest/modules/connections.html): SSLContext, autocommit, timeout và các tùy chọn kết nối.
- [PyMySQL 1.2.3 changelog](https://github.com/PyMySQL/PyMySQL/blob/v1.2.3/CHANGELOG.md): hành vi bắt buộc TLS khi cung cấp SSLContext từ 1.2.0.
