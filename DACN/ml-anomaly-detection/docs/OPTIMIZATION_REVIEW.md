# Rà soát và tối ưu ngày 14/11/2026

## Phạm vi và hiện trạng trước khi sửa

Đã khảo sát backend, toàn bộ frontend, pipeline và mô hình, thu thập MySQL,
scripts dữ liệu/đánh giá, notebook, tài liệu và các kiểm thử. Công nghệ hiện tại:
Python, Streamlit, FastAPI, pandas, scikit-learn và Plotly. Không có database
nghiệp vụ, màn hình đăng nhập, phân quyền hay CRUD trong source hiện tại.
MySQL chỉ là nguồn đo bằng các truy vấn cố định, không ghi dữ liệu nghiệp vụ.

Giữ bốn thuật toán, học theo thời gian, chuẩn hóa trên train, lọc vận hành tách
khỏi dự đoán gốc, so sánh dùng chung nền và notebook NAB với phạm vi chấm riêng.
Các chỉnh sửa chưa commit có sẵn được giữ lại, không reset hoặc thay thế.

Baseline thực chạy: 179 tests / 76,191 giây, 2 failures và 10 errors.
Log: `reports/optimization_baseline.txt`. Một số nhóm không chạy được do thiếu
fixture trong setUpClass, nên số test chạy lại sau sửa sẽ lớn hơn.

## Vấn đề và phương án

| Ưu tiên | Vấn đề có bằng chứng | Phương án nhỏ nhất |
|---|---|---|
| Cao | Tests/scripts đang tham chiếu ba CSV kịch bản chưa tồn tại; FE vẫn chọn bộ gộp cũ. | Tạo ba fixture từ generator hiện có, kiểm tra hash nền, đồng bộ lựa chọn FE và giữ bộ cũ. |
| Trung bình | `build_demo_frames` ghi là tương thích nhưng mất kịch bản `combined_pressure` của luồng cũ. | Giữ generator bốn bộ mới; khôi phục hành vi hàm tương thích trong bộ nhớ. |
| Trung bình | CSV một chỉ số nhận timestamp số thành nanosecond năm 1970, nhận bool/complex thành số đo. | Từ chối kiểu mơ hồ trước chuyển đổi, giữ chính sách làm sạch số thiếu hiện có. |
| Trung bình | Thống kê mùa vụ có thể ghi đè chỉ số mang tên `hour`, `day_of_week`, `month`. | Tách khóa nhóm theo lịch khỏi giá trị đo, kiểm tra cả tên thời gian trùng tên lịch. |
| Trung bình | 1440 × 0,7 bị cắt thành 1007 dòng trong luồng một chỉ số. | Dùng Decimal từ chuỗi tỷ lệ ở cả pipeline và phần xem trước FE, giống DBMS. |
| Trung bình | Client nhận JSON `true` như nhãn/dự đoán/điểm số 1. | Kiểm tra bool trước chuyển kiểu và hiển thị lỗi phản hồi không hợp lệ. |
| Trung bình | Fit đã chạy threadpool nhưng tạo summary/context vẫn chạy trên event loop. | Chạy phân tích và chuẩn bị payload trong cùng một worker, giữ contract JSON. |
| Trung bình | Sinh giải thích DBMS duyệt từng dòng bằng iterrows, kể cả khi không lệch nền. | Chỉ định dạng bằng chứng cho hàng thực sự lệch; đối chiếu hash đầu ra trước/sau. |
| Thấp | Luồng `/detect` chưa kiểm tra bytes/rỗng/10 MiB phía client như `/compare`; kiểm tra URL lặp. | Dùng helper kiểm tra chung trước HTTP, kiểm tra cả cổng URL. |
| Thấp | Biểu đồ so sánh gọi CSV bên trái là bình thường khi chưa xác minh; lọc không có dòng hiện bảng rỗng. | Đặt tên tham chiếu trung tính, thêm hướng dẫn chọn lại bộ lọc. |
| Thấp | Báo cáo suy nguồn tổng hợp từ tên tệp; hai CSV chỉ có một bên có nhãn bị bỏ đánh giá mà chưa giải thích. | Lưu ngữ cảnh nguồn từ thao tác nhập; giải thích rõ điều kiện chấm điểm trên cả hai màn hình. |
| Thấp | Một test yêu cầu nút chạy bị khóa dù đã chuyển sang mẫu NAB hợp lệ. | Kiểm tra đúng bất biến: ẩn kết quả cũ, không tự gửi API; mẫu hợp lệ vẫn được chạy. |

