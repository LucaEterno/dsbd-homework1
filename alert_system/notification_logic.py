import os
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Any

# Legge le variabili d'ambiente
mysql_host = os.getenv("DB_HOST", "mysql_data_db")
mysql_port = int(os.getenv("DB_PORT", 3306))
mysql_database = os.getenv("DB_NAME", "data_db")
mysql_user = os.getenv("DB_USER", "userdt")
mysql_password = os.getenv("DB_PASSWORD", "userdtpwd")

def get_db_standalone():
    """Restituisce una connessione DB stand-alone."""
    try:
        db = mysql.connector.connect(
            host=mysql_host,
            port=mysql_port,
            database=mysql_database,
            user=mysql_user,
            password=mysql_password
        )
        return db
    except Error as e:
        print(f"Errore nella connessione al database: {e}")
        raise

def verification_logic(airports_data: dict) -> List[Dict[str, Any]]:
    """
    Verifica il conteggio dei voli e lo confronta con le soglie degli utenti.

    Params:
        airports_data = dati ricevuti da Kafka
    """

    conn = None
    results_to_notify = []

    try:
        conn = get_db_standalone()
        cursor = conn.cursor(dictionary=True)

        # 1. Recupera le soglie degli utenti dal DB
        sql_users = """
            SELECT user_email, airport_code, high_value, low_value
            FROM user_airports
            WHERE high_value IS NOT NULL OR low_value IS NOT NULL
        """
        cursor.execute(sql_users)
        users_thresholds = cursor.fetchall()

        if not users_thresholds:
            return []

        # 2. Confronto e Generazione Notifiche
        for entry in users_thresholds:
            ap_code = entry['airport_code']
            user_email = entry['user_email']
            high_value = entry['high_value']
            low_value = entry['low_value']

            # Prendi il conteggio da airports_data invece che dal DB
            if ap_code in airports_data:
                current_count = airports_data[ap_code].get('flight_count', 0)
            else:
                current_count = 0  # Aeroporto non aggiornato

            condition = None  # Inizializza la variabile
            
            # Verifica soglie
            if high_value is not None and current_count > high_value:
                condition = f"SUPERA SOGLIA MAX (Voli: {current_count} > Max: {high_value})"

            elif low_value is not None and current_count < low_value:
                condition = f"SOTTO SOGLIA MIN (Voli: {current_count} < Min: {low_value})"

            # Aggiungi alla lista dei risultati se è stata trovata una condizione
            if condition:
                results_to_notify.append({
                    "user_email": user_email,
                    "airport_code": ap_code,
                    "current_count": current_count,
                    "condition": condition,
                    "threshold_max": high_value,
                    "threshold_min": low_value,
                    "timestamp": datetime.now().isoformat()
                })

    except Error as e:
        print(f"Errore durante verification_logic: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    return results_to_notify