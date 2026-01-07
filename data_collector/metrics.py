import os
from prometheus_client import start_http_server, Counter, Gauge

# Labels
SERVICE_NAME = "data_collector"
NODE_NAME = os.getenv("NODE_NAME", "placeholder") # Diventerà dinamico con K8s

# Metrics
HTTP_REQUESTS_TOTAL = Counter('http_requests_total', 'Total HTTP Requests', ['service', 'node'])

def init_monitoring():
    start_http_server(9999, addr='0.0.0.0')
    print(f"Prometheus metrics are available at endpoint: metrics, port: 9999")
