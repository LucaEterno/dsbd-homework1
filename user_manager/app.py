import os
import requests
import mysql.connector
from mysql.connector import Error
from flask import request, jsonify, Flask, g

from redis_utils import generate_content_hash, initialize_redis_client, check_idempotency, save_idempotent_response

app = Flask(__name__)
initialize_redis_client() # Inizializza redis_client


# Variabili d'ambiente
mysql_host = os.getenv("MYSQL_HOST", "mysql_user_db")
mysql_port = int(os.getenv("MYSQL_PORT", 3306))
mysql_database = os.getenv("MYSQL_DATABASE", "usermanager_db")
mysql_user = os.getenv("MYSQL_USER", "usermgr")
mysql_password = os.getenv("MYSQL_PASSWORD", "usermgrpwd")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", 5003))
DATACOLLECTOR_BASE_URL = os.getenv("DATACOLLECTOR_BASE_URL", "http://data_collector:5002")

def get_db():
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
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/users/register", methods=["POST"])
def register():
    """
    Aggiunge un utente.

    Body JSON:
    {
      "email": "user@example.com",
      "password": "pwd123"
      "cf": "CODICEFISCALE"
    }
    """
    db = get_db()
    if db is None:
        return jsonify({"error": "Database non connesso"}), 503

    # Validazione campi
    try:
        data = request.get_json() or {}
    except Exception:
        response_data = {"error": "Corpo della richiesta JSON non valido"}
        return jsonify(response_data), 400

    required_fields = ["email", "password", "cf"]
    missing = [field for field in required_fields if field not in data]

    if missing:
        return jsonify({
            "error": "Campi mancanti",
            "missing_fields": missing
        }), 400

    email = data["email"]
    password = data["password"]
    cf = data["cf"]

    # Controllo requestID
    requestID = request.headers.get("requestID")
    if not requestID:
        return jsonify({
            "error": "Header obbligatorio mancante: requestID",
            "message": "La richiesta non verrà elaborata."
        }), 400

    content_hash = generate_content_hash(data)
    idempotency_key = f"register:{requestID}:{content_hash}"

    status, body = check_idempotency(idempotency_key)
    if status:
        return jsonify(body), status

    # Esecuzione query
    try:
        cursor = db.cursor()
        query = "INSERT INTO users (email, password, cf) VALUES (%s, %s, %s)"
        cursor.execute(query, (email, password, cf))
        db.commit()
        cursor.close()

        response_data = {
            "message": "Utente registrato con successo",
            "user": {
                "email": email,
                "cf": cf
            }
        }
        status_code = 201

    except Error as e:
        # Errore: email duplicata (MySQL error code 1062)
        if e.errno == 1062:
            response_data = {
                "error": "Email già registrata"
            }
            status_code = 409

        # Altri errori MySQL
        else:
            response_data = {
                "error": "Errore durante la creazione dell'utente",
                "details": str(e)
            }
            status_code = 500

    # Salvataggio in redis e invio risposta
    save_idempotent_response(idempotency_key, status_code, response_data)
    return jsonify(response_data), status_code


@app.route("/users/delete", methods=["DELETE"])
def delete_user():
    """
    Cancella un utente esistente.

    Body JSON:
    {
      "email": "user@example.com",
      "password": "pwd123"
    }
    """

    db = get_db()
    if db is None:
        return jsonify({"error": "Database non connesso"}), 503

    # Validazione campi
    data = request.get_json()
    required_fields = ["email", "password"]
    missing = [field for field in required_fields if field not in data]
    if missing:
        return jsonify({
            "error": "Campi mancanti",
            "missing_fields": missing
        }), 400

    email = data["email"]
    password = data["password"]

    # Controllo requestID
    requestID = request.headers.get("requestID")

    if not requestID:
        return jsonify({
            "error": "Header obbligatorio mancante: requestID",
            "message": "La richiesta non verrà elaborata."
        }), 400

    content_hash = generate_content_hash(data)
    idempotency_key = f"delete:{requestID}:{content_hash}"

    status, body = check_idempotency(idempotency_key)
    if status:
        return jsonify(body), status


    # Esecuzione query
    try:
        # Controllo che l'utente esista e che la password sia corretta
        cursor = db.cursor()
        # FOR UPDATE: inserisce un lock sulla riga in attesa della cancellazione
        query_check = "SELECT email FROM users WHERE email = %s AND password = %s FOR UPDATE"
        cursor.execute(query_check, (email, password))
        result = cursor.fetchone()

        if not result:
            print(f"[UserManagerApp] FAILED: wrong email or password")
            response_data = {
                    "error": "Email o password non corretta"
            }
            status_code = 401

        else:
            # Notifico il Data Collector per rimuovere le associazioni utente-aeroporto
            try:
                dc_base = DATACOLLECTOR_BASE_URL
                dc_url = f"{dc_base}/user/airports"
                payload = {"email": email, "password": password}

                print(f"[HTTP UserManager] Notifico Data Collector per cancellare associazioni di '{email}'")
                resp = requests.delete(dc_url, json=payload, timeout=5)

                if resp.status_code == 200:
                    data = resp.json()
                    deleted = data.get("deleted", 0)
                    print(f"[HTTP UserManager] Data Collector ha cancellato {deleted} associazioni per '{email}'")
                else:
                    print(f"[HTTP UserManager] WARNING: risposta non OK da Data Collector: {resp.status_code} - {resp.text}")

            except requests.RequestException as e:
                # Non blocchiamo la cancellazione utente se il Data Collector non risponde
                print(f"[HTTP UserManager] WARNING: impossibile contattare Data Collector per cleanup: {e}")

            # Procedo con la cancellazione effettiva dell'utente
            query_delete = "DELETE FROM users WHERE email = %s"
            cursor.execute(query_delete, (email,))
            db.commit()
            cursor.close()

            response_data = {
                "success": True,
                "message": "Utente cancellato con successo",
                "email": email
            }
            status_code = 200

    except Exception as e:
        db.rollback()
        response_data = {
            "success": False,
            "error": "Errore durante la cancellazione dell'utente",
            "details": str(e)
        }
        status_code = 500

    # Salvataggio in redis e invio risposta
    save_idempotent_response(idempotency_key, status_code, response_data)
    return jsonify(response_data), status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=LISTEN_PORT, debug=True)

