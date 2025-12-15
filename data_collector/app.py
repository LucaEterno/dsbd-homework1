import os
import re
import grpc
import mysql.connector
from mysql.connector import Error
from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta

import collector_worker
import user_manager_pb2, user_manager_pb2_grpc
from opensky_client import refresh_flights_for_airport_logic, opensky_cb
from kafka_producer import send_update_completed_notification
from circuit_breaker import CircuitBreakerOpenException


app = Flask(__name__)


# Variabili d'ambiente
mysql_host = os.getenv("MYSQL_HOST", "mysql_data_db")
mysql_port = int(os.getenv("MYSQL_PORT", 3306))
mysql_database = os.getenv("MYSQL_DATABASE", "data_db")
mysql_user = os.getenv("MYSQL_USER", "userdt")
mysql_password = os.getenv("MYSQL_PASSWORD", "userdtpwd")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", 5002))

ICAO_REGEX = re.compile(r"^[A-Za-z]{4}$") # Setta il regex per il codice icao


def get_db():
    """
    Restituisce la connessione al DB data_db.
    Crea una nuova connessione se non è già presente in g.
    """
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=mysql_host,
            port=mysql_port,
            database=mysql_database,
            user=mysql_user,
            password=mysql_password
        )
    return g.db


@app.teardown_appcontext
def close_db(error):
    """
    Chiude la connessione al DB alla fine della richiesta, se presente in g.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_user_manager_stub():
    """
    Crea un client gRPC per comunicare con lo User Manager.
    """
    host = os.getenv("USER_MANAGER_HOST", "user_manager")
    port = os.getenv("USER_MANAGER_PORT", "50051")
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = user_manager_pb2_grpc.UserManagerStub(channel)
    return stub


@app.route("/user/airports", methods=["POST"])
def add_user_airport():
    """
    Aggiunge un aeroporto di interesse per un utente.

    Body JSON atteso:
    {
        "email": "user@example.com",
        "password": "pwd123",
        "airport_code": "LICC",
        "high_value": 50,   # opzionale
        "low_value": 10     # opzionale
    }

    Passi:
    1. Verifica credenziali chiamando UserManager.CheckUserCredentials via gRPC
    2. Se valide, inserisce (user_email, airport_code, high_value, low_value) nella tabella user_airports.
    """

    # 0) Verifica del JSON
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email")
    password = data.get("password")
    airport_code = data.get("airport_code")

    # Nuovi campi opzionali
    high_value = data.get("high_value", None)
    low_value = data.get("low_value", None)

    if not email or not password or not airport_code:
        return jsonify({"error": "Missing 'email' or 'password' or 'airport_code'"}), 400

    # Controllo sui parametri obbligatori
    if not isinstance(email, str) or \
       not isinstance(password, str) or \
       not isinstance(airport_code, str):
        return jsonify({"error": "email, password and airport_code must be strings"}), 400

    # Controllo formato ICAO
    airport_code = airport_code.upper()  # Case insensitivity
    if not ICAO_REGEX.match(airport_code):
        return jsonify({"error": "Invalid airport_code format (must be 4 letters, ICAO code)"}), 400

    # Validazione campi opzionali high_value / low_value
    try:
        if high_value is not None:
            high_value = int(high_value)
            if high_value < 0:
                return jsonify({"error": "high_value must be >= 0"}), 400

        if low_value is not None:
            low_value = int(low_value)
            if low_value < 0:
                return jsonify({"error": "low_value must be >= 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "high_value and low_value must be integers"}), 400

    # Se entrambi presenti, impongo high > low
    if high_value is not None and low_value is not None:
        if high_value <= low_value:
            return jsonify({"error": "high_value must be strictly greater than low_value"}), 400

    print(f"[DataCollector] Richiesta di aggiunta aeroporto '{airport_code}' per utente '{email}' "
          f"(high_value={high_value}, low_value={low_value})")

    # 1) Verifica credenziali via gRPC
    try:
        stub = get_user_manager_stub()
        cred_req = user_manager_pb2.CheckUserCredentialsRequest(
            email=email,
            password=password
        )
        cred_res = stub.CheckUserCredentials(cred_req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not cred_res.valid:
        print(f"[DataCollector] FAILED: credenziali non valide per '{email}' in POST /user/airports")
        return jsonify({
            "success": False,
            "message": "invalid credentials"
        }), 401

    # 2) Inserimento nel DB data_db.user_airports
    try:
        conn = get_db()
    except Error as e:
        print(f"Errore nella connessione al DB: {e}")
        return jsonify({"error": "Could not connect to data_db"}), 500

    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO user_airports (user_email, airport_code, high_value, low_value)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (email, airport_code, high_value, low_value))
        conn.commit()
        cursor.close()

        print(f"[DataCollector] SUCCESS: aggiunto aeroporto '{airport_code}' per utente '{email}'")
        return jsonify({
            "success": True,
            "message": "airport added for user",
            "email": email,
            "airport_code": airport_code,
            "high_value": high_value,
            "low_value": low_value
        }), 201

    except Error as e:
        # Se è una chiave duplicata (utente ha già quell'aeroporto), gestiamo l'errore
        if e.errno == 1062:
            print(f"[DataCollector] WARNING: coppia (user, airport) già esistente per '{email}', '{airport_code}'")
            return jsonify({
                "success": False,
                "message": "airport already registered for this user"
            }), 200

        # Altre tipologie di errore
        print(f"Errore DB in insert user_airports: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/user/airports", methods=["PUT"])
def update_user_airport_thresholds():
    """
    Aggiorna le soglie high_value / low_value per un profilo utente+aeroporto.

    Body JSON:
    {
      "email": "user@example.com",
      "password": "pwd123",
      "airport_code": "LICC",
      "high_value": 60,    # opzionale
      "low_value": 20      # opzionale
    }

    - Almeno una tra high_value e low_value deve essere presente.
    - Se entrambe presenti, viene verificata la condizione high_value > low_value.
    """
    # 0) Verifica del JSON
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email")
    password = data.get("password")
    airport_code = data.get("airport_code")
    high_value = data.get("high_value")
    low_value = data.get("low_value")

    if not email or not password or not airport_code:
        return jsonify({"error": "Missing 'email' or 'password' or 'airport_code'"}), 400

    # Controllo sui parametri obbligatori
    if not isinstance(email, str) or \
       not isinstance(password, str) or \
       not isinstance(airport_code, str):
        return jsonify({"error": "email, password and airport_code must be strings"}), 400
    if high_value is None and low_value is None:
        return jsonify({"error": "At least one of 'high_value' or 'low_value' must be provided"}), 400
    
    # Controllo formato ICAO
    airport_code = airport_code.upper()  # Case insensitivity
    if not ICAO_REGEX.match(airport_code):
        return jsonify({"error": "Invalid airport_code format (must be 4 letters, ICAO code)"}), 400

    # Validazione campi opzionali high_value / low_value
    try:
        if high_value is not None:
            high_value = int(high_value)
        if low_value is not None:
            low_value = int(low_value)
    except ValueError:
        return jsonify({"error": "high_value and low_value must be integers"}), 400

    if high_value is not None and low_value is not None and high_value <= low_value:
        return jsonify({
            "error": "high_value must be strictly greater than low_value"
        }), 400
    
    print(f"[DataCollector] Richiesta UPDATE soglie per '{email}' - '{airport_code}' "
          f"(high_value={high_value}, low_value={low_value})")
    
    # 1) Verifica credenziali via gRPC
    try:
        stub = get_user_manager_stub()
        cred_req = user_manager_pb2.CheckUserCredentialsRequest(
            email=email,
            password=password
        )
        cred_res = stub.CheckUserCredentials(cred_req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not cred_res.valid:
        print(f"[DataCollector] FAILED: credenziali non valide per '{email}' in PUT /user/airports")
        return jsonify({
            "success": False,
            "message": "invalid credentials"
        }), 401
    
    # 2) Aggiornamento del DB data_db.user_airports
    try:
        conn = get_db()
    except Error as e:
        print(f"Errore nella connessione al DB: {e}")
        return jsonify({"error": "Could not connect to data_db"}), 500

    try:
        cursor = conn.cursor()

        sql_update = """
            UPDATE user_airports
            SET high_value = %s,
                low_value  = %s
            WHERE user_email = %s AND airport_code = %s
        """
        cursor.execute(sql_update, (high_value, low_value, email, airport_code))
        row = cursor.rowcount
        conn.commit()
        cursor.close()

        if row == 0:
            print(f"[DataCollector] FAILED: associazione non esiste per '{email}', '{airport_code}'")
            return jsonify({
                "success": False,
                "message": "user_airport association does not exist"
            }), 404
        
        print(f"[DataCollector] SUCCESS: aggiornate soglie per '{email}' - '{airport_code}' "
              f"(high_value={high_value}, low_value={low_value})")

        return jsonify({
            "success": True,
            "message": "thresholds updated",
            "email": email,
            "airport_code": airport_code,
            "high_value": high_value,
            "low_value": low_value
        }), 200

    except Error as e:
        print(f"Errore DB in update_user_airport_thresholds: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/user/airports", methods=["GET"])
def get_user_airports():
    """
    Restituisce la lista degli aeroporti di interesse per un utente, incluse le soglie high_value e low_value.

    Richiesta:
            GET /user/airports?email=utente@example.com

    Passi:
    1. Legge l'email dalla query string.
    2. Verifica via gRPC che l'utente esista.
    3. Legge dal DB data_db.user_airports tutti gli aeroporti associati.
    4. Restituisce un JSON con la lista degli aeroporti.
    """
    # 0) Validazione parametri query
    email = request.args.get("email")

    if not email:
        return jsonify({"error": "Missing 'email' query parameter"}), 400
    
    if not isinstance(email, str):
        return jsonify({"error": "email must be a string"}), 400

    print(f"[DataCollector] Richiesta lista aeroporti per utente '{email}'")

    # 1) Verifica esistenza utente via UserManager (gRPC)
    try:
        stub = get_user_manager_stub()
        req = user_manager_pb2.CheckUserExistsRequest(email=email)
        res = stub.CheckUserExists(req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager in get_user_airports: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not res.exists:
        print(f"[DataCollector] Utente '{email}' non esiste secondo UserManager (GET /user/airports)")
        return jsonify({"error": "User does not exist"}), 404

    # 2) Recupero aeroporti dal DB data_db.user_airports
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True) #dictionary=True per avere dizionari come risultati anziché tuple di righe
        sql = """
            SELECT airport_code, high_value, low_value
            FROM user_airports
            WHERE user_email = %s
            ORDER BY airport_code
        """
        cursor.execute(sql, (email,))
        rows = cursor.fetchall() #Restituisce una lista di righe (ognuna è un dizionario)
        cursor.close()
        airports = [{"airport_code": row["airport_code"],
                "high_value": row["high_value"],
                "low_value": row["low_value"]} for row in rows]
        
        if len(airports) == 0:
            print(f"[DataCollector] INFO: nessun aeroporto associato a '{email}'")

        print(f"[DataCollector] SUCCESS: Trovati {len(airports)} aeroporti per utente '{email}'")
        return jsonify({
            "email": email,
            "airports": airports,
            "count": len(airports)
        }), 200

    except Error as e:
        print(f"Errore DB in get_user_airports: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/user/airports", methods=["DELETE"])
def delete_user_airports():
    """
    Rimuove le associazioni utente-aeroporto.

    Body JSON:
    {
      "email": "user@example.com",
      "password": "pwd123",
      "airport_code": "LICC",              # opzionale
    }

    - Se viene passato solo 'email'    -> cancella TUTTE le associazioni per quell'utente
    - Se viene passato anche 'airport_code' -> cancella SOLO quella specifica coppia
    """
    #0) Verifica del JSON
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email")
    password = data.get("password")
    airport_code = data.get("airport_code")

    if not email or not password:
        return jsonify({"error": "Missing 'email' or 'password'"}), 400

    # Controllo sui parametri
    if not isinstance(email, str) or \
        not isinstance(password, str):
        return jsonify({"error": "email and password must be strings"}), 400

    # Controllo formato ICAO (se airport_code è fornito)
    if(airport_code):
        airport_code = airport_code.upper() # Case insensitivity
        if not ICAO_REGEX.match(airport_code):
            return jsonify({"error": "Invalid airport_code format (must be 4 letters, ICAO code)"}), 400

    # 1) Verifico le credenziali via gRPC con UserManager
    try:
        stub = get_user_manager_stub()
        cred_req = user_manager_pb2.CheckUserCredentialsRequest(
            email=email,
            password=password
        )
        cred_res = stub.CheckUserCredentials(cred_req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager in delete_user_airports: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not cred_res.valid:
        print(f"[DataCollector] FAILED: credenziali non valide per '{email}' in DELETE /user/airports")
        return jsonify({
            "success": False,
            "message": "invalid credentials"
        }), 401

    conn = get_db()
    if conn is None:
        return jsonify({"error": "Could not connect to flightdata_db"}), 500

    # 2) Eseguo la cancellazione
    try:
        cursor = conn.cursor()

        if airport_code:
            print(f"[DataCollector] DELETE associazione utente '{email}' con aeroporto '{airport_code}'")
            sql_delete = "DELETE FROM user_airports WHERE user_email = %s AND airport_code = %s"
            params = (email, airport_code)
        else:
            print(f"[DataCollector] DELETE tutte le associazioni per utente '{email}'")
            sql_delete = "DELETE FROM user_airports WHERE user_email = %s"
            params = (email,)

        cursor.execute(sql_delete, params)
        conn.commit()
        deleted = cursor.rowcount
        cursor.close()

        return jsonify({
            "success": True,
            "deleted": deleted,
            "email": email,
            "airport_code": airport_code
        }), 200

    except Error as e:
        print(f"Errore DB in delete_user_airports: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/user/flights", methods=["GET"])
def get_user_flights():
    """
    Restituisce tutti i voli registrati nel DB data_db per gli aeroporti
    di interesse di un utente.

    Richiesta:
            GET /user/flights?email=utente@example.com

    Passi:
    1. Legge l'email dalla query string.
    2. Verifica via gRPC che l'utente esista.
    3. Legge dal DB data_db.user_airports tutti gli aeroporti associati.
    4. Restituisce un JSON con la lista dei voli.

    """
    # 1) Legge l'email dalla query string.
    email = request.args.get("email")

    if not email:
        return jsonify({"error": "Missing 'email' query parameter"}), 400

    print(f"[DataCollector] Richiesta lista voli per utente '{email}'")

    # 2) Verifica esistenza utente via UserManager (gRPC)
    try:
        stub = get_user_manager_stub()
        req = user_manager_pb2.CheckUserExistsRequest(email=email)
        res = stub.CheckUserExists(req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager in get_user_flights: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not res.exists:
        print(f"[DataCollector] Utente '{email}' non esiste secondo UserManager (GET /user/flights)")
        return jsonify({"error": "User does not exist"}), 404

    # 3) Recupero aeroporti e voli dal DB data_db
    try:
        conn = get_db()
    except Error as e:
        print(f"Errore nella connessione al DB: {e}")
        return jsonify({"error": "Could not connect to data_db"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # Passo A: Trova tutti gli aeroporti associati all'utente
        sql_airports = """
            SELECT airport_code FROM user_airports WHERE user_email = %s
        """
        cursor.execute(sql_airports, (email,))
        airport_rows = cursor.fetchall()

        # Lista dei codici aeroporto (es. ['LICC', 'LIMJ'])
        airports_of_interest = [row["airport_code"] for row in airport_rows]

        if not airports_of_interest:
            print(f"[DataCollector] Trovati 0 aeroporti di interesse per l'utente '{email}'.")
            return jsonify({
                "email": email,
                "airports": [],
                "flights": [],
                "count": 0
            }), 200

        # Passo B: Trova tutti i voli per quegli aeroporti
        placeholders = ', '.join(['%s'] * len(airports_of_interest))
        sql_flights = f"""
            SELECT airport_code, direction, flight_icao, callsign, flight_time
            FROM flights
            WHERE airport_code IN ({placeholders})
            ORDER BY flight_time DESC
        """

        cursor.execute(sql_flights, airports_of_interest)

        flights = cursor.fetchall()
        cursor.close()

        print(f"[DataCollector] Trovati {len(flights)} voli per utente '{email}' negli aeroporti di interesse.")
        return jsonify({
            "email": email,
            "airports": airports_of_interest,
            "flights": flights,
            "count": len(flights)
        }), 200

    except Error as e:
        print(f"Errore DB in get_user_flights: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/user/flights/last", methods=["GET"])
def get_last_flight_for_user_airport():
    """
    Restituisce l'ultimo volo in partenza e l'ultimo volo in arrivo registrati
    nel DB data_db per un specifico aeroporto di interesse per l'utente.

    Richiesta:
            GET /user/flights/last?email=utente@example.com&airport_code=LICC

    Passi:
    1. Legge i parametri dalla query string.
    2. Verifica la correttezza del codice ICAO.
    3. Verifica via gRPC che l'utente esista.
    4. Verifica che l'aeroporto sia associato all'utente.
    5. Esegue due query per trovare l'ultimo ARRIVO e l'ultima PARTENZA.
    6. Restituisce un JSON con i due voli trovati (o null se non ci sono).
    """
    # 1) Legge i parametri dalla query string.
    email = request.args.get("email")
    airport_code = request.args.get("airport_code")

    if not email or not airport_code:
        return jsonify({"error": "Missing 'email' or 'airport_code' query parameter"}), 400

    # 2) Verifica ICAO
    airport_code = airport_code.upper()
    if not ICAO_REGEX.match(airport_code):
        return jsonify({"error": "Invalid airport_code format (must be 4 letters, ICAO code)"}), 400

    print(f"[DataCollector] Richiesta ultimo volo per utente '{email}' all'aeroporto '{airport_code}'")

    # 3) Verifica esistenza utente via UserManager (gRPC)
    try:
        stub = get_user_manager_stub()
        req = user_manager_pb2.CheckUserExistsRequest(email=email)
        res = stub.CheckUserExists(req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager in get_last_flight_for_user_airport: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not res.exists:
        print(f"[DataCollector] Utente '{email}' non esiste secondo UserManager (GET /user/flights/last)")
        return jsonify({"error": "User does not exist"}), 404

    # 4) Verifica che l'aeroporto sia associato all'utente (opzionale ma buona pratica)
    try:
        conn = get_db()
        cursor = conn.cursor()
        sql_check = "SELECT 1 FROM user_airports WHERE user_email = %s AND airport_code = %s"
        cursor.execute(sql_check, (email, airport_code))
        is_airport_of_interest = cursor.fetchone()
        cursor.close()

        if not is_airport_of_interest:
            print(f"[DataCollector] Aeroporto '{airport_code}' non è negli interessi dell'utente '{email}'.")
            return jsonify({"error": "Airport is not registered as an interest for this user"}), 403

    except Error as e:
        print(f"Errore DB durante la verifica dell'aeroporto di interesse: {e}")
        return jsonify({"error": "Database check error"}), 500


    # 5) Esegue le query per l'ultimo volo (Arrivo e Partenza)
    try:
        cursor = conn.cursor(dictionary=True)

        # Query per l'ultimo ARRIVO
        sql_last_arrival = """
            SELECT airport_code, direction, flight_icao, callsign, flight_time
            FROM flights
            WHERE airport_code = %s AND direction = 'arrival'
            ORDER BY flight_time DESC
            LIMIT 1
        """
        cursor.execute(sql_last_arrival, (airport_code,))
        last_arrival = cursor.fetchone()

        # Query per l'ultima PARTENZA
        sql_last_departure = """
            SELECT airport_code, direction, flight_icao, callsign, flight_time
            FROM flights
            WHERE airport_code = %s AND direction = 'departure'
            ORDER BY flight_time DESC
            LIMIT 1
        """
        cursor.execute(sql_last_departure, (airport_code,))
        last_departure = cursor.fetchone()

        cursor.close()

        print(f"[DataCollector] Trovati ultimi voli per '{airport_code}' per utente '{email}'.")

        return jsonify({
            "email": email,
            "airport_code": airport_code,
            "last_arrival": last_arrival,  # Sarà un dizionario o None
            "last_departure": last_departure # Sarà un dizionario o None
        }), 200

    except Error as e:
        print(f"Errore DB nel recupero degli ultimi voli: {e}")
        return jsonify({"error": "Database query error"}), 500


@app.route("/user/flights/average", methods=["GET"])
def get_average_flights_for_user_airport():
    """
    Calcola la media di voli in partenza e in arrivo da un dato aeroporto
    negli ultimi X giorni.

    Richiesta:
            GET /user/flights/average?email=utente@example.com&airport_code=LICC&days=7

    Passi:
    1. Validazione di email, airport_code e days.
    2. Verifica esistenza utente (gRPC).
    3. Verifica associazione aeroporto (DB).
    4. Calcolo media (DB).
    """
    # 1) Legge e valida i parametri dalla query string.
    email = request.args.get("email")
    airport_code = request.args.get("airport_code")
    days_str = request.args.get("days")

    if not email or not airport_code or not days_str:
        return jsonify({"error": "Missing 'email', 'airport_code', or 'days' query parameter"}), 400

    try:
        days = int(days_str)
        if days <= 0:
            return jsonify({"error": "'days' must be a positive integer"}), 400
    except ValueError:
        return jsonify({"error": "'days' must be an integer"}), 400

    # Verifica ICAO
    airport_code = airport_code.upper()
    if not ICAO_REGEX.match(airport_code):
        return jsonify({"error": "Invalid airport_code format (must be 4 letters, ICAO code)"}), 400

    print(f"[DataCollector] Richiesta media voli per utente '{email}' all'aeroporto '{airport_code}' per {days} giorni.")

    # 2) Verifica esistenza utente via UserManager (gRPC)
    try:
        stub = get_user_manager_stub()
        req = user_manager_pb2.CheckUserExistsRequest(email=email)
        res = stub.CheckUserExists(req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager in get_average_flights_for_user_airport: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not res.exists:
        print(f"[DataCollector] Utente '{email}' non esiste secondo UserManager.")
        return jsonify({"error": "User does not exist"}), 404

    # 3) Verifica che l'aeroporto sia associato all'utente
    try:
        conn = get_db()
        cursor = conn.cursor()
        sql_check = "SELECT 1 FROM user_airports WHERE user_email = %s AND airport_code = %s"
        cursor.execute(sql_check, (email, airport_code))
        is_airport_of_interest = cursor.fetchone()

        if not is_airport_of_interest:
            cursor.close()
            print(f"[DataCollector] Aeroporto '{airport_code}' non è negli interessi dell'utente '{email}'.")
            return jsonify({"error": "Airport is not registered as an interest for this user"}), 403

    except Error as e:
        print(f"Errore DB durante la verifica dell'aeroporto di interesse: {e}")
        return jsonify({"error": "Database check error"}), 500


    # 4) Calcolo media (DB)
    try:
        #Calcolo intervallo
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) # Inizio del giorno corrente
        time_start_limit = now - timedelta(days=days)

        cursor = conn.cursor(dictionary=True)

        # Query per contare i voli totali (arrivi e partenze) nell'intervallo e raggruppare per direzione
        # Uso COUNT e GROUP BY direction
        sql_counts = """
            SELECT direction, COUNT(callsign) AS total_flights
            FROM flights
            WHERE airport_code = %s AND flight_time >= %s
            GROUP BY direction
        """
        cursor.execute(sql_counts, (airport_code, time_start_limit))

        counts = cursor.fetchall()
        cursor.close()

        # Inizializza i conteggi totali
        total_arrivals = 0
        total_departures = 0

        # Popola i conteggi dai risultati della query
        for row in counts:
            if row['direction'] == 'arrival':
                total_arrivals = row['total_flights']
            elif row['direction'] == 'departure':
                total_departures = row['total_flights']

        # Calcolo le medie giornaliere
        # Usiamo float per la divisione per garantire la media corretta
        avg_arrivals = total_arrivals / days
        avg_departures = total_departures / days

        print(f"[DataCollector] Calcolata media: Arrivi={avg_arrivals:.2f}, Partenze={avg_departures:.2f} per '{airport_code}'.")

        return jsonify({
            "email": email,
            "airport_code": airport_code,
            "days": days,
            "period_start": time_start_limit.isoformat(),
            "average_flights": {
                "arrival_per_day": round(avg_arrivals, 2),
                "departure_per_day": round(avg_departures, 2),
                "total_flights_in_period": {
                    "arrivals": total_arrivals,
                    "departures": total_departures
                }
            }
        }), 200

    except Error as e:
        print(f"Errore DB nel calcolo della media dei voli: {e}")
        return jsonify({"error": "Database query error during average calculation"}), 500


@app.route("/airport/refresh-flights", methods=["GET"])
def refresh_flights_for_airport():
    """
    Endpoint REST che simula il comportamento del thread di raccolta dati.
    """

    data = request.get_json(silent=True) or {} # silent=True -> se il body non è JSON valido, non genera errore
    hours = data.get("hours", 24) # parametro per specificare quante ore indietro prendere i voli
    direction = data.get("direction", "both")

    try:
        hours = int(hours)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'hours' value"}), 400

    if direction not in ("arrival", "departure", "both"):
        return jsonify({"error": "direction must be 'arrival', 'departure' or 'both'"}), 400

    try:
        # DEBUG: Recupera conteggi di TUTTI gli aeroporti per invio Kafka completo ed esegue il refresh
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Trova tutti gli aeroporti registrati
        cursor.execute("SELECT DISTINCT airport_code FROM user_airports")
        all_airports = [row[0] for row in cursor.fetchall()]
        
        # 2. Recupera i conteggi per ciascuno
        results = []
        airports_data = {}
        for ap_code in all_airports:
            results.append(refresh_flights_for_airport_logic(conn, ap_code, hours, direction))
            cursor.execute(
                "SELECT COUNT(*) FROM flights WHERE airport_code = %s", 
                (ap_code,)
            )
            count = cursor.fetchone()[0]
            airports_data[ap_code] = {
                'flight_count': count,
                'updated_at': datetime.now().isoformat()
            }
        
        cursor.close()
        
        # Notifica Kafka con TUTTI gli aeroporti (per testing completo)
        send_update_completed_notification(airports_data)
        # Restituisci i refresh di tutti gli aeroporti
        return jsonify(results), 200

    except CircuitBreakerOpenException as e:
        # Circuito aperto: non tentiamo nemmeno la chiamata a OpenSky
        return jsonify({
            "error": "OpenSky temporarily unavailable (circuit open). Retry later.",
            "details": str(e)
        }), 503

    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    except RuntimeError as e:
        # errori provenienti da OpenSky (timeout, HTTP error, token ecc.)
        return jsonify({"error": str(e)}), 502

    except Exception as e:
        print(f"Errore inatteso in refresh_flights_for_airport endpoint: {e}")
        return jsonify({"error": "unexpected error"}), 500
    

@app.route("/debug/opensky-cb", methods=["GET"])
def debug_opensky_cb():
    return jsonify({
        "state": opensky_cb.state,
        "failure_count": opensky_cb.failure_count,
        "last_failure_time": opensky_cb.last_failure_time,
        "failure_threshold": opensky_cb.failure_threshold,
        "recovery_timeout": opensky_cb.recovery_timeout
    }), 200

if __name__ == "__main__":
    # 1. Avvio thread
    collector_thread = collector_worker.start_collector_thread()

    # 2. Avvio Flask
    try:
        app.run(host="0.0.0.0", port=LISTEN_PORT, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        pass

    # 3. Stop thread quando termina app.run
    collector_worker.stop_collector_thread(collector_thread)
    print("Applicazione terminata.")