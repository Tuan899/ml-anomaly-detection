"""The three small, labeled CSV examples delivered with the application."""

NORMAL_SAMPLE = "mysql_normal.csv"
DEFAULT_ANOMALOUS_SAMPLE = "mysql_query_spike.csv"
ANOMALOUS_SAMPLES = {
    "Tăng lượng truy vấn": DEFAULT_ANOMALOUS_SAMPLE,
    "Phản hồi chậm": "mysql_latency_spike.csv",
}
