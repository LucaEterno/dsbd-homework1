# API Documentation - DSBD Homework 1 & 2

Documentazione completa delle API REST e gRPC del sistema con sistema di alert.

## Indice
- [API Gateway](#api-gateway)
- [User Manager REST API](#user-manager-rest-api)
- [Data Collector REST API](#data-collector-rest-api)
- [User Manager gRPC API](#user-manager-grpc-api)
- [Sistema di Alert](#sistema-di-alert)
- [Modelli di Errore](#modelli-di-errore)

---

## API Gateway

**Nuova funzionalità Homework 2**: Tutti gli endpoint sono accessibili tramite Nginx API Gateway.

### URL di accesso

**HTTP** (porta 8080):
- User Manager: `http://localhost:8080/api/users/`
- Data Collector: `http://localhost:8080/api/data/`

**HTTPS** (porta 8443) - Certificati self-signed:
- User Manager: `https://localhost:8443/api/users/`
- Data Collector: `https://localhost:8443/api/data/`

### Healthcheck
```bash
curl http://localhost:8080/health
# Risposta: ok
```

**Nota**: Gli esempi seguenti usano le porte dirette dei servizi per semplicità, ma in produzione si dovrebbe usare il Gateway.

---

## User Manager REST API

Base URL: `http://localhost:5003`

### POST /users/register

Registra un nuovo utente nel sistema. **Operazione idempotente**.

#### Headers
```
Content-Type: application/json
requestID: <unique-request-identifier>  (OBBLIGATORIO)
```

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)",
  "cf": "string (required)"
}
```

#### Responses

**201 Created** - Utente creato con successo
```json
{
  "message": "Utente registrato con successo",
  "user": {
    "email": "mario.rossi@example.com",
    "cf": "RSSMRA80A01H501U"
  }
}
```

**409 Conflict** - Email già registrata
```json
{
  "error": "Email già registrata"
}
```

**400 Bad Request** - Dati mancanti
```json
{
  "error": "Campi mancanti",
  "missing_fields": ["email", "password"]
}
```

**400 Bad Request** - requestID mancante
```json
{
  "error": "Header obbligatorio mancante: requestID",
  "message": "La richiesta non verrà elaborata."
}
```

#### Esempio
```bash
curl -X POST http://localhost:5003/users/register \
  -H "Content-Type: application/json" \
  -H "requestID: req-001-20251130" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123",
    "cf": "RSSMRA80A01H501U"
  }'
```

---

### DELETE /users/delete

Cancella un utente esistente. **Operazione idempotente**.

Nota: La cancellazione dell'utente comporta automaticamente la rimozione di tutte le sue associazioni aeroporto-utente nel Data Collector.

#### Headers
```
Content-Type: application/json
requestID: <unique-request-identifier>  (OBBLIGATORIO)
```

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)"
}
```

#### Responses

**200 OK** - Utente cancellato
```json
{
  "success": true,
  "message": "Utente cancellato con successo",
  "email": "mario.rossi@example.com"
}
```

**401 Unauthorized** - Credenziali errate
```json
{
  "error": "Email o password non corretta"
}
```

**400 Bad Request** - requestID mancante
```json
{
  "error": "Header obbligatorio mancante: requestID",
  "message": "La richiesta non verrà elaborata."
}
```

#### Esempio
```bash
curl -X DELETE http://localhost:5003/users/delete \
  -H "Content-Type: application/json" \
  -H "requestID: req-002-20251130" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123"
  }'
```

---

## Data Collector REST API

Base URL: `http://localhost:5002`

### POST /user/airports

Aggiunge un aeroporto di interesse per un utente con soglie di monitoraggio opzionali.

**Novità Homework 2**: Parametri `high_value` e `low_value` per configurare alert automatici.

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)",
  "airport_code": "string (required, ICAO 4-letter code)",
  "high_value": "integer (optional)",
  "low_value": "integer (optional)"
}
```

**Nota sulle soglie**:
- `high_value`: Soglia massima. Quando i voli >= high_value, viene inviata una notifica
- `low_value`: Soglia minima. Quando i voli <= low_value, viene inviata una notifica
- Entrambe opzionali, possono essere configurate successivamente con PUT

#### Responses

**201 Created** - Aeroporto aggiunto
```json
{
  "success": true,
  "message": "airport added for user",
  "email": "mario.rossi@example.com",
  "airport_code": "LICC"
}
```

**200 OK** - Aeroporto già registrato
```json
{
  "success": false,
  "message": "airport already registered for this user"
}
```

**401 Unauthorized** - Credenziali non valide
```json
{
  "success": false,
  "message": "invalid credentials"
}
```

**400 Bad Request** - Formato ICAO invalido
```json
{
  "error": "Invalid airport_code format (must be 4 letters, ICAO code)"
}
```

**404 Not Found** - Utente non esiste
```json
{
  "error": "User does not exist"
}
```

#### Esempio
```bash
curl -X POST http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123",
    "airport_code": "LICC",
    "high_value": 50,
    "low_value": 10
  }'
