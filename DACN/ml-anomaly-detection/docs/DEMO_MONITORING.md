# Demo giám sát, đồng thuận và chứng cứ

Chế độ mặc định **Giám sát trực tuyến** có ba màn hình: **Giám sát & Cảnh báo**,
**Điều khiển demo**, **Đối chiếu thuật toán**. Backend chấm điểm và phát lại
độc lập với tab trình duyệt; chuyển màn hình hoặc tải lại trang không làm mất
mức nền, số đo hay phản hồi đã ghi vào SQLite.

## Khởi động

Tại thư mục dự án, chạy `CHAY_UNG_DUNG.bat`. Launcher kiểm tra cả API mới
`/monitor/health`, danh mục chứng cứ và API tạo tải; nếu phiên cũ còn chiếm cổng, nó mở phiên mới ở cổng trống
và in địa chỉ cụ thể. Luôn dùng địa chỉ mới được in ra, không mặc định rằng
mọi phiên đều nằm ở 8501.

Nếu chạy riêng bằng PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Mở terminal thứ hai trong cùng thư mục:

```powershell
$env:ANOMALY_API_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501 --server.runOnSave true
```

Địa chỉ API có thể đổi bằng `ANOMALY_API_URL`. Dữ liệu mặc định nằm ở
`.runtime/monitoring.sqlite3`; đổi bằng `ANOMALY_MONITOR_DB` **trước khi chạy Backend**.
Giữ tệp này trong thư mục tin cậy: nó chứa cả mô hình được ứng dụng tự tạo.
Không nhận mô hình pickle từ người dùng. Bản này phục vụ demo cục bộ, chưa có
đăng nhập/phân quyền để mở trực tiếp ra Internet.

## Luồng diễn tập 5 phút

Để xem cảnh báo ngay, tại **Giám sát & Cảnh báo** bấm **Chạy demo cảnh báo K3**.
Nếu chưa có nền, thao tác này học 300 mẫu K1 bình thường riêng rồi phát K1
mỗi giây và chèn 15 mẫu K3. Cảnh báo xuất hiện theo kết quả thực của bốn mô
hình ở các mẫu tiếp theo. Nút này chỉ dùng cho nền K1/nguồn mô phỏng; không
thay nền riêng hoặc ngắt nguồn trực tiếp. Lịch sử trước đó được giữ lại.

Khối **Cảnh báo đã ghi nhận** nằm ngay đầu màn hình, trước các thẻ chỉ số
và biểu đồ. Nó đếm mức nghiêm trọng/cảnh báo/theo dõi trong tối đa 100 điểm
có phiếu gần nhất của mức nền đang chọn. Cảnh báo đã lưu vẫn hiện khi nguồn
dừng hoặc mẫu mới trở lại bình thường; trạng thái nguồn và mẫu mới nhất
được ghi riêng. Chi tiết và phản hồi nằm trong nhật ký phía trên biểu đồ.

1. Mở **Điều khiển demo**, giữ **K1 bình thường**, chọn 300 mẫu và bấm
   **Học mức nền**. Đây là dữ liệu riêng, không lấy từ cửa sổ kiểm tra K1–K4.
2. Giữ **Phát lại mô phỏng**, K1, chu kỳ **1 giây**, bấm **Bắt đầu phát lại**.
   Sang **Giám sát & Cảnh báo**: chờ mẫu đầu tiên, xem trạng thái nguồn và năm thẻ chỉ số.
3. Về **Điều khiển demo**, bấm **K2 · Tăng truy vấn**, rồi sang giám sát.
   15 mẫu tiếp theo được chèn QPS cao. Thẻ cảnh báo ghi thời điểm, giá trị/mức nền,
   độ lệch, các thuật toán bỏ phiếu và mức đồng thuận thực tế.
4. Chọn một cảnh báo và lưu **Xác nhận sự cố thật** hoặc **Cảnh báo giả** kèm ghi chú.
   Tải lại trang để đối chiếu phản hồi vẫn còn. Phản hồi không tự đổi nhãn chuẩn
   và không âm thầm huấn luyện lại mô hình.
5. Thử K3 (kết nối/lỗi) hoặc K4 (độ trễ/truy vấn chậm). Mở **Đối chiếu thuật toán**,
   chọn cùng nguồn/mức nền, bật/tắt **Xem dự đoán gốc của mô hình** để đối chiếu
   kết quả trước/sau lọc. Xem Precision, Recall, F1, FP, FN và bốn ma trận nhầm lẫn.
