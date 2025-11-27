"""
HTTP/REST server per User Manager.
- Registra un nuovo utente
- Cancella un utente esistente

Queste API sono pensate per i client esterni (es. UI, script, ecc.).
Il Data Collector continua a usare il gRPC per CheckUserExists.
"""
import os
import requests

from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import requests


app = Flask(__name__)

 
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("USER_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("USER_DB_PORT", "3306")),
            database=os.getenv("USER_DB_NAME", "usermanager_db"),
            user=os.getenv("USER_DB_USER", "usermgr"),
            password=os.getenv("USER_DB_PASSWORD", "usermgrpwd"),
        )
        return conn
    except Error as e:
        print(f"Errore di connessione a MySQL (usermanager_db): {e}")
        return None


@app.route("/users/register", methods=["POST"])
def register_user():
    """
    Registra un nuovo utente.

    Body JSON:
    {
      "email": "user@example.com",
      "CF": "CODICEFISCALE",
      "password": "pwd123"
    }
    """

    data = request.get_json(silent=True) #silent=true evita di lanciare eccezione in caso di json malformato
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email")
    cf = data.get("CF")
    password = data.get("password")

    if not email or not cf or not password:
        return jsonify({"error": "Missing one of 'email', 'CF', 'password'"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Could not connect to usermanager_db"}), 500

    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO users (email, cf, password)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (email, cf, password))
        conn.commit()

        print(f"[HTTP UserManager] SUCCESS: registrato utente '{email}'")
        return jsonify({
            "success": True,
            "message": "user added",
            "email": email
        }), 201

    except Error as e:
        if e.errno == 1062:
            print(f"[HTTP UserManager] FAILED: '{email}' already exists")
            return jsonify({
                "success": False,
                "message": "user already exists"
            }), 200

        print(f"Errore DB in register_user: {e}")
        return jsonify({"error": "Database error"}), 500

    finally:
        cursor.close()
        conn.close()


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

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing 'email' or 'password'"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Could not connect to usermanager_db"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # 1) Verifico che utente esista e recupero password
        sql_select = "SELECT password FROM users WHERE email = %s"
        cursor.execute(sql_select, (email,))
        row = cursor.fetchone()

        if row is None or row["password"] != password:
                print(f"[HTTP UserManager] FAILED: wrong email or password")
                return jsonify({
                    "success": False,
                    "message": "invalid credentials"
            }), 401

        # 2) Notifico il Data Collector per rimuovere le associazioni utente-aeroporto
        try:
            dc_base = os.getenv("DATACOLLECTOR_BASE_URL", "http://127.0.0.1:5000")
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

        # 3) Cancello l'utente
        sql_delete = "DELETE FROM users WHERE email = %s"
        cursor.execute(sql_delete, (email,))
        conn.commit()

        print(f"[HTTP UserManager] SUCCESS: utente '{email}' cancellato dal DB utenti")

        return jsonify({
            "success": True,
            "message": "user removed (associations cleanup requested)",
            "email": email
        }), 200


    except Error as e:
        print(f"Errore DB in delete_user: {e}")
        return jsonify({"error": "Database error"}), 500

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