```

---

### PUT /user/airports

**[NUOVO - Homework 2]** Modifica le soglie di monitoraggio per un aeroporto già associato all'utente.

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)",
  "airport_code": "string (required)",
  "high_value": "integer (optional)",
  "low_value": "integer (optional)"
}
```

**Vincoli**:
- Almeno uno tra `high_value` e `low_value` deve essere fornito
- Se entrambi presenti: `high_value` deve essere > `low_value`
- L'associazione utente-aeroporto deve già esistere

#### Responses

**200 OK** - Soglie aggiornate
```json
{
  "success": true,
  "message": "thresholds updated",
  "email": "mario.rossi@example.com",
  "airport_code": "LICC",
  "high_value": 60,
  "low_value": 20
}
```

**401 Unauthorized** - Credenziali non valide
```json
{
  "success": false,
  "message": "invalid credentials"
}
```

**404 Not Found** - Associazione non esistente
```json
{
  "success": false,
  "message": "user_airport association does not exist"
}
```

**400 Bad Request** - Parametri invalidi
```json
{
  "error": "high_value must be strictly greater than low_value"
}
```

#### Esempio
```bash
curl -X PUT http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123",
    "airport_code": "LICC",
    "high_value": 60,
    "low_value": 20
  }'
```

---

### GET /user/airports

**[NUOVO - Homework 2]** Modifica le soglie di monitoraggio per un aeroporto già associato all'utente.

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)",
  "airport_code": "string (required)",
  "high_value": "integer (optional)",
  "low_value": "integer (optional)"
}
```

**Vincoli**:
- Almeno uno tra `high_value` e `low_value` deve essere fornito
- Se entrambi presenti: `high_value` deve essere > `low_value`
- L'associazione utente-aeroporto deve già esistere

#### Responses

**200 OK** - Soglie aggiornate
```json
{
  "success": true,
  "message": "thresholds updated",
  "email": "mario.rossi@example.com",
  "airport_code": "LICC",
  "high_value": 60,
  "low_value": 20
}
```

**401 Unauthorized** - Credenziali non valide
```json
{
  "success": false,
  "message": "invalid credentials"
}
```

**404 Not Found** - Associazione non esistente
```json
{
  "success": false,
  "message": "user_airport association does not exist"
}
```

**400 Bad Request** - Parametri invalidi
```json
{
  "error": "high_value must be strictly greater than low_value"
}
```

#### Esempio
```bash
curl -X PUT http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123",
    "airport_code": "LICC",
    "high_value": 60,
    "low_value": 20
  }'
