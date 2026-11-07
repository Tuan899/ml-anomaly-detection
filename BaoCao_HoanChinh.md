# BÁO CÁO ĐỒ ÁN

## NGHIÊN CỨU THUẬT TOÁN PHÁT HIỆN BẤT THƯỜNG TRONG HỆ QUẢN TRỊ CƠ SỞ DỮ LIỆU

**Bản hiệu chỉnh theo mã nguồn và dữ liệu hiện có**  
**Ngày rà soát:** 01/11/2026

> **Phạm vi và giới hạn:** Báo cáo giữ tên đề tài theo yêu cầu. Tuy nhiên, mã nguồn và dữ liệu hiện tại chưa chứng minh việc kết nối hay giám sát trực tiếp một hệ quản trị cơ sở dữ liệu (DBMS). Phần thực nghiệm trong workspace là xử lý CSV metric CPU. Báo cáo không coi dữ liệu giả lập hoặc CSV 19 dòng là bằng chứng về hiệu năng trên DBMS.

## Tóm tắt

Đồ án khảo sát các phương pháp phát hiện bất thường trên chuỗi thời gian, gồm robust Z-score dựa trên độ lệch tuyệt đối trung vị (MAD), Isolation Forest, Local Outlier Factor (LOF) và One-Class Support Vector Machine (One-Class SVM). Phần mềm có các chức năng đọc CSV, xử lý timestamp và giá trị số, tạo đặc trưng lịch, trực quan hóa chuỗi, cung cấp API FastAPI và giao diện Streamlit.

Rà soát mã nguồn không tìm thấy kết nối MySQL, thư viện điều khiển MySQL, câu lệnh SQL, tệp cấu hình DBMS hoặc dữ liệu truy vấn từ cơ sở dữ liệu. Sáu tệp CSV CPU cục bộ có nội dung giống hệt nhau; mỗi tệp có 19 dòng trong khoảng 90 phút, với hai cột timestamp và value. Hai timestamp bất thường được gắn trong mã NAB nằm ngoài khoảng dữ liệu. Pipeline phân tích NAB mặc định yêu cầu 3.550 dòng và lỗi với tệp hiện có; notebook đặt điểm chia 3.000 nên tập kiểm tra rỗng. Vì vậy chưa có Precision, Recall hoặc F1 hợp lệ để so sánh thuật toán.

Kết luận theo bằng chứng hiện có: dự án có các thành phần phần mềm, nhưng chưa hoàn thành thực nghiệm có nhãn đáng tin cậy và chưa triển khai giám sát DBMS. Muốn bảo vệ đề tài theo tên hiện tại cần bổ sung metric DBMS thực tế cùng quy trình thu thập có thể tái hiện. Nếu giữ phạm vi CSV CPU, nên điều chỉnh tên đề tài cho đúng dữ liệu.

**Từ khóa:** phát hiện bất thường, chuỗi thời gian, MAD, Isolation Forest, LOF, One-Class SVM, DBMS.

# Phần I. Kết quả rà soát dự án

## 1. Hiện vật đã kiểm tra

