import os
from prometheus_client import start_http_server, Counter, Gauge

# Labels
SERVICE_NAME = "data_collector"
NODE_NAME = os.getenv("NODE_NAME", "placeholder") # Diventerà dinamico con K8s

# Metrics
REQUESTS_COUNT = Counter(
    'http_requests_total', 
    'Total HTTP Requests', 
    ['service', 'node', 'endpoint', 'method']
    )
ERRORS_COUNT = Counter(
    'errors_total', 
    'Total Errors', 
    ['service', 'node', 'endpoint', 'method']
    )

RESPONSE_TIME = Gauge(
    'response_time', 
    'Response time to the last request in seconds', 
    ['service', 'node', 'endpoint', 'method']
    )
DB_UPDATE_TIME = Gauge(
    'db_update_time', 
    'Tempo impiegato per l\'aggiornamento del database', 
    ['service', 'node', 'operation']
    )

OPENSKY_FETCH_TIME = Gauge(
    'opensky_fetch_time', 
    'Tempo impiegato per il recupero dei dati da OpenSky', 
    ['service', 'node', 'operation']
    )

def init_monitoring() :
    start_http_server(9999)
    print(f"Prometheus metrics are available at endpoint: metrics, port: 9999")