```

---

### GET /user/airports

Restituisce la lista degli aeroporti di interesse per un utente con le soglie configurate.

#### Query Parameters
- `email` (required): Email dell'utente

#### Responses

**200 OK**
```json
{
  "email": "mario.rossi@example.com",
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
    },
    {
      "airport_code": "LIMJ",
      "high_value": 100,
      "low_value": null
    }
  ],
  "count": 3
}
```

**Nota**: `high_value` e `low_value` possono essere `null` se non configurati.

**404 Not Found** - Utente non esiste
```json
{
  "error": "User does not exist"
}
```

#### Esempio
```bash
curl "http://localhost:5002/user/airports?email=mario.rossi@example.com"
```

---

### DELETE /user/airports

Rimuove associazioni utente-aeroporto.

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)",
  "airport_code": "string (optional)"
}
```

**Nota**: Se `airport_code` non è fornito, vengono rimosse TUTTE le associazioni dell'utente.

#### Responses

**200 OK**
```json
{
  "success": true,
  "deleted": 1,
  "email": "mario.rossi@example.com",
  "airport_code": "LICC"
}
```

**401 Unauthorized** - Credenziali non valide
```json
{
  "success": false,
  "message": "invalid credentials"
}
```

#### Esempi
```bash
# Rimuove un aeroporto specifico
curl -X DELETE http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123",
    "airport_code": "LICC"
  }'

# Rimuove tutti gli aeroporti dell'utente
curl -X DELETE http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "securepass123"
  }'
```

---

### GET /user/flights

Restituisce tutti i voli registrati per gli aeroporti di interesse di un utente.

#### Query Parameters
- `email` (required): Email dell'utente

#### Responses

**200 OK**
```json
{
  "email": "mario.rossi@example.com",
  "airports": ["LICC", "LIRF"],
  "flights": [
    {
      "airport_code": "LICC",
      "direction": "arrival",
      "flight_icao": "abc123",
      "callsign": "AZ123",
      "flight_time": "2025-11-30T10:30:00"
    },
    {
      "airport_code": "LIRF",
      "direction": "departure",
      "flight_icao": "def456",
      "callsign": "FR456",
      "flight_time": "2025-11-30T11:15:00"
    }
  ],
  "count": 2
}
```

**404 Not Found** - Utente non esiste
```json
{
  "error": "User does not exist"
}
```

#### Esempio
```bash
curl "http://localhost:5002/user/flights?email=mario.rossi@example.com"
```

---

### GET /user/flights/last

Restituisce l'ultimo volo in arrivo e l'ultimo in partenza per un aeroporto specifico.

#### Query Parameters
- `email` (required): Email dell'utente
- `airport_code` (required): Codice ICAO dell'aeroporto

#### Responses

**200 OK**
```json
{
  "email": "mario.rossi@example.com",
  "airport_code": "LICC",
  "last_arrival": {
    "airport_code": "LICC",
    "direction": "arrival",
    "flight_icao": "abc123",
    "callsign": "AZ123",
    "flight_time": "2025-11-30T10:30:00"
  },
  "last_departure": {
    "airport_code": "LICC",
    "direction": "departure",
    "flight_icao": "def456",
    "callsign": "FR789",
    "flight_time": "2025-11-30T12:45:00"
  }
}
```

**Nota**: `last_arrival` o `last_departure` possono essere `null` se non ci sono voli.

**403 Forbidden** - Aeroporto non negli interessi dell'utente
```json
{
  "error": "Airport is not registered as an interest for this user"
}
```

**404 Not Found** - Utente non esiste
```json
{
  "error": "User does not exist"
}
```

#### Esempio
```bash
curl "http://localhost:5002/user/flights/last?email=mario.rossi@example.com&airport_code=LICC"
```

---

### GET /user/flights/average

Calcola la media di voli giornalieri in arrivo e partenza per un aeroporto negli ultimi X giorni.

#### Query Parameters
- `email` (required): Email dell'utente
- `airport_code` (required): Codice ICAO dell'aeroporto
- `days` (required): Numero di giorni (intero positivo)

#### Responses