6. Tải chứng cứ CSV/JSON. Bấm **Dừng nguồn**: giao diện chuyển sang thông báo
   dữ liệu lịch sử, không tiếp tục khẳng định hệ thống hiện tại bình thường.

Để xem trọn một sự cố có sẵn, phát riêng K2, K3 hoặc K4. Mỗi kịch bản có 180
mẫu; sự cố nằm ở chỉ số 60–89 (đếm từ 0). Ở chu kỳ 1 giây, sự cố bắt đầu sau
khoảng một phút. Có thể dùng 0,1 giây khi thử thao tác; điều đó thay tốc độ phát,
không thay giá trị, nhãn hay tham số mô hình.

## Dữ liệu và mức đồng thuận

Các kịch bản do `src/demo_scenarios.py` sinh với seed cố định, không chọn theo
điểm số mô hình. Tạo lại CSV bằng:

```powershell
.\.venv\Scripts\python.exe scripts/generate_replay_scenarios.py
```

| Tệp trong `resources/replay/` | Vai trò |
|---|---|
| `baseline_K1.csv` | 300 mẫu bình thường chỉ dùng để học nền |
| `K1.csv` | 180 mẫu bình thường dành cho phát lại/đánh giá |
| `K2.csv` | 30 mẫu tăng QPS lên 300–350 trong 180 mẫu |
| `K3.csv` | 30 mẫu tăng kết nối lên 120–180, lỗi kết nối lên 5–10 |
| `K4.csv` | 30 mẫu tăng phản hồi lên 180–220 ms, truy vấn chậm lên 8–10 |

Mỗi dòng là một giây theo thời gian nguồn có múi giờ UTC+07:00. Thời gian
nguồn được giữ trong tooltip; trục đồ thị dùng thời gian Backend nhận mẫu để
việc phát lại không làm đường tín hiệu chạy ngược. Bộ đếm sự kiện là số phát
sinh trong khoảng lấy mẫu, không phải tổng tích lũy. Manifest lưu tại
`docs/replay_scenarios_manifest.json`. Đây là **dữ liệu giả lập**, không phải
đo trên CSDL thật và không chứng minh độ chính xác trong vận hành thực tế.

Mỗi mẫu được cùng một StandardScaler cố định chuyển đổi rồi chấm bởi MAD,
Isolation Forest, LOF và One-Class SVM. MAD dùng robust Z-score 3,5; ba mô hình
còn lại giữ cấu hình của pipeline hiện tại. Điểm quyết định không phải xác suất.
Bộ lọc vận hành giữ phiếu khi mô hình gắn cờ **và** có ít nhất một chỉ số lệch
quá dung sai học từ nền. Cả phiếu thô lẫn sau lọc đều được giữ lại.

| Số phiếu sau lọc | Mức |
|---|---|
| 0/4 | Chưa có cảnh báo trên mẫu đó |
| 1/4 | Theo dõi, ghi nhật ký nhẹ |
| 2/4 | Cảnh báo vàng |
| 3–4/4 | Nghiêm trọng, cảnh báo đỏ |

Đây là quy tắc minh họa, không phải bảo đảm phát hiện mọi sự cố hay xác suất
sự cố. Các mô hình có thể cùng sai; bộ lọc có thể che bất thường quan hệ giữa
các chỉ số. Vì vậy luôn đối chiếu dự đoán thô và sau lọc trên **cùng mẫu, cùng
phiên mức nền**. Không hứa trước thuật toán nào thắng hoặc cả bốn luôn đồng ý.

## Học lại từ dữ liệu riêng

Tải CSV có `timestamp` và năm cột `queries_per_second`, `connections`,
`response_time_ms`, `slow_queries`, `connection_errors`. Chọn một khoảng bình
thường ít nhất 30 mẫu. Nếu có `label`, khoảng đã chọn không được chứa `-1`.
Ứng dụng không tự bỏ dòng bất thường để cải thiện điểm đánh giá.

Chỉ khoảng được chọn tham gia học scaler, mô hình và dung sai. Mọi mẫu chấm
điểm phải có thời gian nguồn sau cuối khoảng nền. Nền mới có phiên riêng;
lịch sử cũ giữ phiên mô hình đã chấm nó. Đánh giá mặc định chỉ dùng phiên nền
hiện hành; bộ chọn trong màn hình đối chiếu cho phép xem các phiên có lịch sử.
Khi dùng các kịch bản demo đi kèm, học nền K1 đi kèm để có khoảng thời gian và
ý nghĩa chỉ số phù hợp.

