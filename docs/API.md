# API Documentation - DSBD Homework 1

Documentazione completa delle API REST e gRPC del sistema.

## Indice
- [User Manager REST API](#user-manager-rest-api)
- [Data Collector REST API](#data-collector-rest-api)
- [User Manager gRPC API](#user-manager-grpc-api)
- [Modelli di Errore](#modelli-di-errore)

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

Aggiunge un aeroporto di interesse per un utente.

#### Request Body
```json
{
  "email": "string (required)",
  "password": "string (required)",
  "airport_code": "string (required, ICAO 4-letter code)"
}
```

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
    "airport_code": "LICC"
  }'
```

---

### GET /user/airports

Restituisce la lista degli aeroporti di interesse per un utente.

#### Query Parameters
- `email` (required): Email dell'utente

#### Responses

**200 OK**
```json
{
  "email": "mario.rossi@example.com",
  "airports": ["LICC", "LIRF", "LIMJ"],
  "count": 3
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

Le operazioni `POST /users/register` e `DELETE /users/delete` sono idempotenti tramite:

1. **Header requestID**: Identificatore univoco della richiesta
2. **Content Hash**: Hash SHA-256 del body della richiesta
3. **Redis Cache**: Memorizzazione della risposta con TTL di 24 ore

**Chiave Redis**: `{operation}:{requestID}:{content_hash}`

Se una richiesta con lo stesso `requestID` e contenuto viene ripetuta entro 24 ore, viene restituita la risposta cached invece di ri-eseguire l'operazione.

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
