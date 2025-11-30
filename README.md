# DSBD Homework 1 - Flight Data Collection System

Sistema distribuito per la raccolta e gestione di dati sui voli tramite microservizi. Il sistema permette agli utenti di registrarsi, specificare aeroporti di interesse e ricevere informazioni sui voli in arrivo e partenza.

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

Il sistema è composto da due microservizi principali che comunicano tra loro:

```
┌─────────────────┐         gRPC          ┌──────────────────┐
│  User Manager   │◄──────────────────────┤ Data Collector   │
│   (Flask + gRPC)│                        │     (Flask)      │
└────────┬────────┘                        └────────┬─────────┘
         │                                          │
         │                                          │
    ┌────▼─────┐                              ┌────▼─────┐
    │  MySQL   │                              │  MySQL   │
    │  Users   │                              │  Flights │
    └──────────┘                              └──────────┘
         │
         │
    ┌────▼─────┐
    │  Redis   │
    │  Cache   │
    └──────────┘
```

### Caratteristiche principali:
- **Idempotenza**: Le operazioni di scrittura sono idempotenti grazie a Redis
- **Comunicazione gRPC**: User Manager e Data Collector comunicano tramite gRPC
- **Worker periodico**: Aggiornamento automatico dei dati sui voli ogni 12 ore
- **Persistenza**: Database MySQL separati per utenti e dati sui voli

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
- Aggiunta/rimozione aeroporti di interesse per utente
- Recupero voli da OpenSky Network API (OAuth2)
- Worker periodico per aggiornamento automatico dati
- Query avanzate (ultimo volo, media voli giornalieri)

**Tecnologie**: Flask, gRPC client, MySQL, OpenSky API

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

# 2. Aggiunta aeroporto di interesse
curl -X POST http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypassword",
    "airport_code": "LICC"
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

#### POST /user/airports
Aggiunge un aeroporto di interesse per l'utente

**Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "airport_code": "LICC"
}
```

**Risposte**:
- `201`: Aeroporto aggiunto
- `200`: Aeroporto già registrato
- `401`: Credenziali errate
- `400`: Formato ICAO invalido

#### GET /user/airports
Ottiene la lista degli aeroporti di interesse

**Query params**: `email`

**Risposta**:
```json
{
  "email": "user@example.com",
  "airports": ["LICC", "LIRF"],
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

- **Python 3.11**: Linguaggio principale
- **Flask**: Framework web per REST API
- **gRPC**: Comunicazione inter-servizi
- **MySQL 8.0**: Database relazionale
- **Redis 7**: Cache per idempotenza
- **Docker & Docker Compose**: Containerizzazione e orchestrazione
- **OpenSky Network API**: Sorgente dati sui voli

### Librerie Python principali:
- `flask`: Web framework
- `grpcio`: gRPC runtime
- `mysql-connector-python`: Driver MySQL
- `redis`: Client Redis
- `requests`: HTTP client per OpenSky API

## 📁 Struttura del Progetto

```
homework1/
├── data_collector/
│   ├── app.py                    # Flask app principale
│   ├── collector_worker.py       # Worker thread per aggiornamenti periodici
│   ├── flight_services.py        # Logica di business per voli
│   ├── opensky_auth.py           # Autenticazione OAuth2 OpenSky
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
├── docker-compose.yaml           # Orchestrazione servizi
├── .gitignore
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

### Worker periodico

Il Data Collector include un thread che ogni 12 ore:
1. Legge tutti gli aeroporti di interesse da `user_airports`
2. Per ciascuno, recupera i voli delle ultime 12 ore da OpenSky
3. Salva i nuovi voli nella tabella `flights`

## 📝 Note Tecniche

### Idempotenza
Le operazioni di registrazione e cancellazione utente sono idempotenti grazie a:
- Header `requestID` obbligatorio
- Hash del contenuto della richiesta
- Cache Redis con TTL (24 ore)
- Chiave: `{operation}:{requestID}:{content_hash}`

### Codici ICAO
Gli aeroporti usano codici ICAO a 4 lettere (es. LIMC = Milano, EGLL = Londra)

### Limitazioni OpenSky API
- Massimo 2 giorni di intervallo per richiesta
- Rate limiting applicato
- Richiede autenticazione OAuth2

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
