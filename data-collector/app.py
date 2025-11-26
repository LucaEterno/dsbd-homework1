"""
Data Collector Service (prima versione)
- Espone una semplice API HTTP con Flask
- Verifica l'esistenza dell'utente tramite User Manager (gRPC)
- Memorizza gli aeroporti di interesse per utente nel DB flightdata_db
"""

from flask import Flask, request, jsonify
import grpc
from mysql.connector import Error
import os
import sys

from flight_services import (
    get_db_connection,
    refresh_flights_for_airport_logic,
)

# Aggiungo il path del microservizio user-manager per importare i file gRPC
#DA MODIFICARE PERCHE NON SICURA
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_MANAGER_DIR = os.path.join(CURRENT_DIR, "..", "user-manager")
sys.path.append(USER_MANAGER_DIR)
import user_manager_pb2, user_manager_pb2_grpc


app = Flask(__name__)


def get_user_manager_stub():
    """
    Crea un client gRPC per comunicare con lo User Manager.
    Per ora si assume che User Manager sia in ascolto su localhost:50051.
    """
    channel = grpc.insecure_channel("localhost:50051")
    stub = user_manager_pb2_grpc.UserManagerStub(channel)
    return stub


@app.route("/user/airports", methods=["POST"])
def add_user_airport():
    """
    Aggiunge un aeroporto di interesse per un utente.

    Body JSON atteso:
    {
        "email": "user@example.com",
        "airport_code": "LICC"
    }

    Passi:
    1. Verifica che l'utente esista chiamando UserManager.CheckUserExists via gRPC.
    2. Se esiste, inserisce (user_email, airport_code) nella tabella user_airports.
    """

    #0) Verifica del JSON
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email") #ricava l'email dal json
    airport_code = data.get("airport_code") #ricava il codice aeroporto dal json
    if not email or not airport_code:
        return jsonify({"error": "Missing 'email' or 'airport_code'"}), 400

    print(f"[DataCollector] Richiesta di aggiunta aeroporto '{airport_code}' per utente '{email}'")


    # 1) Verifica esistenza utente via gRPC
    try:
        stub = get_user_manager_stub()
        req = user_manager_pb2.CheckUserExistsRequest(email=email)
        res = stub.CheckUserExists(req)
    except grpc.RpcError as e:
        print(f"Errore gRPC verso UserManager: {e}")
        return jsonify({"error": "UserManager not reachable"}), 500

    if not res.exists:
        print(f"[DataCollector] Utente '{email}' non esiste")
        return jsonify({"error": "User does not exist"}), 404

    # 2) Inserimento nel DB flightdata_db.user_airports
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Could not connect to flightdata_db"}), 500

    try:
        cursor = conn.cursor() #non uso dictionary=True perché non devo visualizzare righe, solo inserire
        sql = """
            INSERT INTO user_airports (user_email, airport_code)
            VALUES (%s, %s)
        """
        cursor.execute(sql, (email, airport_code))
        conn.commit()
        print(f"[DataCollector] SUCCESS: aggiunto aeroporto '{airport_code}' per utente '{email}'")
        return jsonify({
            "success": True,
            "message": "airport added for user",
            "email": email,
            "airport_code": airport_code
        }), 201

    except Error as e:
        # Se è una chiave duplicata (utente ha già quell'aeroporto), gestiamo l'errore
        if e.errno == 1062:
            print(f"[DataCollector] WARNING: coppia (user, airport) già esistente per '{email}', '{airport_code}'")
            return jsonify({
                "success": False,
                "message": "airport already registered for this user"
            }), 200

        #Altre tipologie di errore
        print(f"Errore DB in insert user_airports: {e}")
        return jsonify({"error": "Database error"}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/user/airports", methods=["GET"])
def get_user_airports():
    """
    Restituisce la lista degli aeroporti di interesse per un utente.

    Richiesta:
        GET /user/airports?email=utente@example.com

    Passi:
    1. Legge l'email dalla query string.
    2. Verifica via gRPC che l'utente esista.
    3. Legge dal DB flightdata_db.user_airports tutti gli aeroporti associati.
    4. Restituisce un JSON con la lista degli aeroporti.
    """

    email = request.args.get("email")

    if not email:
        return jsonify({"error": "Missing 'email' query parameter"}), 400

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

    # 2) Recupero aeroporti dal DB flightdata_db.user_airports
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Could not connect to flightdata_db"}), 500

    try:
        cursor = conn.cursor(dictionary=True) #dictionary=True per avere dizionari come risultati anziché tuple di righe
        sql = """
            SELECT airport_code
            FROM user_airports
            WHERE user_email = %s
            ORDER BY airport_code
        """
        cursor.execute(sql, (email,))
        rows = cursor.fetchall() #Restituisce una lista di righe (ognuna è un dizionario)

        airports = [row["airport_code"] for row in rows]

        print(f"[DataCollector] Trovati {len(airports)} aeroporti per utente '{email}'")
        return jsonify({
            "email": email,
            "airports": airports,
            "count": len(airports)
        }), 200

    except Error as e:
        print(f"Errore DB in get_user_airports: {e}")
        return jsonify({"error": "Database error"}), 500

    finally:
        cursor.close()
        conn.close()


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

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email")
    password = data.get("password")
    airport_code = data.get("airport_code")

    if not email or not password:
        return jsonify({"error": "Missing 'email' or 'password'"}), 400

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

    conn = get_db_connection()
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

        return jsonify({
            "success": True,
            "deleted": deleted,
            "email": email,
            "airport_code": airport_code
        }), 200

    except Error as e:
        print(f"Errore DB in delete_user_airports: {e}")
        return jsonify({"error": "Database error"}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/airport/<airport_code>/refresh-flights", methods=["POST"])
def refresh_flights_for_airport(airport_code):
    """
    Endpoint REST che usa la logica di flight_service.refresh_flights_for_airport_logic.
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
        result = refresh_flights_for_airport_logic(airport_code, hours, direction)
        return jsonify(result), 200
    except ValueError as e:
        # errori di validazione lato servizio
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        # errori provenienti da OpenSky
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        print(f"Errore inatteso in refresh_flights_for_airport endpoint: {e}")
        return jsonify({"error": "unexpected error"}), 500


if __name__ == "__main__":
    # Avvio del server Flask
    # host 0.0.0.0 per permettere accesso dall'esterno (es. da altri container)
    app.run(host="0.0.0.0", port=5000, debug=True)
