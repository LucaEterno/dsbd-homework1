# DSBD Homework 1 & 2 - Flight Data Collection & Alert System

Sistema distribuito per la raccolta e gestione di dati sui voli tramite microservizi con sistema di allerta basato su messaggistica Kafka. Il sistema permette agli utenti di registrarsi, specificare aeroporti di interesse con soglie di monitoraggio personalizzate, ricevere informazioni sui voli e notifiche email automatiche quando le condizioni di allerta vengono soddisfatte.

## 📋 Indice

- [Architettura](#architettura)
- [Componenti](#componenti)
- [Prerequisiti](#prerequisiti)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)
- [API Endpoints](#api-endpoints)
- [Tecnologie](#tecnologie)
- [Struttura del Progetto](#struttura-del-progetto)

## 🏗️ Architettura

Il sistema è basato su un'architettura a microservizi con messaggistica asincrona:

```
                           ┌─────────────────┐
                           │  API Gateway    │  HTTPS/HTTP
                           │    (Nginx)      │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
         ┌──────────▼────────┐         ┌───────────▼──────────┐
         │  User Manager     │  gRPC   │  Data Collector      │
         │  (Flask + gRPC)   │◄────────┤  (Flask + Worker)    │
         └──────────┬────────┘         └───────────┬──────────┘
            │       │                       │      │      │
     ┌──────▼──┐ ┌──▼─────┐          ┌─────▼──┐   │      │
     │  MySQL  │ │ Redis  │          │ MySQL  │   │      │
     │  Users  │ │ Cache  │          │ Flights│   │      │
     └─────────┘ └────────┘          └────────┘   │      │
                                                   │      │
                                        ┌──────────▼──────▼─────────┐
                                        │   Kafka (KRaft Mode)      │
                                        │  Topic: to-alert-system   │
                                        └──────────┬────────────────┘
                                                   │
                                        ┌──────────▼────────────┐
                                        │   Alert System        │
                                        │  (Consumer + Logic)   │
                                        └──────────┬────────────┘
                                                   │
                                        ┌──────────▼────────────┐
                                        │   Kafka               │
                                        │  Topic: to-notifier   │
                                        └──────────┬────────────┘
                                                   │
                                        ┌──────────▼────────────┐
                                        │  Alert Notifier       │
                                        │  (Consumer + SMTP)    │
                                        └──────────┬────────────┘
                                                   │
                                        ┌──────────▼────────────┐
                                        │     MailHog           │
                                        │  (SMTP Test Server)   │
                                        └───────────────────────┘
```

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

- Docker & Docker Compose
- Credenziali OpenSky Network API (CLIENT_ID e CLIENT_SECRET)

## 🚀 Installazione

1. **Clone del repository**
```bash
git clone https://github.com/LucaEterno/dsbd-homework1.git
cd dsbd-homework1
```

2. **Configurazione credenziali OpenSky**

Modifica il file `docker-compose.yaml` e inserisci le tue credenziali:
```yaml
data_collector:
  environment:
    CLIENT_ID: "tuo-client-id"
    CLIENT_SECRET: "tuo-client-secret"
```

3. **Avvio dei servizi**
```bash
docker-compose up -d
```

4. **Verifica dello stato**
```bash
docker-compose ps
```

## 💡 Utilizzo
### Nei Documenti è presente un .json per un utilizzo guidato tramite POSTMAN
### Esempio: Workflow completo

```bash
# 1. Registrazione utente
curl -X POST http://localhost:5003/users/register \
  -H "Content-Type: application/json" \
  -H "requestID: unique-request-id-123" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "cf": "RSSMRA80A01H501U"
  }'

# 2. Aggiunta aeroporto di interesse con soglie di monitoraggio
curl -X POST http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "airport_code": "LICC",
    "high_value": 50,
    "low_value": 10
  }'

# 2b. Modifica soglie per un aeroporto esistente
curl -X PUT http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "airport_code": "LICC",
    "high_value": 60,
    "low_value": 15
  }'

# 3. Recupero lista aeroporti
curl "http://localhost:5002/user/airports?email=mario.rossi@example.com"

# 4. Refresh manuale dei voli per un aeroporto
curl -X POST http://localhost:5002/airport/LICC/refresh-flights \
  -H "Content-Type: application/json" \
  -d '{
    "hours": 12,
    "direction": "both"
  }'

# 5. Visualizza tutti i voli per gli aeroporti dell'utente
curl "http://localhost:5002/user/flights?email=mario.rossi@example.com"

# 6. Ultimo volo per un aeroporto
curl "http://localhost:5002/user/flights/last?email=mario.rossi@example.com&airport_code=LICC"

# 7. Media voli giornalieri
curl "http://localhost:5002/user/flights/average?email=mario.rossi@example.com&airport_code=LICC&days=7"

# 8. Cancellazione utente
curl -X DELETE http://localhost:5003/users/delete \
  -H "Content-Type: application/json" \
  -H "requestID: unique-request-id-456" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword"
  }'
```

## 📡 API Endpoints

### User Manager (porta 5003)

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

### Data Collector (porta 5002)

**Nota**: Gli endpoint sono accessibili tramite API Gateway su:
- HTTP: `http://localhost:8080/api/data/`
- HTTPS: `https://localhost:8443/api/data/`

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
**[NUOVO HW2]** Modifica le soglie di monitoraggio per un aeroporto esistente

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
├── docs/
│   ├── API.md                    # Documentazione API completa
│   └── DSBD-HW2.postman_collection.json  # Collection Postman
├── docker-compose.yaml           # Orchestrazione servizi (11 container)
├── .gitignore
├── LICENSE
└── README.md
```

## ⚙️ Configurazione

### Variabili d'ambiente

Tutte le variabili sono configurate in `docker-compose.yaml`:

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

## 📝 Note Tecniche

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

**Problema**: Container non si avviano
```bash
docker-compose logs [service_name]
docker-compose down -v  # Rimuovi volumi e ricrea
docker-compose up -d
```

**Problema**: Errori di connessione MySQL
- Verificare healthcheck con `docker-compose ps`
- Aumentare `retries` in `docker-compose.yaml`

**Problema**: OpenSky API errori 401/403
- Verificare credenziali CLIENT_ID e CLIENT_SECRET
- Controllare rate limits dell'API