**200 OK**
```json
{
  "email": "mario.rossi@example.com",
  "airport_code": "LICC",
  "days": 7,
  "period_start": "2025-11-23T00:00:00",
  "average_flights": {
    "arrival_per_day": 12.57,
    "departure_per_day": 11.86,
    "total_flights_in_period": {
      "arrivals": 88,
      "departures": 83
    }
  }
}
```

**400 Bad Request** - days non valido
```json
{
  "error": "'days' must be a positive integer"
}
```

**403 Forbidden** - Aeroporto non negli interessi dell'utente
```json
{
  "error": "Airport is not registered as an interest for this user"
}
```

#### Esempio
```bash
curl "http://localhost:5002/user/flights/average?email=mario.rossi@example.com&airport_code=LICC&days=7"
```

---

### POST /airport/{airport_code}/refresh-flights

Aggiorna manualmente i dati sui voli per un aeroporto specifico.

#### Path Parameters
- `airport_code`: Codice ICAO dell'aeroporto

#### Request Body
```json
{
  "hours": "integer (optional, default: 24, max: 48)",
  "direction": "string (optional, values: 'arrival', 'departure', 'both', default: 'both')"
}
```

#### Responses

**200 OK**
```json
{
  "airport_code": "LICC",
  "hours": 12,
  "inserted": {
    "arrival": 45,
    "departure": 42
  }
}
```

**400 Bad Request** - Parametri invalidi
```json
{
  "error": "Invalid 'hours' value"
}
```

**502 Bad Gateway** - Errore OpenSky API
```json
{
  "error": "OpenSky error 401"
}
```

#### Esempio
```bash
curl -X POST http://localhost:5002/airport/LICC/refresh-flights \
  -H "Content-Type: application/json" \
  -d '{
    "hours": 12,
    "direction": "both"
  }'
```

---

### GET /debug/opensky-cb

**[NUOVO - Homework 2]** Endpoint di debug per monitorare lo stato del Circuit Breaker OpenSky API.

#### Responses

**200 OK**
```json
{
  "state": "CLOSED",
  "failure_count": 0,
  "failure_threshold": 5,
  "recovery_timeout": 30,
  "last_failure_time": null
}
```

**Stati possibili**:
- `CLOSED`: Operazioni normali, API calls permesse
- `OPEN`: Circuit aperto dopo fallimenti, calls bloccate
- `HALF_OPEN`: Tentativo di recovery in corso

#### Esempio
```bash
curl http://localhost:5002/debug/opensky-cb
```

---

## Sistema di Alert

**[NUOVO - Homework 2]** Sistema automatico di monitoraggio e notifica basato su Kafka.

### Architettura del Sistema

```
Data Collector → Kafka (to-alert-system) → Alert System → Kafka (to-notifier) → Alert Notifier → Email
```

### Flusso di Elaborazione

1. **Trigger**: Il Data Collector aggiorna i dati sui voli (manualmente o tramite worker periodico)
2. **Notifica Kafka**: Viene inviato un messaggio al topic `to-alert-system` con:
   ```json
   {
     "timestamp": "2025-12-19T10:30:00",
     "airport_data": {
       "airport_code": "LICC",
       "flight_count": 55,
       "updated_at": "2025-12-19T10:30:00"
     }
   }
   ```

3. **Alert System**: 
   - Consuma il messaggio dal topic
   - Query al database per recuperare le soglie degli utenti per quell'aeroporto
   - Verifica condizioni:
     - `flight_count >= high_value` → Genera alert "SUPERA SOGLIA MAX"
     - `flight_count <= low_value` → Genera alert "SOTTO SOGLIA MIN"
   - Per ogni condizione soddisfatta, produce un messaggio a `to-notifier`

4. **Alert Notifier**:
   - Consuma i messaggi di alert
   - Compone l'email:
     - **Subject**: Codice aeroporto (es. "LICC")
     - **To**: Email dell'utente
     - **From**: `alert-system@your-app.com`
     - **Body**: Descrizione della condizione
   - Invia email tramite SMTP (MailHog in development)

### Struttura Messaggio Alert

