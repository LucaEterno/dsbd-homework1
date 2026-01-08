import os
import time
import requests
from mysql.connector import Error
import time
from datetime import datetime, timezone
from opensky_auth import get_opensky_token
from circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
import requests

from metrics import SERVICE_NAME, NODE_NAME, DB_UPDATE_TIME, OPENSKY_FETCH_TIME

# Configura il Circuit Breaker per le chiamate OpenSky
failure_threshold = int(os.getenv("OPENSKY_CB_FAILURE_THRESHOLD", "5"))
recovery_timeout = int(os.getenv("OPENSKY_CB_RECOVERY_TIMEOUT", "30"))

opensky_cb = CircuitBreaker(
    failure_threshold=failure_threshold,
    recovery_timeout=recovery_timeout,
    expected_exception=requests.exceptions.RequestException
)


def fetch_flights_from_opensky(airport_code, direction, begin, end):
    """
    Recupera i voli da OpenSky per un certo aeroporto e intervallo temporale,
    usando un token OAuth2 (Bearer) con caching.
    """

    token = get_opensky_token()
    if not token:
        raise RuntimeError("Impossibile ottenere il token OpenSky (controlla CLIENT_ID/CLIENT_SECRET)")

    base_url = "https://opensky-network.org/api"
    endpoint = f"/flights/{direction}"
    url = base_url + endpoint

    params = {
        "airport": airport_code,
        "begin": begin,
        "end": end,
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"[OpenSky] GET {url} params={params}, direction={direction} (con Bearer token)")

    # --- chiamata protetta da Circuit Breaker ---
    def _do_request():
        resp = requests.get(url, params=params, headers=headers, timeout=30)

        # 200 ok
        if resp.status_code == 200:
            return resp.json()

        # 404 = nessun volo (non è un "fallimento" della rete)
        if resp.status_code == 404:
            return []

        # per tutti gli altri status -> lo consideriamo errore
        # convertiamo in HTTPError (subclass di RequestException) così il CB lo conta come failure
        resp.raise_for_status()

    fetch_time = time.time()
    try:
        flights = opensky_cb.call(_do_request)

        # Registrazione durata del fetch da OpenSky per monitoraggio
        duration = time.time() - fetch_time
        OPENSKY_FETCH_TIME.labels(service=SERVICE_NAME, node=NODE_NAME, operation=f"fetch flights for {airport_code} with direction {direction}").set(duration)
    
    except CircuitBreakerOpenException:
        # Registrazione durata del fetch da OpenSky per monitoraggio
        duration = time.time() - fetch_time
        OPENSKY_FETCH_TIME.labels(service=SERVICE_NAME, node=NODE_NAME, operation=f"fetch flights for {airport_code} with direction {direction}: FAILED").set(duration)

        # rilanciamo, così lo gestisce il livello sopra (route/logic) con 503
        print("[OpenSky] Circuit OPEN: richiesta negata dal Circuit Breaker")
        raise

    except requests.exceptions.RequestException as e:
        # Registrazione durata del fetch da OpenSky per monitoraggio
        duration = time.time() - fetch_time
        OPENSKY_FETCH_TIME.labels(service=SERVICE_NAME, node=NODE_NAME, operation=f"fetch flights for {airport_code} with direction {direction}: FAILED").set(duration)

        # errore rete/HTTP -> viene già conteggiato dal CB
        print(f"[OpenSky] RequestException: {e}")
        raise RuntimeError(f"OpenSky request failed: {e}")

    print(f"[OpenSky] {len(flights)} voli ricevuti per {airport_code} ({direction})")
    return flights


def store_flights_in_db(conn, airport_code, direction, flights):
    """
    Salva una lista di voli nella tabella flights di flightdata_db.
    conn: Connessione attiva al DB (proveniente da Flask g.db).
    flights: lista di dict così come arriva da OpenSky.
    Usiamo:
      - flight_icao  <- icao24
      - callsign    <- callsign
      - flight_time <- lastSeen
    """

    if not flights:
        return 0

    if conn is None:
        print("Connessione al DB non fornita per salvare i voli")
        return 0

    inserted = 0

    start_db = time.time()
    try:
        cursor = conn.cursor()
        sql = """
            INSERT IGNORE INTO flights (airport_code, direction, flight_icao, callsign, flight_time)
            VALUES (%s, %s, %s, %s, %s)
        """

        for f in flights:
            icao24 = f.get("icao24") # identificativo univoco del velivolo
            callsign = f.get("callsign") # identificativo del volo (es. "DLH400")
            last_seen = f.get("lastSeen") # UNIX timestamp dell'ultimo avvistamento

            if last_seen is None:
                continue

            # UNIX timestamp → datetime UTC
            dt = datetime.fromtimestamp(last_seen, tz=timezone.utc) # datetime con tzinfo=UTC
            dt_naive = dt.replace(tzinfo=None) # rimuovo tzinfo per inserirlo in MySQL DATETIME

            params = (airport_code, direction, icao24, callsign, dt_naive)
            cursor.execute(sql, params)
            inserted += cursor.rowcount
        conn.commit()

        # Registrazione durata dell'aggiornamento del db per monitoraggio
        duration = time.time() - start_db
        DB_UPDATE_TIME.labels(service=SERVICE_NAME, node=NODE_NAME, operation=f"store flights for {airport_code} with direction {direction} in db").set(duration)

        print(f"[DataCollector] {inserted} Voli effettivamente inseriti in DB per {airport_code} ({direction})")
        return inserted

    except Error as e:
        # Registrazione durata dell'aggiornamento del db per monitoraggio
        duration = time.time() - start_db
        DB_UPDATE_TIME.labels(service=SERVICE_NAME, node=NODE_NAME, operation=f"store flights for {airport_code} with direction {direction} in db: FAILED").set(duration)

        print(f"Errore DB in store_flights_in_db: {e}")
        return -1

    finally:
        # Chiude solo il cursore, NON la connessione (che è gestita da Flask g.db)
        if 'cursor' in locals() and cursor:
            cursor.close()


def refresh_flights_for_airport_logic(conn, airport_code, hours, direction):
    """
    Logica applicativa per il refresh dei voli di un aeroporto.
    """

    if hours <= 0:
        hours = 24
    if hours > 48:
        hours = 48

    if direction not in ("arrival", "departure", "both"):
        raise ValueError("direction must be 'arrival', 'departure' or 'both'")

    print(f"[Service] Refresh voli per '{airport_code}', hours={hours}, direction={direction}")

    now = int(time.time())
    end_time = now - 3600
    start_time = end_time - hours * 3600

    total_inserted = {}

    if direction in ("arrival", "both"):
        arrivals = fetch_flights_from_opensky(airport_code, "arrival", start_time, end_time)
        inserted_arr = store_flights_in_db(conn, airport_code, "arrival", arrivals)
        total_inserted["arrival"] = inserted_arr

    if direction in ("departure", "both"):
        departures = fetch_flights_from_opensky(airport_code, "departure", start_time, end_time)
        inserted_dep = store_flights_in_db(conn, airport_code, "departure", departures)
        total_inserted["departure"] = inserted_dep

    return {
        "airport_code": airport_code,
        "hours": hours,
        "inserted": total_inserted,
    }