## Bộ thu trực tiếp chạy độc lập

Chức năng này cần một máy chủ và tài khoản giám sát đã được cấu hình theo
[MYSQL_SETUP.md](MYSQL_SETUP.md). Học nền từ một CSV đo trong giai đoạn bình
thường của chính hệ thống trước khi chạy bộ thu liên tục.

Đặt `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, tùy chọn `MYSQL_PORT`,
`MYSQL_DATABASE`, `MYSQL_SSL_CA` trong môi trường riêng của tiến trình thu.
Mật khẩu không đưa vào câu lệnh hoặc gửi tới Backend. Ví dụ nhận mật khẩu qua
lời nhắc trong PowerShell:

```powershell
$env:MYSQL_HOST = "db.example.internal"
$env:MYSQL_USER = "anomaly_monitor"
$env:MYSQL_SSL_CA = "C:\certs\ca.pem"
$credential = Get-Credential -UserName $env:MYSQL_USER -Message "Tài khoản giám sát CSDL"
$env:MYSQL_PASSWORD = $credential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe scripts/run_collector.py --backend-url http://127.0.0.1:8000 --interval 1
```

`--samples 120` giới hạn số mẫu gửi; bỏ tham số để chạy đến khi Ctrl+C.
TLS xác minh CA/tên máy chủ là mặc định. `--no-tls` chỉ dành cho máy chủ demo
cục bộ đã được kiểm soát. Thư viện yêu cầu PyMySQL >= 1.2.3.

Bộ thu dùng các câu lệnh cố định `SHOW GLOBAL STATUS`, `SELECT 1` và thiết lập
phiên chỉ đọc. QPS là ΔQuestions/thời gian thực; kết nối là Threads_connected;
truy vấn chậm là ΔSlow_queries; lỗi kết nối là ΔAborted_connects. Độ trễ là thời
gian khứ hồi của phép thăm dò, không phải trung bình thời gian mọi truy vấn.
Khi Uptime/bộ đếm giảm, chu kỳ đó bị bỏ qua và mốc đo được đặt lại; không tạo
mẫu 0 giả. Mất kết nối sẽ thử lại. Event ID giúp lần gửi lại không nhân đôi lịch sử.

Health Bar dựa vào thời điểm **nhận số đo mới**, không dựa vào timestamp lịch
sử của CSV. Quá ngưỡng không có mẫu thì báo mất tín hiệu. Một lần gửi lại mẫu
cũ không kéo dài trạng thái khỏe. Nguồn đã dừng/phát hết dữ liệu được ghi rõ.
Sau khi Backend khởi động lại, lịch sử/mô hình còn nguyên nhưng nguồn cần được
khởi chạy lại; trạng thái nguồn cũ không được coi là đang hoạt động.

Các nút **Bơm sự cố mô phỏng** tác động luồng phát lại. Chế độ **Tạo tải trên
máy chủ thử nghiệm** bên dưới dùng kết nối riêng; bộ thu trực tiếp tiếp tục
chỉ đọc. Âm thanh và thông báo ra ngoài chưa được bật.

## Diễn tập bằng tải thật trên MySQL thử nghiệm

Từ thư mục dự án, chạy:

```powershell
.\CHAY_DEMO_TRUC_TIEP.bat
```

Công cụ hỏi địa chỉ/cổng, tài khoản giám sát và tài khoản tạo tải; mật khẩu
được nhập kín, không ghi vào mã nguồn, câu lệnh hay tệp cấu hình. Cần tạo sẵn
hai tài khoản trên máy chủ thử nghiệm. Tài khoản tạo tải chỉ cần đăng nhập,
`SELECT 1`, `SELECT SLEEP(0.2)` và đặt `long_query_time` cho chính phiên đó;
không cần quyền ghi bảng, tạo tài khoản hay đổi biến toàn cục.

Ví dụ DBA tạo hai tài khoản mới cho MySQL **cục bộ thử nghiệm** trong phiên
SQL quản trị (thay hai mật khẩu mẫu bằng mật khẩu riêng):

```sql
CREATE USER 'anomaly_monitor'@'localhost' IDENTIFIED BY 'THAY_MAT_KHAU_BO_THU';
CREATE USER 'anomaly_demo'@'localhost' IDENTIFIED BY 'THAY_MAT_KHAU_TAO_TAI';
GRANT USAGE ON *.* TO 'anomaly_monitor'@'localhost';
GRANT USAGE ON *.* TO 'anomaly_demo'@'localhost';
```

Nếu tài khoản đã tồn tại, giữ cấu hình của DBA thay vì chạy lại `CREATE USER`.
Với máy chủ ở xa, giới hạn host tài khoản theo máy thu/tạo tải và áp dụng TLS
như [hướng dẫn thiết lập](MYSQL_SETUP.md). Các chỉ số là toàn máy chủ, thường
không cần truyền `--database`.

TLS xác minh chứng chỉ được dùng mặc định. Với MySQL trên máy cá nhân không
cấu hình TLS, chỉ rõ:

```powershell
.\CHAY_DEMO_TRUC_TIEP.bat --no-tls
```

Tùy chọn này chỉ chấp nhận địa chỉ loopback. Với CA nội bộ, dùng
`--ssl-ca "C:\certs\ca.pem"`. Chạy `--help` để xem các tham số; `--check`
chỉ kiểm tra thư viện, không kết nối CSDL hay tạo tải.

Công cụ thu **60 mẫu bình thường thật** làm nền trước khi khởi động bộ thu
liên tục và giao diện. Giữ hệ thống thử nghiệm ở trạng thái bình thường trong
giai đoạn này; có thể chọn `--baseline-samples 120` để lấy nhiều mẫu hơn.
Mức nền và số đo được lưu riêng trong `.runtime/live_monitoring.sqlite3`.
Công cụ in địa chỉ web và API thực tế, tự chọn cổng còn trống, không dùng lại
Backend đã chạy với cấu hình khác. Giữ cửa sổ mở; Ctrl+C dừng các tiến trình
do công cụ này tạo.

Trong **Điều khiển demo → Bộ thu trực tiếp**, kiểm tra máy chủ đích rồi chọn
một nút tạo tải. Backend chỉ nhận lệnh khi bộ thu đang gửi mẫu mới và có
cùng mã định danh host/cổng với cấu hình tạo tải. Hai phía cần dùng cùng tên
host; không tự suy đoán rằng một bí danh DNS và một địa chỉ IP là cùng máy.
Mỗi lần chỉ chạy một tác vụ, có nút **Dừng tạo tải**, tự đóng kết nối khi hết
thời lượng, khi lỗi hoặc khi đổi nguồn/học lại nền.

| Kịch bản thật | Tác vụ | Giới hạn |
|---|---|---|
| K2 | Phát `SELECT 1` theo tốc độ mục tiêu | 1–500 truy vấn/giây, 1–60 giây |
| K3 | Mở và giữ kết nối; tùy chọn thử tên tài khoản ngẫu nhiên không tồn tại | 1–20 kết nối, 0–3 lần xác thực lỗi, 1–60 giây |
| K4 | Lặp `SELECT SLEEP(0.2)` với `SET SESSION long_query_time=0.05` | 1–60 giây; chỉ sửa cấu hình phiên tạo tải |

Mặc định là 15 giây; K2 nhắm 100 truy vấn/giây, K3 giữ 10 kết nối và không
tạo lỗi đăng nhập cho đến khi người dùng chọn số lần. Tốc độ là mục tiêu,
không phải cam kết số đo; mạng và máy chủ có thể giới hạn tốc độ thực tế.
Hết cửa sổ thời lượng sẽ không phát thêm thao tác; một thao tác đang chờ I/O
có thể cần kết thúc hoặc hết timeout 2 giây trước khi hoàn tất dọn kết nối.
K4 nhằm tăng bộ đếm `Slow_queries`. Chạy `SLEEP` trong phiên riêng **không
bảo đảm** phép thăm dò `SELECT 1` của bộ thu có độ trễ cao; ứng dụng hiển thị
số đo thật, không sửa giá trị để ép cảnh báo.

Nhật ký tác vụ lưu thời điểm, kịch bản, máy chủ đích, tham số, số truy vấn và
trạng thái hoàn tất/dừng/lỗi trong SQLite; không lưu mật khẩu. Nếu dịch vụ
khởi động lại, tác vụ đang chạy được đánh dấu bị ngắt, không tự phát lại tải.
Dữ liệu đo trong tác vụ không tự được gắn nhãn `-1`: thời gian tạo tải không
thay thế nhãn sự cố được kiểm chứng, nên không tự sinh điểm Precision/Recall/F1.

Nếu khởi động từng thành phần, đặt các biến này trong **terminal Backend**:

```powershell
$env:ANOMALY_FAULT_ENABLED = "1"
$env:FAULT_MYSQL_HOST = "127.0.0.1"
$env:FAULT_MYSQL_PORT = "3306"
$env:FAULT_MYSQL_USER = "anomaly_demo"
$credential = Get-Credential -UserName $env:FAULT_MYSQL_USER -Message "Tài khoản tạo tải thử nghiệm"
$env:FAULT_MYSQL_PASSWORD = $credential.GetNetworkCredential().Password
# Chỉ với MySQL loopback không TLS:
$env:FAULT_MYSQL_NO_TLS = "1"
# Với máy chủ có TLS, bỏ NO_TLS và dùng FAULT_MYSQL_SSL_CA nếu cần CA riêng.
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8002
```

Sau đó khởi chạy bộ thu với `MYSQL_HOST`/`MYSQL_PORT` trùng máy chủ đích,
tài khoản `MYSQL_USER`/`MYSQL_PASSWORD` riêng và `--backend-url` đúng cổng.
Các biến `FAULT_MYSQL_*` chỉ được đọc ở Backend; không nhận mật khẩu hoặc
SQL tự do từ yêu cầu HTTP. Không dùng trình chạy thường để mong cập nhật
biến môi trường cho một Backend đang chạy; cần khởi động Backend với cấu
hình mới hoặc dùng trình chạy trực tiếp ở trên.

Cách đo và giới hạn được đối chiếu với tài liệu gốc:
[Server Status Variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html),
[long_query_time](https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html#sysvar_long_query_time)
và [SLEEP](https://dev.mysql.com/doc/refman/8.4/en/miscellaneous-functions.html#function_sleep).

## Hợp đồng API

Các đường dẫn mới nằm dưới `/monitor`; `/detect` và `/compare` cũ vẫn được giữ.

| Phương thức/đường dẫn | Vai trò |
|---|---|
| `GET /health` | Tình trạng Backend, mức nền, nguồn và mẫu mới nhất |
| `GET /scenarios` | Mô tả K1–K4 |
| `GET /catalog` | Toàn bộ phiên mức nền và nguồn đã lưu, kể cả ngoài cửa sổ biểu đồ |
| `POST /train` | Học khoảng nền riêng; lưu phiên mô hình mới |
| `POST /samples` | Nhận số đo, chấm bằng bốn mô hình, lưu lịch sử |
| `GET /history` và `GET /alerts` | Lịch sử và các phiếu cảnh báo, lọc theo nguồn/phiên nền |
| `POST /alerts/{id}/feedback` | Lưu phản hồi DBA và nhật ký thay đổi |
| `GET /evaluation` | Chỉ số đánh giá từ nhãn tham chiếu, tách thô/sau lọc |
| `GET /evidence` | Snapshot đầy đủ mẫu, phiên nền và đánh giá để tái lập chứng cứ |
| `POST /replay/start`, `POST /replay/stop` | Điều khiển tiến trình phát lại |
| `POST /inject` | Xếp sự cố mô phỏng K2/K3/K4 vào các mẫu tiếp theo |
| `POST /demo/alert` | Demo nhanh K3 bằng nền K1, không thay nền riêng hoặc nguồn trực tiếp |
| `GET /faults/live` | Cấu hình công khai, giới hạn và trạng thái tác vụ tạo tải thật gần nhất |
| `POST /faults/live` | Bắt đầu K2/K3/K4 thật khi bộ thu mới và đúng máy chủ đích |
| `POST /faults/live/stop` | Dừng tác vụ tạo tải thật và đóng kết nối của tác vụ |
| `POST /source/live`, `POST /source/stop` | Chọn/dừng nguồn trực tiếp, có kiểm tra phiên bộ thu |

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Các kiểm tra mới bao phủ tách nền/kiểm tra, giữ scaler cố định, kết quả khớp
pipeline cũ, đồng thuận, lưu/đọc lại SQLite, phản hồi độc lập nhãn chuẩn,
chuyển nguồn, mất tín hiệu, reset bộ đếm, gửi lại idempotent và HTTP/giao diện.
Kết nối CSDL thật vẫn cần diễn tập trên máy chủ của người dùng với tài khoản
và TLS hợp lệ; bộ test không dùng thông tin đăng nhập sản xuất.