## Giới hạn được giữ rõ

Không bổ sung đăng nhập/phân quyền chỉ để có tính năng mới. API hiện phù hợp demo
cục bộ; triển khai công khai cần thiết kế xác thực và giới hạn tài nguyên riêng.
Không thay database, URL endpoint, quy ước nhãn hoặc thêm dependencies.
Không dùng kết quả tổng hợp để khẳng định chất lượng trên máy chủ thực.

## Những thay đổi đã triển khai

1. **Dữ liệu và tương thích demo:** tạo ba CSV kịch bản còn thiếu từ generator
   sẵn có, thêm manifest riêng trong `docs/`; đồng bộ mặc định Cơ bản/so sánh sang
   kịch bản tăng QPS. Nâng cao chọn được từng sự cố và vẫn mở được mẫu phối hợp
   cũ. Khôi phục chính xác bốn tình huống của hàm tương thích `build_demo_frames`.
2. **Tính đúng của dữ liệu:** kiểm tra timestamp số, bool/complex ở chỉ số/nhãn,
   kiểu cấu hình, thuật toán không hợp lệ; chia tập bằng Decimal thống nhất FE/BE;
   bảo toàn chỉ số trùng tên lịch khi tổng hợp mùa vụ.
3. **Độ ổn định API:** kiểm tra CSV/URL chung trước gửi; từ chối JSON bool giả
   dạng dữ liệu số; chạy cả fit và chuẩn bị payload trong một worker. Đường dẫn,
   trường JSON, độ chính xác timestamp và score được giữ nguyên.
4. **UX và tốc độ:** nguồn tải lên không bị gắn là dữ liệu tổng hợp chỉ do tên tệp;
   thông báo rõ khi chỉ một CSV có nhãn; so sánh dùng tên tham chiếu trung tính;
   lọc rỗng hướng dẫn chọn Tất cả. Sinh giải thích DBMS chỉ định dạng hàng lệch nền.

## Tệp đã sửa hoặc bổ sung trong đợt này

| Tệp | Mục đích |
|---|---|
| `backend/api.py` | Dùng chung cách tạo payload và đưa công việc đó vào worker. |
| `frontend/api_client.py` | Kiểm tra phản hồi, CSV và URL trước khi trình bày/gửi. |
| `frontend/app.py` | Hiển thị cách chia tập đúng với backend. |
| `frontend/demo_data.py` (mới) | Tập trung tên các mẫu, tránh lệch giữa hai giao diện. |
| `frontend/dbms_dashboard.py` | Chọn kịch bản riêng/cũ; ghi đúng nguồn dữ liệu. |
| `frontend/monitoring_workspace.py` | Đồng bộ mẫu, thông báo nhãn và bộ lọc rỗng, bỏ import dư. |
| `frontend/monitoring_charts.py` | Đặt tên tham chiếu không khẳng định trước kết quả. |
| `src/data_prep.py` | Kiểm tra kiểu dữ liệu, giữ đúng thống kê mùa vụ. |
| `src/pipeline.py`, `src/models.py` | Validation nhất quán, chia tập chính xác. |
| `src/dbms_monitoring.py` | Giảm chi phí sinh bằng chứng mà giữ nguyên đầu ra. |
| `scripts/generate_mysql_demo.py` | Giữ hàm tương thích cũ bên cạnh generator mới đã có. |
| `scripts/benchmark_indicators.py` (mới) | Benchmark tái lập với hash đầu ra. |
| `tests/test_frontend.py` | Sửa một kỳ vọng cũ: mẫu hợp lệ được chạy nhưng không tự gửi API. Giữ các thay đổi trước đó. |
| `tests/test_api_resilience.py` (mới) | 7 kiểm thử về contract, preflight và event loop. |
| `tests/test_validation_regressions.py` (mới) | 10 kiểm thử về dữ liệu, cấu hình, split và mùa vụ. |
| `tests/test_ux_regressions.py` (mới) | 4 kiểm thử về kịch bản, nguồn, nhãn và lọc rỗng. |
| `data/mysql_query_spike.csv`, `mysql_connection_spike.csv`, `mysql_latency_spike.csv` (mới) | Fixture có thể tái tạo; không ghi đè CSV cũ. |
| `docs/mysql_datasets_manifest.json` (mới) | Seed, hash, phạm vi sự kiện, đơn vị và giới hạn. |
| `README.md`, `docs/INTERFACE_GUIDE.md`, `docs/DEMO_MYSQL.md` | Đồng bộ hướng dẫn theo mẫu và lựa chọn thực tế. |
| `docs/OPTIMIZATION_REVIEW.md` (mới), `reports/optimization_*`, `reports/benchmark_api_serialization.py`, `reports/api_serialization_benchmark.json` | Báo cáo và bằng chứng kiểm tra. |

