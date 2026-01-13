# DSBD Homework

Sistema distribuito per la raccolta e gestione di dati sui voli tramite microservizi con sistema di allerta basato su messaggistica Kafka. Il sistema permette agli utenti di registrarsi, specificare aeroporti di interesse con soglie di monitoraggio personalizzate, ricevere informazioni sui voli e notifiche email automatiche quando le condizioni di allerta vengono soddisfatte.

## 📋 Indice

- [Componenti](#componenti)
- [Prerequisiti](#prerequisiti)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)
- [API Endpoints](#api-endpoints)
- [Tecnologie](#tecnologie)
- [Struttura del Progetto](#struttura-del-progetto)


### Caratteristiche principali:

**Homework 1:**
- **Idempotenza**: Le operazioni di scrittura sono idempotenti grazie a Redis
- **Comunicazione gRPC**: User Manager e Data Collector comunicano tramite gRPC
- **Worker periodico**: Aggiornamento automatico dei dati sui voli ogni 12 ore
- **Persistenza**: Database MySQL separati per utenti e dati sui voli

**Homework 2:**
- **Messaggistica Kafka**: Sistema publish-subscribe per comunicazione asincrona
- **Alert System**: Monitoraggio automatico delle soglie personalizzate per utente
- **Notifiche Email**: Invio automatico di email tramite sistema di notifica dedicato
- **Circuit Breaker**: Pattern di resilienza per chiamate all'API OpenSky
- **API Gateway**: Reverse proxy Nginx con supporto HTTPS
- **Soglie Personalizzate**: Ogni utente può impostare soglie min/max per i propri aeroporti

**Homework 3:**
- **White-Box Monitoring**: Sistema di monitoraggio basato su Prometheus
- **Metriche COUNTER**: Tracciamento richieste HTTP totali e errori per servizio
- **Metriche GAUGE**: Monitoraggio response time e tempi di aggiornamento DB
- **Label Service e Node**: Ogni metrica identifica servizio e nodo Kubernetes
- **Deployment Kubernetes**: Applicazione deployata su cluster Kind locale
- **Orchestrazione K8s**: Manifest completi per tutti i componenti

## 🔧 Componenti

### 1. User Manager
Gestisce gli utenti del sistema con le seguenti funzionalità:
- Registrazione utenti (idempotente)
- Cancellazione utenti (idempotente)
- Verifica credenziali (gRPC)
- Verifica esistenza utente (gRPC)
- Cache con Redis per idempotenza

**Tecnologie**: Flask, gRPC, MySQL, Redis

### 2. Data Collector
Gestisce i dati sui voli e le associazioni utente-aeroporto:
- Aggiunta/rimozione aeroporti di interesse per utente con soglie personalizzate
- Recupero voli da OpenSky Network API (OAuth2) con Circuit Breaker
- Worker periodico per aggiornamento automatico dati (ogni 12h)
- Query avanzate (ultimo volo, media voli giornalieri)
- Produttore Kafka per notifiche di aggiornamento

**Tecnologie**: Flask, gRPC client, MySQL, OpenSky API, Kafka Producer, Circuit Breaker

### 3. Kafka Broker
Message broker per comunicazione asincrona:
- Modalità KRaft (senza Zookeeper)
- Topic `to-alert-system`: Notifiche di aggiornamento voli
- Topic `to-notifier`: Allerte da inviare via email
- Retention: 24 ore, max 1GB

**Tecnologie**: Confluent Kafka 7.4.0

### 4. Alert System
Sistema di elaborazione degli alert:
- Consumer Kafka (topic: `to-alert-system`)
- Verifica soglie personalizzate per utente/aeroporto
- Generazione notifiche quando le soglie vengono superate
- Producer Kafka per invio a Alert Notifier

**Tecnologie**: Python, Kafka Consumer/Producer, MySQL

### 5. Alert Notifier System
Sistema di invio notifiche:
- Consumer Kafka (topic: `to-notifier`)
- Composizione e invio email
- Integrazione con MailHog per testing

**Tecnologie**: Python, Kafka Consumer, SMTP

### 6. MailHog
SMTP test server per visualizzazione email:
- Interfaccia web (porta 8025)
- SMTP server (porta 1025)
- Cattura tutte le email inviate

**Tecnologie**: MailHog

### 7. API Gateway
Reverse proxy per routing e sicurezza:
- Routing: `/api/users/` → User Manager, `/api/data/` → Data Collector
- Supporto HTTP (porta 8080) e HTTPS (porta 8443)
- Certificati SSL self-signed
- Rate limiting e body size control

**Tecnologie**: Nginx

### 8. Prometheus
Sistema di monitoraggio white-box per metriche dei microservizi:
- Scraping automatico da User Manager e Data Collector (porta 9999)
- Raccolta metriche ogni 10 secondi
- Interfaccia web per query e visualizzazione (porta 9090)
- Storage persistente su PVC Kubernetes

**Metriche raccolte**:
- **COUNTER**: `http_requests_total`, `errors_total` (errori 5xx)
- **GAUGE**: `response_time` (secondi), `db_update_time` (secondi)
- **Label**: `service` (nome microservizio), `node` (nodo Kubernetes), `endpoint`, `method`

**Tecnologie**: Prometheus 2.x, prometheus_client (Python)

### 3. Database

#### MySQL User DB (usermanager_db)
```sql
users (
  email VARCHAR(255) PRIMARY KEY,
  cf VARCHAR(255),
  password VARCHAR(255) NOT NULL
)
```

#### MySQL Data DB (data_db)
```sql
user_airports (
  user_email VARCHAR(255),
  airport_code CHAR(4),
  high_value INT,           -- Soglia massima per alert
  low_value INT,            -- Soglia minima per alert
  PRIMARY KEY (user_email, airport_code)
)

flights (
  airport_code CHAR(4),
  direction VARCHAR(255),
  flight_icao CHAR(6) PRIMARY KEY,
  callsign VARCHAR(10),
  flight_time DATETIME
)
```

#### Redis Cache
- Chiavi di idempotenza con TTL per operazioni di registrazione/cancellazione
- Pattern: `{operation}:{requestID}:{content_hash}`

## 📦 Prerequisiti

- Docker
- Kind (Kubernetes in Docker) v0.20+
- kubectl configurato
- Credenziali OpenSky Network API (CLIENT_ID e CLIENT_SECRET)

## 🚀 Installazione

Deployment completo su cluster Kubernetes locale con Kind.

1. **Clone del repository**
```bash
git clone https://github.com/LucaEterno/dsbd-homework1.git
cd dsbd-homework1
```

2. **Configurazione credenziali OpenSky**

Modifica `kubernetes/opensky_credentials.yaml` con le tue credenziali (Base64 encoded):
```bash
echo -n "tuo-client-id" | base64
echo -n "tuo-client-secret" | base64
```

3. **Avvio automatico con script Python**
```bash
python3 start.py
```

Lo script esegue automaticamente:
- Creazione cluster Kind (control-plane + worker)
- Build delle immagini Docker
- Caricamento immagini nel cluster Kind
- Deploy in 3 fasi:
  1. Ingress Controller (NGINX)
  2. Infrastruttura (DB, Kafka, Redis, Prometheus, Secrets)
  3. Microservizi e Ingress rules
- Attesa readiness di tutti i deployment

4. **Verifica dello stato**
```bash
kubectl get pods --all-namespaces
kubectl get services
kubectl get ingress
```

5. **Accesso ai servizi**
- **Prometheus**: http://localhost:9090
- **MailHog**: http://localhost:8025
- **API Gateway**: http://localhost/api/ (tramite Ingress)

6. **Cleanup**
```bash
# Eliminare il cluster
kind delete cluster --name myapp
```

## 💡 Utilizzo
### Nei Documenti è presente un .json per un utilizzo guidato tramite POSTMAN
### Esempio: Workflow completo

```bash
# 1. Registrazione utente
curl -X POST http://progettoeternograsso.com/api/users/users/register \
  -H "Content-Type: application/json" \
  -H "requestID: unique-request-id-123" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "cf": "RSSMRA80A01H501U"
  }'

# 2. Aggiunta aeroporto di interesse con soglie di monitoraggio
curl -X POST http://progettoeternograsso.com/api/data/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "airport_code": "LICC",
    "high_value": 50,
    "low_value": 10
  }'

# 2b. Modifica soglie per un aeroporto esistente
curl -X PUT http://progettoeternograsso.com/api/data/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "airport_code": "LICC",
    "high_value": 60,
    "low_value": 15
  }'

# 3. Recupero lista aeroporti
curl "http://progettoeternograsso.com/api/data/user/airports?email=mario.rossi@example.com"

# 4. Refresh manuale dei voli per un aeroporto
curl -X POST http://progettoeternograsso.com/api/data/airport/LICC/refresh-flights \
  -H "Content-Type: application/json" \
  -d '{
    "hours": 12,
    "direction": "both"
  }'

# 5. Visualizza tutti i voli per gli aeroporti dell'utente
curl "http://progettoeternograsso.com/api/data/user/flights?email=mario.rossi@example.com"

# 6. Ultimo volo per un aeroporto
curl "http://progettoeternograsso.com/api/data/user/flights/last?email=mario.rossi@example.com&airport_code=LICC"

# 7. Media voli giornalieri
curl "http://progettoeternograsso.com/api/data/user/flights/average?email=mario.rossi@example.com&airport_code=LICC&days=7"

# 8. Cancellazione utente
curl -X DELETE http://progettoeternograsso.com/api/users/users/delete \
  -H "Content-Type: application/json" \
  -H "requestID: unique-request-id-456" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword"
  }'
```

## 📡 API Endpoints

**Tutti gli endpoint sono accessibili tramite Ingress su**: `http://progettoeternograsso.com/api/`

### User Manager

Base path: `/api/users/`

#### POST /users/register
Registra un nuovo utente (idempotente)

**Headers richiesti**: `requestID`

**Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "cf": "CODICEFISCALE"
}
```

**Risposte**:
- `201`: Utente creato
- `409`: Email già registrata
- `400`: Dati mancanti o requestID assente

#### DELETE /users/delete
Cancella un utente esistente (idempotente)

**Headers richiesti**: `requestID`

**Body**:
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Risposte**:
- `200`: Utente cancellato
- `401`: Credenziali errate
- `400`: Dati mancanti o requestID assente

### Data Collector

Base path: `/api/data/`

#### POST /user/airports
Aggiunge un aeroporto di interesse per l'utente con soglie opzionali

**Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "airport_code": "LICC",
  "high_value": 50,  // opzionale - soglia massima per alert
  "low_value": 10    // opzionale - soglia minima per alert
}
```

**Risposte**:
- `201`: Aeroporto aggiunto
- `200`: Aeroporto già registrato
- `401`: Credenziali errate
- `400`: Formato ICAO invalido

#### PUT /user/airports
Modifica le soglie di monitoraggio per un aeroporto esistente

**Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "airport_code": "LICC",
  "high_value": 60,  // almeno uno richiesto
  "low_value": 20    // almeno uno richiesto
}
```

**Risposte**:
- `200`: Soglie aggiornate
- `401`: Credenziali errate
- `404`: Associazione non esistente
- `400`: Parametri invalidi (high_value deve essere > low_value)

#### GET /user/airports
Ottiene la lista degli aeroporti di interesse con le soglie configurate

**Query params**: `email`

**Risposta**:
```json
{
  "email": "user@example.com",
  "airports": [
    {
      "airport_code": "LICC",
      "high_value": 50,
      "low_value": 10
    },
    {
      "airport_code": "LIRF",
      "high_value": null,
      "low_value": 5
    }
  ],
  "count": 2
}
```

#### DELETE /user/airports
Rimuove aeroporti di interesse

**Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "airport_code": "LICC"  // opzionale - se omesso rimuove tutti
}
```

#### GET /user/flights
Ottiene tutti i voli per gli aeroporti dell'utente

**Query params**: `email`

#### GET /user/flights/last
Ottiene l'ultimo volo in arrivo e partenza

**Query params**: `email`, `airport_code`

**Risposta**:
```json
{
  "email": "user@example.com",
  "airport_code": "LICC",
  "last_arrival": {
    "flight_icao": "abc123",
    "callsign": "AZ123",
    "flight_time": "2025-11-30T10:30:00"
  },
  "last_departure": { ... }
}
```

#### GET /user/flights/average
Calcola la media di voli giornalieri

**Query params**: `email`, `airport_code`, `days`

**Risposta**:
```json
{
  "email": "user@example.com",
  "airport_code": "LICC",
  "days": 7,
  "average_flights": {
    "arrival_per_day": 12.5,
    "departure_per_day": 11.8,
    "total_flights_in_period": {
      "arrivals": 88,
      "departures": 83
    }
  }
}
```

#### POST /airport/{airport_code}/refresh-flights
Aggiorna manualmente i dati sui voli

**Body**:
```json
{
  "hours": 12,
  "direction": "both"  // "arrival", "departure", "both"
}
```

## 🛠️ Tecnologie

### Homework 1
- **Python 3.11**: Linguaggio principale
- **Flask**: Framework web per REST API
- **gRPC**: Comunicazione inter-servizi
- **MySQL 8.0**: Database relazionale
- **Redis 7**: Cache per idempotenza
- **Docker & Docker Compose**: Containerizzazione e orchestrazione
- **OpenSky Network API**: Sorgente dati sui voli (OAuth2)

### Homework 2
- **Apache Kafka 7.4.0**: Message broker (modalità KRaft)
- **Nginx**: Reverse proxy e API Gateway
- **MailHog**: SMTP test server per development
- **Circuit Breaker Pattern**: Resilienza per servizi esterni

### Homework 3
- **Kubernetes**: Orchestrazione container su cluster Kind
- **Prometheus**: Sistema di monitoraggio white-box
- **Kind**: Kubernetes locale in Docker
- **Ingress NGINX**: Controller per routing HTTP/HTTPS

### Librerie Python principali:
- `flask`: Web framework
- `grpcio`: gRPC runtime
- `mysql-connector-python`: Driver MySQL
- `redis`: Client Redis
- `requests`: HTTP client per OpenSky API
- `confluent-kafka`: Client Kafka producer/consumer

## 📁 Struttura del Progetto

```
homework1/
├── data_collector/
│   ├── app.py                    # Flask app principale
│   ├── metrics.py                # Definizione metriche Prometheus
│   ├── collector_worker.py       # Worker thread per aggiornamenti periodici
│   ├── opensky_client.py         # Logica business per voli (con CB)
│   ├── opensky_auth.py           # Autenticazione OAuth2 OpenSky
│   ├── circuit_breaker.py        # Implementazione Circuit Breaker pattern
│   ├── kafka_producer.py         # Producer Kafka per notifiche
│   ├── init_data_db.sql          # Schema DB data
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── user_manager_pb2.py       # gRPC generated
│   └── user_manager_pb2_grpc.py  # gRPC generated
├── user_manager/
│   ├── app.py                    # Flask app principale
│   ├── metrics.py                # Definizione metriche Prometheus
│   ├── server.py                 # gRPC server
│   ├── redis_utils.py            # Gestione cache Redis
│   ├── user_manager.proto        # Definizione servizio gRPC
│   ├── init_user_db.sql          # Schema DB utenti
│   ├── start.sh                  # Script di avvio (gRPC + Flask)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── user_manager_pb2.py       # gRPC generated
│   └── user_manager_pb2_grpc.py  # gRPC generated
├── alert_system/
│   ├── alerts.py                 # Consumer Kafka + logica alert
│   ├── notification_logic.py     # Verifica soglie e generazione notifiche
│   ├── Dockerfile
│   └── requirements.txt
├── alert_notifier_system/
│   ├── notifier.py               # Consumer Kafka + invio email
│   ├── Dockerfile
│   └── requirements.txt
├── kafka/
│   ├── topic_setup.sh            # Script creazione topic Kafka
│   └── Dockerfile
├── gateway/
│   ├── nginx.conf                # Configurazione Nginx
│   ├── Dockerfile
│   └── SSL_certificate/
│       ├── nginx-selfsigned.crt  # Certificato SSL
│       └── nginx-selfsigned.key  # Chiave privata SSL
├── prometheus/                   # Configurazione Prometheus
│   └── prometheus.yml            # Config scraping microservizi
├── kind/                         # Configurazione Kind cluster
│   └── config.yaml               # Cluster con control-plane + worker
├── kubernetes/                   # Manifest Kubernetes
│   ├── user_manager.yaml         # Deployment + Service User Manager
│   ├── data_collector.yaml       # Deployment + Service Data Collector
│   ├── prometheus.yaml           # Deployment + Service + NodePort Prometheus
│   ├── prometheus_init.yaml      # ConfigMap con prometheus.yml
│   ├── prometheus_pvc.yaml       # PersistentVolumeClaim per storage
│   ├── user_db.yaml              # Deployment + Service MySQL users
│   ├── data_db.yaml              # Deployment + Service MySQL data
│   ├── kafka.yaml                # Deployment + Service Kafka
│   ├── redis.yaml                # Deployment + Service Redis
│   ├── alert_system.yaml         # Deployment Alert System
│   ├── alert_notifier_system.yaml# Deployment Alert Notifier
│   ├── mailhog.yaml              # Deployment + Service MailHog
│   ├── ingress-controller.yaml   # NGINX Ingress Controller
│   ├── ingress.yaml              # Ingress rules per routing
│   ├── *_secrets.yaml            # Secrets per DB e OpenSky
│   ├── *_init.yaml               # ConfigMap per init script
│   └── *_pvc.yaml                # PersistentVolumeClaim per DB
├── docs/
│   ├── API.md                    # Documentazione API completa
│   └── DSBD-HW3.postman_collection.json  # Collection Postman
├── start.py                      # Script deploy automatico Kubernetes
├── docker-compose.yaml           # Orchestrazione Docker Compose
├── .gitignore
├── LICENSE
└── README.md
```

## ⚙️ Configurazione

### Variabili d'ambiente

Tutte le variabili sono configurate nei manifest Kubernetes (file `kubernetes/*.yaml`):

**User Manager**:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `LISTEN_PORT`: Porta Flask (default: 5003)
- `DATACOLLECTOR_BASE_URL`: URL del Data Collector

**Data Collector**:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
- `LISTEN_PORT`: Porta Flask (default: 5002)
- `USER_MANAGER_HOST`, `USER_MANAGER_PORT`: gRPC endpoint
- `CLIENT_ID`, `CLIENT_SECRET`: Credenziali OpenSky
- `KAFKA_BOOTSTRAP_SERVERS`: Broker Kafka (default: kafka:9092)
- `OPENSKY_CB_FAILURE_THRESHOLD`: Soglia fallimenti Circuit Breaker (default: 5)
- `OPENSKY_CB_RECOVERY_TIMEOUT`: Timeout recovery CB in secondi (default: 30)
- `NODE_NAME`: Nome nodo Kubernetes (auto-popolato via downward API)

**Prometheus**:
- `scrape_interval`: Intervallo di scraping (default: 10s)
- Target scraping: `user-manager-service:9999`, `data-collector-service:9999`

**Alert System**:
- `KAFKA_BOOTSTRAP_SERVERS`: Broker Kafka
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: Connessione MySQL data_db

**Alert Notifier**:
- `KAFKA_BOOTSTRAP_SERVERS`: Broker Kafka
- `SMTP_SERVER`: Server SMTP (default: mailhog)
- `SMTP_PORT`: Porta SMTP (default: 1025)

**Gateway**:
- Nessuna variabile, tutto configurato in `nginx.conf`

### Worker periodico

Il Data Collector include un thread che ogni 12 ore:
1. Legge tutti gli aeroporti di interesse da `user_airports`
2. Per ciascuno, recupera i voli delle ultime 12 ore da OpenSky
3. Salva i nuovi voli nella tabella `flights`

## � White-Box Monitoring con Prometheus

Sistema di monitoraggio delle performance dei microservizi.

### Architettura Monitoring

Prometheus effettua lo scraping delle metriche esposte dai microservizi:
- **User Manager**: espone metriche su porta `9999` all'endpoint `/metrics`
- **Data Collector**: espone metriche su porta `9999` all'endpoint `/metrics`
- **Scraping interval**: ogni 10 secondi
- **Storage**: Persistente su PVC Kubernetes

### Metriche Implementate

#### COUNTER (valori crescenti)

1. **`http_requests_total`**
   - Descrizione: Numero totale di richieste HTTP ricevute
   - Label: `service`, `node`, `endpoint`, `method` (solo data_collector)
   - Incrementata: `@app.before_request` per ogni richiesta
   - Esempio: `http_requests_total{service="user_manager",node="myapp-worker",endpoint="/users/register"}`

2. **`errors_total`**
   - Descrizione: Numero totale di errori HTTP 5xx
   - Label: `service`, `node`, `endpoint`, `method` (solo data_collector)
   - Incrementata: `@app.after_request` quando `status_code >= 500`
   - Esempio: `errors_total{service="data_collector",node="myapp-control-plane",endpoint="/user/airports"}`

#### GAUGE (valori che possono aumentare o diminuire)

1. **`response_time`**
   - Descrizione: Tempo di risposta dell'ultima richiesta in secondi
   - Label: `service`, `node`, `endpoint`, `method` (solo data_collector)
   - Aggiornata: `@app.after_request` con delta tra before e after
   - Esempio: `response_time{service="user_manager",node="myapp-worker",endpoint="/users/register"} = 0.045`

2. **`db_update_time`**
   - Descrizione: Tempo impiegato per operazioni di aggiornamento database
   - Label: `service`, `node`, `operation`
   - Aggiornata: Nelle funzioni che modificano il DB (INSERT, UPDATE, DELETE)
   - Operazioni tracciate:
     - User Manager: `registration`, `delete_user`
     - Data Collector: `add_user_airport`, `update_user_airport_thresholds`, `delete_user_airports`
   - Esempio: `db_update_time{service="data_collector",node="myapp-worker",operation="add_user_airport"} = 0.023`

3. **`opensky_fetch_time`** (solo Data Collector)
   - Descrizione: Tempo impiegato per recupero dati da OpenSky API
   - Label: `service`, `node`, `operation`
   - Aggiornata: Nelle chiamate a `opensky_client.refresh_flights_for_airport_logic`

### Label Obbligatorie

Tutte le metriche includono:
- **`service`**: Nome del microservizio (`user_manager` o `data_collector`)
- **`node`**: Nome del nodo Kubernetes che esegue il Pod (es. `myapp-control-plane`, `myapp-worker`)
  - Popolato automaticamente tramite Kubernetes Downward API:
    ```yaml
    env:
      - name: NODE_NAME
        valueFrom:
          fieldRef:
            fieldPath: spec.nodeName
    ```

### Implementazione Tecnica

#### File metrics.py (per ogni microservizio)
```python
from prometheus_client import start_http_server, Counter, Gauge
import os

SERVICE_NAME = "user_manager"  # o "data_collector"
NODE_NAME = os.getenv("NODE_NAME", "unknown")

REQUESTS_COUNT = Counter(
    'http_requests_total',
    'Total HTTP Requests',
    ['service', 'node', 'endpoint']
)

RESPONSE_TIME = Gauge(
    'response_time',
    'Response time in seconds',
    ['service', 'node', 'endpoint']
)

def init_monitoring():
    start_http_server(9999)  # Espone /metrics su porta 9999
```

#### Integrazione in app.py
```python
from metrics import init_monitoring, REQUESTS_COUNT, RESPONSE_TIME, ...

@app.before_request
def monitor_before_request():
    g.start_time = time.time()
    REQUESTS_COUNT.labels(service=SERVICE_NAME, node=NODE_NAME, endpoint=request.path).inc()

@app.after_request
def monitor_after_request(response):
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        RESPONSE_TIME.labels(service=SERVICE_NAME, node=NODE_NAME, endpoint=request.path).set(duration)
    return response

if __name__ == "__main__":
    init_monitoring()  # Avvia server metriche
    app.run(...)
```

### Accesso alle Metriche

```bash
# Prometheus UI
http://localhost:9090

# Query esempio
rate(http_requests_total{service="user_manager"}[5m])
avg(response_time{service="data_collector"})

# Metriche dirette dai microservizi (per debug)
kubectl port-forward svc/user-manager-service 9999:9999
curl http://localhost:9999/metrics
```

### Query Prometheus Utili

```promql
# Tasso di richieste al minuto per servizio
rate(http_requests_total[1m])

# Percentuale di errori
rate(errors_total[5m]) / rate(http_requests_total[5m]) * 100

# Response time medio per endpoint
avg by (endpoint) (response_time{service="user_manager"})

# Tempo medio aggiornamento DB per operazione
avg by (operation) (db_update_time)

# Richieste totali per nodo
sum by (node) (http_requests_total)
```

## �📝 Note Tecniche

### Idempotenza
Le operazioni di registrazione e cancellazione utente sono idempotenti grazie a:
- Header `requestID` obbligatorio
- Hash del contenuto della richiesta (SHA-256)
- Cache Redis con TTL (3 minuti)
- Chiave: `{operation}:{requestID}:{content_hash}`
- Meccanismo IN_PROGRESS per prevenire richieste concorrenti (409 Conflict)

### Circuit Breaker
Implementazione del pattern Circuit Breaker per le chiamate all'API OpenSky:
- **Stati**: CLOSED → OPEN → HALF_OPEN
- **Soglia fallimenti**: 5 errori consecutivi (configurabile)
- **Recovery timeout**: 30 secondi (configurabile)
- **Protezione**: Evita chiamate a servizi non disponibili
- **Endpoint debug**: `GET /debug/opensky-cb` per monitorare lo stato

### Sistema di Alert
**Flusso di elaborazione**:
1. Data Collector aggiorna i voli e invia messaggio Kafka a `to-alert-system`
2. Alert System riceve il messaggio e verifica le soglie configurate dagli utenti
3. Per ogni condizione soddisfatta (count >= high_value OR count <= low_value):
   - Genera una notifica con i dettagli
   - Invia messaggio Kafka a `to-notifier`
4. Alert Notifier riceve e compone email
5. Email inviata a MailHog (porta 8025 per visualizzazione)

**Gestione Offset Kafka**:
- Commit manuale dopo elaborazione riuscita
- In caso di errore, il messaggio viene riprocessato
- Consumer group separati per Alert System e Alert Notifier

### Codici ICAO
Gli aeroporti usano codici ICAO a 4 lettere (es. LICC = Catania, LIRF = Roma Fiumicino)

### Limitazioni OpenSky API
- Massimo 48 ore di intervallo per richiesta
- Rate limiting applicato
- Richiede autenticazione OAuth2
- Circuit Breaker attivo per gestire indisponibilità

## 🐛 Troubleshooting

**Problema**: Pod non si avviano
```bash
kubectl get pods --all-namespaces
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

**Problema**: Errori di connessione tra servizi
```bash
# Verifica i servizi
kubectl get services

# Verifica DNS interno
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup user-manager-service
```

**Problema**: Immagini non trovate
```bash
# Ricarica immagini nel cluster Kind
kind load docker-image user-manager:latest --name myapp
kind load docker-image data-collector:latest --name myapp
```

**Problema**: OpenSky API errori 401/403
- Verificare credenziali in `kubernetes/opensky_credentials.yaml` (Base64 encoded)
- Verificare che il secret sia stato applicato: `kubectl get secrets`
- Controllare rate limits dell'API

**Problema**: Prometheus non raccoglie metriche
```bash
# Verifica configurazione Prometheus
kubectl get configmap prometheus-config -o yaml

# Verifica target in Prometheus UI
http://localhost:9090/targets
```

**Problema**: Ingress non raggiungibile
```bash
# Verifica Ingress Controller
kubectl get pods -n ingress-nginx

# Verifica Ingress rules
kubectl get ingress
kubectl describe ingress <ingress-name>

# Verifica mapping porte Kind
docker ps | grep myapp
```