- Báo cáo hiện tại: **baocao.md**; hướng dẫn chạy: **huongdan.md**.
- Mã nguồn: **DACN/anomaly_detection.py** và các module trong **DACN/ml-anomaly-detection/src/**.
- API và giao diện: **backend/api.py**, **frontend/app.py**.
- Dữ liệu: **data/cpu_0.csv** đến **data/cpu_5.csv**; notebook: **notebooks/exploratory.ipynb**.
- Cấu hình thư viện: **requirements.txt**; tài nguyên minh họa: **report_assets/**.
- Không thấy file SQL, cấu hình MySQL, log chạy, bảng kết quả thực nghiệm riêng hoặc file Word trong dự án đã kiểm tra. requirements.txt không khai báo thư viện MySQL.

## 2. Kết luận về MySQL và phạm vi đề tài

| Nội dung | Kết quả |
|---|---|
| Kết nối MySQL | Không tìm thấy trong mã nguồn/cấu hình. |
| Vai trò MySQL | Không có bằng chứng MySQL được dùng để lưu trữ, thu thập metric, tạo dữ liệu hay chạy thí nghiệm. |
| Đầu vào mô hình | CSV từ đường dẫn hoặc file tải lên; script cũ tự sinh dữ liệu ngẫu nhiên. |
| Ý nghĩa dữ liệu CPU | Được mô tả là metric CPU EC2/NAB, không phải metric truy vấn hay trạng thái bên trong DBMS. Không có bằng chứng máy được đo đang chạy CSDL. |
| Phân loại | Trường hợp C: dự án không sử dụng MySQL và không cần MySQL cho thí nghiệm CSV hiện tại. |

Hàm **database_metric_columns()** chỉ lọc các cột số và loại một số tên cột nhãn; tên hàm không chứng minh có kết nối cơ sở dữ liệu. Không nên viết rằng hệ thống đã giám sát trực tiếp MySQL hoặc hiệu năng DBMS.

Tên đề tài hiện tại chỉ được dữ liệu hỗ trợ nếu nghiên cứu được mở rộng bằng metric DBMS thật. Với hiện trạng, tên trung thực hơn là **“Nghiên cứu một số thuật toán phát hiện bất thường trên chuỗi thời gian sử dụng CPU”**. Bản này giữ tên đề tài người dùng nêu, đồng thời ghi rõ khoảng cách giữa tên gọi và sản phẩm hiện có.

Nếu phát triển giám sát MySQL, nên thu thập theo timestamp: số kết nối hiện tại/tối đa, số truy vấn và lỗi, thời gian thực thi theo digest truy vấn, số hàng đọc/trả về, thời gian chờ khóa, chỉ số InnoDB buffer pool và I/O, cùng CPU, bộ nhớ, đĩa và mạng của máy chủ. MySQL cung cấp status variables và các bảng tổng hợp statement/wait trong Performance Schema. Bộ đếm tích lũy cần được chuyển thành mức tăng theo từng khoảng lấy mẫu và cần ghi nhận khi máy chủ khởi động lại hoặc reset bộ đếm. Đây là hướng phát triển, chưa phải chức năng của dự án. Nguồn: [MySQL Server Status Variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html), [Performance Schema Statement Summary Tables](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html).

## 3. Kiểm tra dữ liệu CSV

| Thuộc tính | Kết quả xác minh |
|---|---|
| Tên file | cpu_0.csv đến cpu_5.csv |
| Số dòng mỗi file | 19 |
| Cột | timestamp, value |
| Khoảng thời gian | 14/02/2014 14:30 đến 16:00 |
| Chu kỳ | 5 phút |
| Dòng thiếu hoặc timestamp trùng | Không thấy trong các file đã kiểm tra |
| Giá trị nhỏ nhất/lớn nhất | 0.066 / 0.202 |
| Trung bình/trung vị | 0.126526 / 0.134 |
| Đơn vị của value | CSV không khai báo; không tự diễn giải là phần trăm |
| Quan hệ giữa sáu file | Cùng SHA-256, nội dung giống hệt nhau; không phải sáu chuỗi độc lập |
| Nhãn NAB trong mã | 2014-02-26 22:05 và 2014-02-27 17:15; đều ngoài khoảng dữ liệu cục bộ |

Không tìm thấy **ec2_cpu_utilization.csv** mà baocao.md liên kết. data_prep.py có hàm tải dữ liệu NAB, nhưng không có bằng chứng hàm tải đã được gọi để tạo các file hiện tại. Vì vậy, quy mô dữ liệu đang có là 19 dòng mỗi file; nguồn gốc và phiên bản đầy đủ cần được xác nhận lại. NAB mô tả nhóm realAWSCloudwatch là metric máy chủ AWS; hai timestamp trong mã có trong [combined_labels.json](https://github.com/numenta/NAB/blob/master/labels/combined_labels.json). Các nguồn này không biến metric CPU EC2 thành metric DBMS. [NAB data README](https://github.com/numenta/NAB/blob/master/data/README.md).

## 4. Thuật toán và cách triển khai quan sát được

| Phương pháp | Triển khai và đầu vào | Cấu hình và giới hạn |
|---|---|---|
| Robust Z-score/MAD | **compute_robust_z_scores()** tính median, MAD, robust score; bất thường nếu trị tuyệt đối score ≥ 3.5. | Đây là baseline thống kê. run_nab_analysis tính MAD trên toàn chuỗi trước khi đánh giá, có rò rỉ nếu xem là kết quả held-out. Script cũ dùng ngưỡng một phía. API tính MAD trên riêng test thay vì fit từ train. |
| Isolation Forest | Có trong **fit_models()**; run_nab_analysis dùng value, còn API/giao diện thêm đặc trưng lịch. | contamination nhận từ caller, random_state=42; tham số khác dùng mặc định scikit-learn. Mặc định run_nab_analysis là 1/split_index, chưa có căn cứ hiệu chỉnh. |
| LOF | Có trong **fit_models()**, novelty=True cho phép dự đoán mẫu mới. | Số láng giềng = min(20, số mẫu train − 1), tối thiểu 2. Với 13 dòng train hiện tại, số láng giềng là 12. |
| One-Class SVM | Có trong **fit_models()**. | nu=contamination, kernel=rbf, gamma=scale; chưa có bước chuẩn hóa đặc trưng riêng. |
| Đặc trưng lịch | **build_feature_matrix()** tạo value, hour_sin, hour_cos, dow_sin, dow_cos, is_weekend. | Notebook và run_nab_analysis chỉ dùng value; API/giao diện dùng thêm đặc trưng lịch. Các đường chạy chưa thống nhất đầu vào. |
| Cửa sổ trượt | Không thấy trong đường chạy mô hình. | Đặc trưng lịch không phải cửa sổ của các giá trị quá khứ; chưa có lag hoặc thống kê rolling. |
| Tuning | Có **tune_model()** cho Isolation Forest và LOF. | Không thấy được gọi trong notebook/API/giao diện; hàm fit và chấm trên cùng đầu vào, không phải quy trình validation độc lập. |

Theo scikit-learn, nhãn **1** là bình thường và **−1** là bất thường. Hàm đánh giá đặt lớp bất thường làm lớp dương khi tính Precision, Recall, F1. Tài liệu đã kiểm tra: [scikit-learn Outlier Detection](https://scikit-learn.org/stable/modules/outlier_detection); bài báo gốc [Isolation Forest](https://doi.org/10.1109/ICDM.2008.17), [LOF](https://doi.org/10.1145/335191.335388), [One-Class SVM](https://doi.org/10.1162/089976601750264965).

## 5. Khả năng chạy và độ tin cậy kết quả

Môi trường Python ảo có Python 3.10.9, pandas 2.3.3, NumPy 2.2.6, scikit-learn 1.7.2, SciPy 1.15.3 và Matplotlib 3.10.9. requirements.txt chỉ nêu phiên bản tối thiểu; không thấy lockfile.

| Phép chạy | Kết quả | Diễn giải |
|---|---|---|
| Script cũ **DACN/anomaly_detection.py** | Chạy hết với 4.032 điểm ngẫu nhiên. Spike được chèn tại chỉ số 1000 và 2500; nhãn timestamp nằm ở 3547 và 3777. MAD confusion matrix theo thứ tự [1, −1] là [[4026, 4], [2, 0]]. Isolation Forest và LOF trên test mỗi mô hình có [[1030, 0], [2, 0]]. | Đây là chẩn đoán cho thấy dữ liệu giả và nhãn không khớp; không phải kết quả NAB. |
| **run_nab_analysis(data/cpu_0.csv)** với mặc định | Dừng với ValueError vì split_index=3550 không nhỏ hơn 19 dòng. | Pipeline phân tích NAB chính không chạy được với CSV hiện tại. |
| Notebook **exploratory.ipynb** | Có 12 cell, không có output lưu sẵn; split=3000 tạo test rỗng với 19 dòng. | Chưa có bằng chứng notebook chạy hoàn chỉnh. |
| Gọi trực tiếp API handler **detect()** với cpu_0.csv | Trả 19 dòng, metrics rỗng; trên 6 dòng test gắn cờ IF 0, LOF 1, One-Class SVM 5 điểm. | Chỉ xác nhận handler xử lý CSV nhỏ; thiếu nhãn và test quá nhỏ để đánh giá. Chưa khởi chạy kiểm chứng HTTP server hoặc giao diện trình duyệt. |

Không dùng confusion matrix của script giả lập hoặc số điểm API trên làm kết quả so sánh mô hình. Không có F1 hợp lệ hoặc căn cứ kết luận thuật toán nào tốt hơn trên dữ liệu hiện tại.

# Phần II. Báo cáo nghiên cứu đã hiệu chỉnh

# Chương 1. Tổng quan về vấn đề

## 1.1. Lý do chọn đề tài

Các hệ thống máy tính tạo ra metric theo thời gian như CPU, bộ nhớ, độ trễ, số kết nối và lưu lượng mạng. Biến động bất thường có thể giúp người quản trị nhận biết sớm sự cố hoặc thay đổi tải. Trong DBMS, chuỗi thời gian về truy vấn, kết nối, khóa và I/O có thể hỗ trợ giám sát hoạt động. Tuy nhiên, để nghiên cứu đúng bài toán DBMS cần dữ liệu gắn với DBMS; CPU của máy chủ nói chung chưa đủ để quy kết anomaly cho cơ sở dữ liệu.

Đồ án khảo sát các phương pháp không giám sát và xây dựng công cụ phân tích CSV. Dữ liệu và triển khai hiện tại mới thể hiện chuỗi metric CPU, vì vậy kết luận trong báo cáo được giới hạn theo bằng chứng đó. NAB cung cấp các chuỗi thời gian thực tế từ nhiều miền, trong đó có metric máy chủ AWS, nhưng việc dùng metric này không đồng nghĩa đã đo hoạt động bên trong DBMS. [NAB repository](https://github.com/numenta/NAB), [NAB data README](https://github.com/numenta/NAB/blob/master/data/README.md).

## 1.2. Vấn đề và câu hỏi nghiên cứu

Bài toán là xác định quan sát hoặc đoạn thời gian có hành vi khác với phần lớn trạng thái thông thường. Các câu hỏi nghiên cứu:

1. Có thể xây dựng pipeline đọc chuỗi thời gian và chạy nhiều thuật toán phát hiện bất thường trên CSV không?
2. Khi có dữ liệu và nhãn đáng tin cậy, các phương pháp đạt Precision, Recall, F1 như thế nào trên đoạn test theo thời gian?
3. Tham số, thang đo đặc trưng và giả định của từng thuật toán ảnh hưởng thế nào đến cảnh báo?

Câu hỏi thứ nhất có các thành phần mã tương ứng. Câu hỏi thứ hai và thứ ba chưa thể trả lời do dữ liệu cục bộ không có anomaly nhãn trong khoảng quan sát và pipeline chính không chạy được.

## 1.3. Mục tiêu, phạm vi và giới hạn

Mục tiêu phần mềm là đọc CSV, chuẩn hóa dữ liệu, tạo đặc trưng thời gian, áp dụng các detector, trực quan hóa kết quả và cung cấp giao diện/API. Phạm vi dữ liệu đã kiểm tra là timestamp cùng một cột số. Chưa có kết nối MySQL, dataset metric DBMS, workload CSDL, truy vấn SQL hoặc nhãn anomaly trong khoảng dữ liệu.

Mục tiêu tích hợp thuật toán đạt mức có mã triển khai. Mục tiêu đánh giá hiệu năng bằng thực nghiệm đáng tin cậy chưa hoàn thành. Để giữ tên đề tài liên quan DBMS, cần bổ sung dữ liệu hoạt động DBMS thật; nếu chỉ dùng CSV CPU, nên đổi tên đề tài cho khớp phạm vi.

## 1.4. Kiến trúc phần mềm

Luồng thể hiện trong mã: CSV/file tải lên → load_timeseries → tạo đặc trưng và biểu đồ → Isolation Forest/LOF/One-Class SVM → điểm bất thường/score → FastAPI hoặc Streamlit. MAD nằm trong module phân tích và có thể tính metric khi có nhãn, nhưng không được tích hợp thành danh sách anomaly giống ba mô hình trong API/giao diện.

# Chương 2. Cơ sở lý thuyết

## 2.1. Chuỗi thời gian và dạng bất thường

Chuỗi thời gian có thể biểu diễn bằng các cặp (t, x_t), trong đó t là thời điểm và x_t là giá trị quan sát. Thứ tự thời gian có ý nghĩa; khi chia train/test cần giữ thứ tự để tránh đưa thông tin tương lai vào huấn luyện.

- **Bất thường điểm:** một quan sát riêng lẻ khác biệt rõ so với phần còn lại.
- **Bất thường theo ngữ cảnh:** giá trị chỉ bất thường khi xét ngữ cảnh như giờ, ngày hoặc tải hệ thống.
- **Bất thường tập thể:** một đoạn nhiều điểm tạo thành hành vi bất thường dù từng điểm riêng lẻ chưa chắc cực đoan.

Mã hiện tại dự đoán theo từng dòng. Đặc trưng giờ và thứ trong tuần cung cấp một phần ngữ cảnh lịch, nhưng chưa mô hình hóa bất thường theo đoạn.

## 2.2. Cửa sổ trượt

Với độ dài cửa sổ w, chuỗi có thể được chuyển thành vector tại thời điểm t:

**X_t = [x_(t−w+1), x_(t−w+2), …, x_t].**

Từ cửa sổ có thể tính trung bình, độ lệch chuẩn, min/max, độ dốc hoặc dùng trực tiếp các giá trị trễ. Cửa sổ chỉ nên chứa dữ liệu đã có tại thời điểm dự đoán. Pipeline hiện tại chưa tạo vector cửa sổ; đây là hướng mở rộng, không phải chức năng đã thực nghiệm.

## 2.3. Robust Z-score dựa trên MAD

**MAD(x) = median_i |x_i − median(x)|.**

**R_i = 0.6745 × (x_i − median(x)) / MAD(x).**

Mã đánh dấu bất thường nếu **|R_i| ≥ 3.5**. Đây là baseline thống kê; hệ số điều chỉnh MAD để xấp xỉ độ lệch chuẩn khi dữ liệu chuẩn. Ngưỡng 3.5 là quy tắc gắn cờ tiềm năng, không chứng minh mọi điểm bị gắn cờ là bất thường thật. Nếu MAD bằng 0, hàm hiện tại báo lỗi. Trong đánh giá held-out, median và MAD phải được ước lượng trên train rồi áp dụng cho test. [NIST/SEMATECH e-Handbook](https://www.itl.nist.gov/div898/handbook/toolaids/pff/eda.pdf).

## 2.4. Isolation Forest

Isolation Forest tạo các cây phân hoạch ngẫu nhiên. Điểm dễ bị cô lập thường có đường đi ngắn hơn và có thể được xem là bất thường. Trong mã, contamination nhận từ caller và random_state=42; tham số khác theo mặc định thư viện. contamination tác động ngưỡng dự đoán, không phải tỷ lệ bất thường đã xác nhận từ nhãn. Thuật toán được đề xuất bởi Liu, Ting và Zhou. [Bài báo](https://doi.org/10.1109/ICDM.2008.17).

## 2.5. Local Outlier Factor

LOF so sánh mật độ cục bộ của một điểm với các láng giềng. Điểm có mật độ thấp hơn đáng kể vùng xung quanh có thể là ngoại lệ. Mã dùng novelty=True để fit trên train và dự đoán điểm mới. Kết quả phụ thuộc số láng giềng và thang đo đặc trưng. [Bài báo](https://doi.org/10.1145/335191.335388).

## 2.6. One-Class SVM

One-Class SVM ước lượng biên bao quanh phần lớn dữ liệu huấn luyện; điểm ngoài biên có thể bị xem là bất thường. Mã sử dụng kernel RBF, gamma=scale và nu=contamination. nu điều khiển biên và số điểm huấn luyện có thể nằm ngoài; không đồng nhất trực tiếp nu với tỷ lệ anomaly thực tế. [Bài báo](https://doi.org/10.1162/089976601750264965).

## 2.7. Chỉ số đánh giá

Với nhãn tin cậy: Precision = TP/(TP+FP), Recall = TP/(TP+FN), F1 = 2×Precision×Recall/(Precision+Recall). Trong mã, lớp −1 là anomaly và được dùng làm lớp dương. Với dữ liệu mất cân bằng, accuracy có thể cao dù mô hình bỏ sót phần lớn anomaly; không dùng accuracy đơn độc.

Nếu không có nhãn đáng tin cậy, không thể tính Precision/Recall/F1 để khẳng định chất lượng. Khi so sánh theo NAB cần dùng nhãn cửa sổ và cơ chế scoring phù hợp, không tự tạo nhãn. [NAB paper](https://arxiv.org/abs/1510.03336), [NAB repository và scoring](https://github.com/numenta/NAB).

# Chương 3. Dữ liệu và phương pháp thực nghiệm

## 3.1. Mô tả dữ liệu cục bộ

| Trường | Kiểu/ý nghĩa hiện biết |
|---|---|
| timestamp | Chuỗi thời gian, có thể chuyển sang datetime |
| value | Giá trị số; CSV không khai báo đơn vị |

Mỗi file có 19 dòng, cách nhau 5 phút, từ 14/02/2014 14:30 đến 16:00. Giá trị nằm từ 0.066 đến 0.202; trung bình 0.126526 và trung vị 0.134. Không thấy dòng thiếu hoặc timestamp trùng. Sáu file có nội dung giống hệt nhau. Hai timestamp anomaly trong mã nằm sau khoảng quan sát; add_nab_labels vì thế gán nhãn bình thường cho mọi dòng hiện có. Điều này không chứng minh chuỗi không có anomaly; dữ liệu không bao phủ thời điểm gắn nhãn.

Mã data_prep.py khai báo URL tải bộ EC2 CPU từ NAB, nhưng không tìm thấy file nguồn đầy đủ trong workspace hoặc log chứng minh hàm tải đã chạy. Cần lấy lại file đầy đủ, ghi URL/commit, kiểm tra số dòng, khoảng thời gian, đơn vị và nhãn trước thí nghiệm. [NAB combined_labels.json](https://github.com/numenta/NAB/blob/master/labels/combined_labels.json).

## 3.2. Tiền xử lý và đặc trưng

load_timeseries chuyển timestamp, ép value sang số, loại dòng lỗi và sắp xếp thời gian. Hàm chưa báo cáo số dòng bị loại, chưa nêu chính sách timestamp trùng và không xác nhận đơn vị.

add_time_features tạo hour, day_of_week, is_weekend, day_of_month, month và biểu diễn sin/cos cho giờ/thứ. build_feature_matrix dùng value, hour_sin, hour_cos, dow_sin, dow_cos, is_weekend. Tuy vậy, run_nab_analysis và notebook hiện truyền riêng value; API/giao diện dùng đặc trưng lịch. Cần chọn pipeline thống nhất và ghi rõ đầu vào.

## 3.3. Quy trình cần dùng cho thực nghiệm có thể bảo vệ

1. Khôi phục dữ liệu đầy đủ; xác minh nguồn, thời gian, đơn vị, thiếu/trùng và nhãn.
2. Sắp xếp theo thời gian; chia train, validation, test theo thời gian, không xáo trộn ngẫu nhiên.
3. Fit scaler và mọi thống kê MAD trên train; áp dụng phép biến đổi đó lên validation/test.
4. Dùng cùng ma trận đặc trưng, đoạn test và quy ước nhãn cho các mô hình.
5. Chọn contamination/nu theo kiến thức miền hoặc validation; không chọn tham số theo test.
6. Nếu tuning, tách riêng dữ liệu fit và validation; không chấm F1 trên chính dữ liệu đã fit.
7. Tính Precision, Recall, F1 và confusion matrix trên nhãn độc lập. Báo số anomaly thật và khoảng thời gian đánh giá.
8. Đo riêng thời gian huấn luyện và dự đoán nếu đưa ra nhận định tốc độ.

Mã hiện có ba cách chia không thống nhất: 3.000 trong notebook, 3.550 mặc định trong run_nab_analysis, và 70/30 trong API/giao diện. Hai điểm chia cố định không tương thích với 19 dòng. Với 19 dòng, chia 70/30 để lại 6 điểm test, không đủ kết luận tổng quát.

## 3.4. Môi trường

Môi trường đã kiểm tra có Python 3.10.9, pandas 2.3.3, NumPy 2.2.6, scikit-learn 1.7.2, SciPy 1.15.3 và Matplotlib 3.10.9. requirements.txt ghi phiên bản tối thiểu; không thấy lockfile. Notebook không có output đã lưu.

# Chương 4. Kết quả thực nghiệm và đánh giá

## 4.1. Kiểm tra chạy

Script cũ chạy hết nhưng sinh 4.032 điểm ngẫu nhiên. Hai spike được chèn tại chỉ số 1000 và 2500; nhãn timestamp tương ứng chỉ số 3547 và 3777. MAD đánh dấu 4 điểm nhưng bỏ lỡ cả hai nhãn; Isolation Forest và LOF không đánh dấu điểm nào trong test và cũng bỏ lỡ cả hai nhãn. Đây là chẩn đoán sự không khớp giữa dữ liệu giả và nhãn, không phải thực nghiệm NAB.

Pipeline mới run_nab_analysis dừng với ValueError do split_index mặc định 3550 lớn hơn số dòng. Notebook dùng split=3000 nên test rỗng. Gọi trực tiếp API handler xử lý CSV 19 dòng nhưng không trả metric do không có nhãn; test có 6 dòng. Vì vậy chưa có thí nghiệm hợp lệ để điền bảng so sánh.

## 4.2. Bảng kết quả

| Phương pháp | Precision | Recall | F1 | Số cảnh báo | Trạng thái |
|---|---:|---:|---:|---:|---|
| Robust Z-score/MAD | Chưa xác định | Chưa xác định | Chưa xác định | Chưa báo cáo | CSV không có nhãn phù hợp; điểm fit cần thống nhất |
| Isolation Forest | Chưa xác định | Chưa xác định | Chưa xác định | Chưa báo cáo | Pipeline chính lỗi; dữ liệu không có anomaly nhãn |
| LOF | Chưa xác định | Chưa xác định | Chưa xác định | Chưa báo cáo | Pipeline chính lỗi; test quá nhỏ |
| One-Class SVM | Chưa xác định | Chưa xác định | Chưa xác định | Chưa báo cáo | Chưa có test gán nhãn hợp lệ |

“Chưa xác định” không có nghĩa là metric bằng 0. Không có căn cứ kết luận mô hình nào tốt nhất. Không đưa accuracy hoặc biểu đồ hiệu năng giả định vào báo cáo.

## 4.3. Đánh giá hạn chế

So sánh hiện tại chưa công bằng vì các đường chạy khác nhau về đặc trưng và điểm chia. MAD trong luồng nghiên cứu dùng thống kê toàn chuỗi; tune_model chấm trên dữ liệu đã fit. CSV không có nhãn tương ứng. Chưa đo riêng thời gian huấn luyện và dự đoán. Các hình minh họa luồng/mã không thay thế biểu đồ kết quả thực nghiệm.

# Chương 5. Kết luận và hướng phát triển

## 5.1. Kết luận

Dự án có mã cho xử lý CSV, đặc trưng lịch, MAD, Isolation Forest, LOF, One-Class SVM, biểu đồ, API và giao diện Streamlit. Tuy nhiên, dữ liệu cục bộ chỉ có 19 quan sát mỗi file và sáu file là bản sao giống nhau. Nhãn NAB nằm ngoài khoảng dữ liệu; pipeline mặc định không chạy được. Vì vậy, phần tích hợp thuật toán có thành phần mã nguồn, nhưng mục tiêu so sánh hiệu năng bằng thực nghiệm đáng tin cậy chưa hoàn thành.

Không có bằng chứng MySQL được sử dụng. Dự án hiện chưa phải hệ thống giám sát trực tiếp DBMS, và chưa thể khẳng định thuật toán nào phát hiện tốt hơn trên dữ liệu này.

## 5.2. Hạn chế

- Dữ liệu ngắn, các file lặp bản sao và không có nhãn anomaly trong khoảng.
- Đơn vị, provenance và phiên bản CSV chưa được ghi lại.
- Điểm chia không thống nhất; hai cấu hình cố định vượt kích thước mẫu.
- MAD có nguy cơ rò rỉ thông tin; tuning fit và chấm trên cùng dữ liệu.
- Đường chạy mô hình không thống nhất ma trận đặc trưng.
- Không có log, notebook output hoặc metric hợp lệ đã lưu.
- Không có telemetry DBMS hoặc kết nối MySQL.

## 5.3. Hướng phát triển

1. Khôi phục dữ liệu NAB đầy đủ hoặc chọn nguồn metric DBMS có provenance, nhãn và đơn vị.
2. Dùng một pipeline với train/validation/test theo thời gian; đặt điểm chia theo độ dài thực.
3. Fit scaler và baseline trên train; tuning trên validation; đánh giá test một lần.
4. Dùng chung đặc trưng và đoạn test, lưu cấu hình, log, metric và biểu đồ thật.
5. Nếu giữ phạm vi DBMS, thu thập latency truy vấn, throughput, connections, lock waits, buffer pool, I/O, CPU và bộ nhớ.
6. Chỉ thêm kết nối MySQL khi cần thu thập dữ liệu trực tiếp; thí nghiệm CSV hiện tại không cần MySQL.

# Phụ lục A. Bảng rà soát báo cáo cũ

| Vị trí | Vấn đề | Mức độ | Cách khắc phục |
|---|---|---|---|
| Tiêu đề/mục tiêu | Nói về DBMS nhưng chưa có kết nối hoặc metric DBMS. | Nghiêm trọng | Đổi tên theo chuỗi CPU hoặc bổ sung dữ liệu/telemetry DBMS thật. |
| baocao.md, dữ liệu | Nêu ec2_cpu_utilization.csv có 4.032 điểm; file không có trong workspace. | Nghiêm trọng | Ghi 19 dòng mỗi CSV; cập nhật sau khi lấy file nguồn đầy đủ. |
| README, dữ liệu | Nói cpu_0 đến cpu_5 có 4.032 điểm. | Nghiêm trọng | Sửa thành 19 dòng và ghi rõ sáu file giống hệt nhau. |
| baocao.md, kết quả kiểm thử | Ghi CSV 72 dòng, hai anomaly, các hạng mục “Đạt”. | Nghiêm trọng | CSV có 19 dòng và không có nhãn trong khoảng; bỏ khẳng định không có log hỗ trợ. |
| Notebook/script mới | Chia tại 3000/3550 trong khi chỉ có 19 dòng. | Nghiêm trọng | Sửa sau khi khôi phục dữ liệu và lưu output chạy lại. |
| Script cũ | Sinh dữ liệu giả nhưng nhãn NAB không trùng spike. | Nghiêm trọng | Chỉ mô tả là minh họa giả lập, không coi là kết quả NAB. |
| MAD/tuning | MAD dùng toàn chuỗi; tune_model fit rồi chấm cùng dữ liệu. | Nghiêm trọng | Tách train/validation/test theo thời gian; fit thống kê trên train. |
| Mô tả đầu vào | Notebook chỉ dùng value; API/giao diện dùng đặc trưng lịch. | Quan trọng | Chọn đầu vào thống nhất và mô tả rõ. |
| Tuning | Hàm tồn tại nhưng không thấy được gọi trong luồng chạy. | Quan trọng | Không nói đã tuning cho đến khi có log và validation riêng. |
| Hình/bảng | SVG minh họa mã/luồng không phải biểu đồ hiệu năng. | Quan trọng | Phân biệt hình kiến trúc với kết quả thực nghiệm. |
| Tài liệu tham khảo | Báo cáo cũ thiếu trích dẫn và danh mục. | Quan trọng | Bổ sung nguồn đã xác minh ở Phụ lục B. |
| Đơn vị/nguồn dữ liệu | CSV không ghi đơn vị, phiên bản hoặc provenance. | Quan trọng | Xác nhận từ nguồn gốc; ghi URL/commit, đơn vị và khoảng thời gian. |
| Thuật ngữ/trình bày | Thuật ngữ anomaly chưa nhất quán; số hình/bảng chưa theo chương. | Cải thiện | Dùng “điểm bất thường” thống nhất; đánh số hình/bảng theo chương và ghi nguồn. |

### Nội dung đúng có thể giữ từ báo cáo cũ

- Mục tiêu tổng quát phát hiện bất thường trên chuỗi thời gian.
- Sơ đồ CSV → tiền xử lý/đặc trưng → detector → kết quả.
- Mô tả khái quát về Isolation Forest, LOF và One-Class SVM sau khi gắn nguồn.
- Các chức năng có trong mã: loader, đặc trưng lịch, biểu đồ Plotly, API và giao diện.
- Hướng mở rộng dữ liệu, cảnh báo và lưu lịch sử nếu ghi là kế hoạch.

### Cấu trúc báo cáo cuối cùng đề xuất

1. **Chương 1 – Tổng quan:** lý do, bài toán, câu hỏi nghiên cứu, mục tiêu và phạm vi.
2. **Chương 2 – Cơ sở lý thuyết:** chuỗi thời gian, dạng anomaly, cửa sổ trượt, MAD, Isolation Forest, LOF, One-Class SVM và metric.
3. **Chương 3 – Dữ liệu và phương pháp:** nguồn/phiên bản, schema/đơn vị, tiền xử lý, nhãn, đặc trưng, chia thời gian, tham số và môi trường.
4. **Chương 4 – Kết quả:** số liệu tái lập, cùng đoạn test, metric, phân tích sai/bỏ sót và thời gian chạy.
5. **Chương 5 – Kết luận:** mục tiêu đạt/chưa đạt, hạn chế và hướng phát triển.

# Phụ lục B. Tài liệu tham khảo đã xác minh

[1] A. Lavin và S. Ahmad, “Evaluating Real-time Anomaly Detection Algorithms – the Numenta Anomaly Benchmark,” arXiv:1510.03336, 2015. [Bản ghi arXiv](https://arxiv.org/abs/1510.03336).

[2] Numenta, “The Numenta Anomaly Benchmark.” [Kho NAB](https://github.com/numenta/NAB), [README dữ liệu](https://github.com/numenta/NAB/blob/master/data/README.md), [combined_labels.json](https://github.com/numenta/NAB/blob/master/labels/combined_labels.json).

[3] F. T. Liu, K. M. Ting và Z.-H. Zhou, “Isolation Forest,” Proceedings of the 2008 Eighth IEEE International Conference on Data Mining, 2008, DOI: 10.1109/ICDM.2008.17. [DOI](https://doi.org/10.1109/ICDM.2008.17).

[4] M. M. Breunig, H.-P. Kriegel, R. T. Ng và J. Sander, “LOF: Identifying Density-Based Local Outliers,” ACM SIGMOD Record, 29(2), 93–104, 2000, DOI: 10.1145/335191.335388. [DOI](https://doi.org/10.1145/335191.335388).

[5] B. Schölkopf, J. C. Platt, J. Shawe-Taylor, A. J. Smola và R. C. Williamson, “Estimating the Support of a High-Dimensional Distribution,” Neural Computation, 13(7), 1443–1471, 2001, DOI: 10.1162/089976601750264965. [DOI](https://doi.org/10.1162/089976601750264965).

[6] scikit-learn developers, “Novelty and Outlier Detection.” [Tài liệu chính thức](https://scikit-learn.org/stable/modules/outlier_detection).

[7] NIST/SEMATECH, “Exploratory Data Analysis,” phần modified Z-score dựa trên MAD. [Tài liệu NIST](https://www.itl.nist.gov/div898/handbook/toolaids/pff/eda.pdf).

[8] Oracle, “MySQL 8.4 Reference Manual,” status variables và Performance Schema. [Server Status Variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html), [Statement Summary Tables](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html).

[9] SciPy developers, “scipy.stats.median_abs_deviation.” [Tài liệu SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.median_abs_deviation.html).

## Các việc cần hoàn tất trước khi nộp

- Khôi phục và xác minh dữ liệu đầy đủ, nhãn, đơn vị và nguồn.
- Chốt với giảng viên việc giữ tên đề tài DBMS hay đổi theo chuỗi CPU.
- Sửa điểm chia và xử lý leakage trước khi chạy thí nghiệm.
- Chạy lại pipeline trên tập có nhãn; lưu cấu hình, log, output và biểu đồ.
- Chỉ điền bảng metric sau khi chạy trên cùng tập test hợp lệ.
- Nếu giữ phạm vi DBMS, bổ sung collector và dataset DBMS; hiện chưa triển khai.
- Khởi chạy kiểm tra HTTP API và giao diện sau khi sửa quy trình dữ liệu; lần rà soát này chỉ gọi trực tiếp API handler.