Những tệp khác đã có thay đổi trước lượt làm việc, bao gồm `frontend/reporting.py`,
`scripts/evaluate_mysql_demo.py`, nhiều tests và các tài liệu ngoài project con,
không được tính là thay đổi mới của đợt này. Không reset, commit hoặc xóa dữ liệu.

## Kết quả kiểm thử thực tế

Môi trường: Windows, Python 3.10.9 tại `C:\Users\User\DACN\.venv`, Streamlit
1.65.0, pandas 2.3.3, NumPy 2.2.6, scikit-learn 1.7.2, FastAPI 0.162.0,
httpx 0.28.1, Plotly 7.1.0, PyMySQL 1.2.3. Không cài thêm dependencies.

Lệnh chạy từ thư mục project con:

```powershell
& C:\Users\User\DACN\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- **207 tests đạt / 97,976 giây**, không lỗi hoặc thất bại. Log đầy đủ:
  [optimization_after.txt](../reports/optimization_after.txt). Có 21 regression
  mới; các test trước bị chặn bởi `setUpClass` thiếu CSV nay cũng được chạy.
  Không dùng thời gian tổng suite trước/sau để kết luận nhanh hơn, vì số ca khác nhau.
- Phạm vi: pipeline bốn thuật toán, API `/detect` và `/compare`, HTTP FE–BE,
  Cơ bản/Nâng cao, upload, ánh xạ cột, giữ/ẩn kết quả khi đổi cấu hình, CSV/JSON,
  so sánh dùng chung nền, notebook NAB, dữ liệu rỗng/sai nhãn/sai kiểu/quá lớn,
  mất kết nối/timeout/lỗi API và thu MySQL bằng adapter giả lập.
- Kiểm thử đồng thời xác nhận `/health` vẫn trả lời khi worker đang chuẩn bị kết quả.
- HTTP qua hai tiến trình thật: Uvicorn cổng 8765 và Streamlit cổng 8766 đều trả
  health 200. Bốn mẫu mới gọi `/detect` thành công, mỗi mẫu 1.008 dòng train/432
  dòng test. CSV có timestamp số trả 422. Hai tiến trình kiểm thử đã được dừng.
- Số cảnh báo sau lọc trên lần HTTP thực (thứ tự MAD/IF/LOF/SVM): bình thường
  **0/0/0/0**, QPS **44/0/44/44**, kết nối **44/2/44/44**, độ trễ **43/24/43/43**.
  Đây là kết quả tính thực trên dữ liệu tổng hợp; không phải bằng chứng chất lượng
  trên MySQL thực. Không thay kết quả Isolation Forest để ép bốn mô hình khớp nhau.
- Kiểm tra toàn vẹn: bốn bộ mới khớp generator và hash manifest; CSV phối hợp cũ
  khớp từng byte với hàm tương thích được khôi phục. Kết quả tại
  [optimization_data_integrity.json](../reports/optimization_data_integrity.json).
- `git diff --check` đạt. Bytecode đã bị theo dõi trong Git được khôi phục về
  trạng thái trước chạy tests, tránh đưa thay đổi tự sinh vào bản sửa.

## Hiệu năng đo được

Sinh bằng chứng DBMS trên 20.000 dòng, 5% lệch nền, trung vị 5 lần trên cùng máy:

| Phạm vi | Trước | Sau | Kiểm chứng |
|---|---:|---:|---|
| `_add_indicators` | 0,549011 giây | 0,018120 giây | Nhanh khoảng 30 lần; hash toàn bộ bảng đầu ra giống nhau. |

Chạy lại bằng `python scripts/benchmark_indicators.py`. Bằng chứng:
[trước](../reports/optimization_performance_before.json),
[sau](../reports/optimization_performance_after.json). Số đo chỉ áp dụng bước sinh
bằng chứng; không tính fit, HTTP hoặc trình duyệt. Mức cải thiện phụ thuộc tỷ lệ
hàng lệch nền.

Benchmark phụ trên 100.000 dòng, 30.000 dự đoán, trung vị 3 lần: chuyển chuẩn bị
payload sang worker giảm độ trễ event loop lớn nhất từ **386,31 xuống 140,05 ms**;
thời gian chuẩn bị tăng **388,09 lên 472,57 ms**. Mục tiêu là khả năng đáp ứng
đồng thời, chưa khẳng định tổng request nhanh hơn. Xem
[số đo](../reports/api_serialization_benchmark.json) và
[script tái lập](../reports/benchmark_api_serialization.py).

## Hạn chế chưa giải quyết và bước tiếp theo

1. **Chưa kiểm tra bằng mắt trên desktop/tablet/mobile.** Browser Use báo lỗi
   `service_info`; Windows Computer Use dừng vì không xác định đủ chắc chắn URL
   để thực thi chính sách. Đã dừng thao tác UI, không thử vượt chặn. AppTest kiểm
   tra luồng/giá trị/widget, không chứng minh bố cục hay độ tương phản hoàn hảo.
2. **Chưa có kết nối MySQL thật hoặc chứng chỉ/tài khoản được cung cấp.** Kiểm thử
   collector dùng adapter giả lập; chưa xác minh quyền và TLS trên máy chủ thực.
   Không có đăng nhập, phân quyền, CRUD ứng dụng để kiểm thử trong source này.
3. **Biểu đồ Nâng cao:** expander đóng vẫn dựng các biểu đồ; CSV Nâng cao được
   parse lại mỗi rerun. Bước tiếp theo nên lazy render/cache theo dữ liệu, sau khi
   đo thời gian trang thực và kiểm tra bố cục trên điện thoại.
4. **CPU và tải đồng thời:** JSON cuối response và Python GIL vẫn có thể làm chậm
   event loop; LOF/SVM tốn tài nguyên trên tệp lớn. Trước triển khai công khai cần
   đo tải, giới hạn đồng thời/tài nguyên và thiết kế xác thực phù hợp.
5. **Luồng CLI phụ:** NAB CLI làm sạch hai lần có thể làm mất số đếm dòng đã loại;
   tải NAB trực tiếp chưa có timeout và ghi tệp tạm rồi thay thế. Ưu tiên xử lý khi
   dùng hai luồng này thường xuyên, kèm kiểm thử lỗi tải và bảo toàn tệp cũ.
6. **Môi trường tái lập:** dependencies còn dùng nhiều khoảng phiên bản rộng;
   nên lưu lock/constraints sau khi chọn môi trường nộp đồ án. Chưa nâng cấp hoặc
   thay đổi thư viện trong đợt này.