```json
{
  "user_email": "mario.rossi@example.com",
  "airport_code": "LICC",
  "current_count": 55,
  "condition": "SUPERA SOGLIA MAX (Voli: 55 >= Max: 50)",
  "threshold_max": 50,
  "threshold_min": 10,
  "timestamp": "2025-12-19T10:30:15"
}
```

### MailHog - Visualizzazione Email

**URL Web UI**: `http://localhost:8025`

Tutte le email inviate dal sistema vengono catturate da MailHog e sono visualizzabili tramite interfaccia web.

**Esempio Email Ricevuta**:
```
From: alert-system@your-app.com
To: mario.rossi@example.com
Subject: LICC

SUPERA SOGLIA MAX (Voli: 55 >= Max: 50)
```

### Configurazione Alert per Utente

#### Esempio Completo

```bash
# 1. Registrazione utente
curl -X POST http://localhost:5003/users/register \
  -H "Content-Type: application/json" \
  -H "requestID: req-001" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypass",
    "cf": "RSSMRA80A01H501U"
  }'

# 2. Aggiungi aeroporto con soglie
curl -X POST http://localhost:5002/user/airports \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mario.rossi@example.com",
    "password": "mypass",
    "airport_code": "LICC",
    "high_value": 50,
    "low_value": 10
  }'

# 3. Forza aggiornamento voli (trigger alert se soglie superate)
curl -X POST http://localhost:5002/airport/LICC/refresh-flights \
  -H "Content-Type: application/json" \
  -d '{
    "hours": 12,
    "direction": "both"
  }'

# 4. Controlla email su MailHog: http://localhost:8025
```

### Kafka Topics

#### Topic: `to-alert-system`
- **Producer**: Data Collector
- **Consumer**: Alert System (group: `group1`)
- **Schema**: Notifiche di aggiornamento dati voli

#### Topic: `to-notifier`
- **Producer**: Alert System
- **Consumer**: Alert Notifier (group: `group2`)
- **Schema**: Alert da inviare via email

### Gestione Errori

- **Commit Manuale**: Gli offset Kafka vengono committati solo dopo elaborazione riuscita
- **Retry**: In caso di errore, il messaggio viene riprocessato
- **Dead Letter**: Non implementato (i messaggi errati vengono skippati con log)

### Circuit Breaker OpenSky API

**Protezione per chiamate all'API esterna.**

#### Stati del Circuit Breaker

- **CLOSED**: Operazioni normali, chiamate API permesse
- **OPEN**: Dopo 5 fallimenti consecutivi, blocca le chiamate per 30 secondi
- **HALF_OPEN**: Dopo il timeout, tenta una chiamata di test
  - Se successo → ritorna CLOSED
  - Se fallisce → ritorna OPEN

#### Configurazione

Parametri configurabili via environment variables:
- `OPENSKY_CB_FAILURE_THRESHOLD`: Numero fallimenti prima di aprire (default: 5)
- `OPENSKY_CB_RECOVERY_TIMEOUT`: Secondi prima di tentare recovery (default: 30)

---

## User Manager gRPC API

Host: `localhost:50051`

### CheckUserExists

Verifica se un utente esiste tramite email.

#### Request
```protobuf
message CheckUserExistsRequest {
  string email = 1;
}
```

#### Response
```protobuf
message CheckUserExistsResponse {
  bool exists = 1;
}
```

#### Esempio (Python)
```python
import grpc
import user_manager_pb2
import user_manager_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = user_manager_pb2_grpc.UserManagerStub(channel)

request = user_manager_pb2.CheckUserExistsRequest(
    email="mario.rossi@example.com"
)
response = stub.CheckUserExists(request)

print(f"User exists: {response.exists}")
```

---

### CheckUserCredentials

Verifica che email e password siano credenziali valide.

#### Request
```protobuf
message CheckUserCredentialsRequest {
  string email = 1;
  string password = 2;
}
```

