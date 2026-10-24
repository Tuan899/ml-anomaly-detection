import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings

warnings.filterwarnings('ignore')

# Cài đặt kích thước mặc định cho biểu đồ
plt.rcParams["figure.figsize"] = (9, 4)

# ==========================================
# 1. ĐỌC VÀ CHUẨN BỊ DỮ LIỆU
# ==========================================
# Giả sử bạn đã tải tập dữ liệu ec2_cpu_utilization_24ae8d.csv
# df = pd.read_csv('data/ec2_cpu_utilization.csv')

# (Đoạn mã này tạo dữ liệu giả lập để bạn có thể chạy thử trực tiếp nếu chưa có file csv)
np.random.seed(42)
dates = pd.date_range(start='2014-02-14 14:30:00', periods=4032, freq='5min')
values = np.random.normal(0.1, 0.02, 4032)
df = pd.DataFrame({'timestamp': dates, 'value': values})
# Chèn một số điểm bất thường (anomalies) giả lập
df.loc[1000, 'value'] = 2.0
df.loc[2500, 'value'] = 1.5

# Chuyển đổi cột timestamp sang định dạng datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Tạo cột gán nhãn thực tế (Ground Truth)
# Trong Sklearn: 1 thường là bình thường (inlier), -1 là bất thường (outlier). 
# Tuy nhiên tùy bài toán, ở đây ta cứ khởi tạo -1 hoặc 1 theo nhãn thực tế.
df['is_anomaly'] = 1 
# Đánh dấu các điểm bất thường (thực tế dữ liệu mẫu gán theo thời gian cụ thể)
anomalies_timestamp = [
    "2014-02-26 22:05:00",
    "2014-02-27 17:15:00"
]
for each in anomalies_timestamp:
    df.loc[df['timestamp'] == each, 'is_anomaly'] = -1 

# Vẽ biểu đồ phân tán (Scatter Plot) xem mức sử dụng CPU
fig, ax = plt.subplots()
ax.scatter(df.index, df['value'], color='blue', s=3, label='inlier')
anomaly_df = df[df['is_anomaly'] == -1]
ax.scatter(anomaly_df.index, anomaly_df['value'], color='red', s=10, label='anomaly')
ax.set_xlabel('Time')
ax.set_ylabel('CPU usage')
ax.legend(loc=2)
plt.tight_layout()
plt.show()

# ==========================================
# 2. BASELINE: MEDIAN ABSOLUTE DEVIATION (MAD)
# ==========================================
from scipy.stats import median_abs_deviation
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

# Tính toán MAD và Median
mad = median_abs_deviation(df['value'])
median = np.median(df['value'])

# Hàm tính Z-score mạnh (Robust Z-score)
def compute_robust_z_score(x):
    return 0.6745 * (x - median) / mad

df['z_score'] = df['value'].apply(compute_robust_z_score)

# Đặt ngưỡng đánh giá (ví dụ: Z-score > 3.5 là bất thường)
df['baseline'] = 1  # 1 là bình thường
df.loc[df['z_score'] >= 3.5, 'baseline'] = -1 # -1 là bất thường

# Đánh giá Baseline bằng Ma trận nhầm lẫn (Confusion Matrix)
cm = confusion_matrix(df['is_anomaly'], df['baseline'], labels=[1, -1])
disp_cm = ConfusionMatrixDisplay(cm, display_labels=[1, -1])
disp_cm.plot()
plt.title("Confusion Matrix - MAD Baseline")
plt.tight_layout()
plt.show()

# ==========================================
# 3. ISOLATION FOREST
# ==========================================
from sklearn.ensemble import IsolationForest

# Chia tập train/test (ví dụ: 3000 điểm đầu để train, phần còn lại để test)
train = df[:3000]
test = df[3000:]

# Khởi tạo mô hình
contamination = 1 / len(train)
iso_forest = IsolationForest(contamination=contamination, random_state=42)

# Reshape dữ liệu 1D thành 2D array cho sklearn
X_train = train['value'].values.reshape(-1, 1)
iso_forest.fit(X_train)

X_test = test['value'].values.reshape(-1, 1)
preds_iso_forest = iso_forest.predict(X_test)

# Đánh giá Isolation Forest
cm_iso = confusion_matrix(test['is_anomaly'], preds_iso_forest, labels=[1, -1])
disp_cm_iso = ConfusionMatrixDisplay(cm_iso, display_labels=[1, -1])
disp_cm_iso.plot()
plt.title("Confusion Matrix - Isolation Forest")
plt.tight_layout()
plt.show()

# ==========================================
# 4. LOCAL OUTLIER FACTOR (LOF)
# ==========================================
from sklearn.neighbors import LocalOutlierFactor

# Khởi tạo mô hình LOF (với novelty=True để có thể predict trên tập test)
lof = LocalOutlierFactor(contamination=contamination, novelty=True)
lof.fit(X_train)

preds_lof = lof.predict(X_test)

# Đánh giá LOF
cm_lof = confusion_matrix(test['is_anomaly'], preds_lof, labels=[1, -1])
disp_cm_lof = ConfusionMatrixDisplay(cm_lof, display_labels=[1, -1])
disp_cm_lof.plot()
plt.title("Confusion Matrix - Local Outlier Factor")
plt.tight_layout()
plt.show()
