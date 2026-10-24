# Hướng dẫn cài đặt và chạy chương trình phát hiện bất thường

## 1. Giới thiệu

Chương trình trong `DACN/anomaly_detection.py` phát hiện dữ liệu bất thường trong chuỗi thời gian sử dụng CPU bằng các phương pháp:

- Median Absolute Deviation (MAD)
- Isolation Forest
- Local Outlier Factor (LOF)

## 2. Thư viện cần cài đặt

Cài đặt các thư viện bằng lệnh:

```bash
pip install pandas numpy matplotlib seaborn scipy scikit-learn
```

Ý nghĩa của từng thư viện:

- `pandas`: đọc và xử lý dữ liệu dạng bảng.
- `numpy`: tính toán số học và tạo dữ liệu mẫu.
- `matplotlib`: vẽ biểu đồ và ma trận nhầm lẫn.
- `seaborn`: hỗ trợ trực quan hóa dữ liệu.
- `scipy`: tính Median Absolute Deviation.
- `scikit-learn`: cung cấp Isolation Forest, LOF và các công cụ đánh giá mô hình.

Thư viện `warnings` có sẵn trong Python nên không cần cài đặt.

## 3. Tạo môi trường ảo trên Windows

Mở PowerShell hoặc Command Prompt tại thư mục `C:\Users\User\DACN`, sau đó chạy:

```bash
python -m venv .venv
```

Kích hoạt môi trường ảo bằng PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Hoặc bằng Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

Sau đó cài đặt thư viện:

```bash
pip install pandas numpy matplotlib seaborn scipy scikit-learn
```

## 4. Chạy chương trình

Từ thư mục `C:\Users\User\DACN`, chạy:

```bash
python DACN\anomaly_detection.py
```

Chương trình sẽ:

1. Tạo dữ liệu CPU mẫu.
2. Chèn một số điểm bất thường.
3. Hiển thị biểu đồ dữ liệu.
4. Phát hiện bất thường bằng MAD.
5. Phát hiện bất thường bằng Isolation Forest.
6. Phát hiện bất thường bằng LOF.
7. Hiển thị ma trận nhầm lẫn cho từng phương pháp.

## 5. Sử dụng dữ liệu CSV thực tế

Hiện tại chương trình đang tạo dữ liệu giả lập. Để sử dụng dữ liệu thật, thay phần tạo dữ liệu bằng:

```python
df = pd.read_csv("data/ec2_cpu_utilization.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
```

File CSV cần có tối thiểu các cột:

- `timestamp`: thời gian đo.
- `value`: giá trị CPU.

Để đánh giá mô hình, cần có thêm cột `is_anomaly`:

- `1`: dữ liệu bình thường.
- `-1`: dữ liệu bất thường.

## 6. Hướng phát triển

### 6.1. Tách chương trình thành các hàm

Nên tách mã nguồn thành các hàm riêng để dễ bảo trì và kiểm thử:

- Đọc dữ liệu.
- Tiền xử lý dữ liệu.
- Phát hiện bằng MAD.
- Phát hiện bằng Isolation Forest.
- Phát hiện bằng LOF.
- Đánh giá mô hình.
- Vẽ biểu đồ.

### 6.2. Bổ sung kiểm tra dữ liệu

Nên kiểm tra:

- Dữ liệu bị thiếu.
- Dữ liệu trùng lặp.
- Dữ liệu có được sắp xếp theo thời gian hay chưa.
- Các giá trị không hợp lệ.

### 6.3. Bổ sung chỉ số đánh giá

Ngoài confusion matrix, có thể sử dụng thêm Precision, Recall và F1-score:

```python
from sklearn.metrics import classification_report

print(classification_report(
    test["is_anomaly"],
    preds_iso_forest,
    labels=[1, -1]
))
```

### 6.4. Lưu kết quả

Có thể lưu kết quả dự đoán vào file CSV:

```python
test.to_csv("output/anomaly_results.csv", index=False)
```

### 6.5. Xây dựng giao diện hoặc API

Các hướng phát triển tiếp theo:

- Xây dựng dashboard bằng Streamlit.
- Xây dựng API dự đoán bằng FastAPI.
- Theo dõi CPU theo thời gian thực.
- Gửi cảnh báo khi phát hiện điểm bất thường.

## 7. Lưu ý

- `seaborn` hiện được import nhưng chưa được sử dụng trực tiếp trong chương trình.
- Các nhãn bất thường phải sử dụng thống nhất quy ước `1` là bình thường và `-1` là bất thường.
- Tham số `contamination` của Isolation Forest và LOF nên được điều chỉnh theo tỷ lệ bất thường thực tế.