#### Response
```protobuf
message CheckUserCredentialsResponse {
  bool valid = 1;
}
```

#### Esempio (Python)
```python
import grpc
import user_manager_pb2
import user_manager_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = user_manager_pb2_grpc.UserManagerStub(channel)

request = user_manager_pb2.CheckUserCredentialsRequest(
    email="mario.rossi@example.com",
    password="securepass123"
)
response = stub.CheckUserCredentials(request)

print(f"Credentials valid: {response.valid}")
```

---

## Modelli di Errore

### Errori Comuni

#### 400 Bad Request
Richiesta malformata o parametri mancanti/invalidi.

#### 401 Unauthorized
Credenziali errate o mancanti.

#### 403 Forbidden
Operazione non permessa (es. accesso a risorsa non associata all'utente).

#### 404 Not Found
Risorsa non trovata (es. utente inesistente).

#### 409 Conflict
Conflitto con lo stato corrente (es. email duplicata).

#### 500 Internal Server Error
Errore interno del server (es. errore database).

#### 502 Bad Gateway
Errore nella comunicazione con servizi esterni (es. OpenSky API).

#### 503 Service Unavailable
Servizio temporaneamente non disponibile (es. database non connesso).

---

## Note sull'Idempotenza

Le operazioni `POST /users/register` e `DELETE /users/delete` sono idempotent tramite:

1. **Header requestID**: Identificatore univoco della richiesta (obbligatorio)
2. **Content Hash**: Hash SHA-256 del body della richiesta
3. **Redis Cache**: Memorizzazione della risposta con TTL di 3 minuti
4. **Meccanismo IN_PROGRESS**: Prevenzione richieste concorrenti

**Chiave Redis**: `{operation}:{requestID}:{content_hash}`

### Flusso Idempotenza

1. **Prima richiesta**:
   - Sistema verifica se chiave esiste in Redis
   - Se non esiste, crea chiave con valore `"IN_PROGRESS"` e TTL 3 minuti
   - Elabora la richiesta
   - Salva la risposta in Redis con la stessa chiave
   - Restituisce la risposta

2. **Richiesta duplicata (stesso requestID e body)**:
   - Sistema trova la chiave in Redis
   - Se valore è `"IN_PROGRESS"` → Ritorna 409 Conflict (richiesta in elaborazione)
   - Se valore è una risposta salvata → Ritorna la risposta cached (200/201)

3. **Dopo TTL (3 minuti)**:
   - Chiave scade automaticamente
   - Richiesta viene trattata come nuova

### Esempio Comportamento

```bash
# Prima richiesta - Successo
curl -X POST http://localhost:5003/users/register \
  -H "requestID: req-123" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pwd","cf":"CF123"}'
# Risposta: 201 Created

# Seconda richiesta (stesso requestID e body) entro 3 minuti
curl -X POST http://localhost:5003/users/register \
  -H "requestID: req-123" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pwd","cf":"CF123"}'
# Risposta: 201 Created (dalla cache, operazione non ripetuta)

# Terza richiesta (stesso requestID ma body diverso)
curl -X POST http://localhost:5003/users/register \
  -H "requestID: req-123" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"different","cf":"CF123"}'
# Risposta: 400/409 (nuovo hash, quindi trattata come nuova richiesta)
```

---

## Codici Aeroporto ICAO

Esempi di codici ICAO italiani:
- `LICC` - Catania Fontanarossa
- `LIRF` - Roma Fiumicino
- `LIMJ` - Genova Cristoforo Colombo
- `LIML` - Milano Linate
- `LIMC` - Milano Malpensa
- `LIPE` - Bologna Guglielmo Marconi
- `LIPZ` - Venezia Marco Polo
- `LIRN` - Napoli Capodichino
- `LICJ` - Palermo Falcone-Borsellino
- `LIBD` - Bari Karol Wojtyła

Per la lista completa: [ICAO Airport Codes](https://en.wikipedia.org/wiki/ICAO_airport_code)
