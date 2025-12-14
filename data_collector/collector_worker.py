import time
import threading
import os
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from opensky_client import refresh_flights_for_airport_logic
from kafka_producer import send_update_completed_notification, flush_producer


# Legge le variabili d'ambiente
mysql_host = os.getenv("MYSQL_HOST", "mysql_data_db")
mysql_port = int(os.getenv("MYSQL_PORT", 3306))
mysql_database = os.getenv("MYSQL_DATABASE", "data_db")
mysql_user = os.getenv("MYSQL_USER", "userdt")
mysql_password = os.getenv("MYSQL_PASSWORD", "userdtpwd")

PERIOD_HOURS = 12
PERIOD_SECONDS = PERIOD_HOURS * 3600

stop_event = threading.Event()

def get_db_standalone():
    """Restituisce una connessione DB stand-alone."""
    db = mysql.connector.connect(
        host=mysql_host,
        port=mysql_port,
        database=mysql_database,
        user=mysql_user,
        password=mysql_password
    )
    return db

def periodic_data_collection():
    """Ciclo principale del thread di monitoraggio."""
    print(f"Data Collector Thread avviato, periodo: {PERIOD_HOURS} ore.")
    while not stop_event.is_set():
        start_time = time.time()
        update_successful = False

        try:
            conn = get_db_standalone() # Connessione dedicata per il thread
            cursor = conn.cursor()

            # 1. Recupera la lista univoca di tutti gli aeroporti di interesse
            sql = "SELECT DISTINCT airport_code FROM user_airports"
            cursor.execute(sql)
            airports = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()

            print(f"[Collector_Worker] Trovati {len(airports)} aeroporti da monitorare.")

            # 2. Aggiorna i dati per ciascun aeroporto
            for airport_code in airports:
                try:
                    conn_refresh = get_db_standalone()
                    print(f"[Collector_Worker] Aggiornamento dati per {airport_code}...")
                    refresh_flights_for_airport_logic(conn_refresh, airport_code, PERIOD_HOURS, "both")
                    conn_refresh.close()
                except Exception as e:
                    print(f"[Collector_Worker] ATTENZIONE: Errore durante l'aggiornamento dati per {airport_code}: {e}")
                    # Chiusura connessione in caso di errore
                    if conn_refresh is not None and conn_refresh.is_connected():
                        conn_refresh.close()

            update_successful = True

        except Error as e:
            print(f"[Collector_Worker] Errore DB nel thread di monitoraggio: {e}")
            # Chiude la connessione principale se è aperta
            if 'conn' in locals() and conn.is_connected():
                conn.close()
        except Exception as e:
            print(f"[Collector_Worker] Errore inatteso nel thread di monitoraggio: {e}")

        # 3. Invio del messaggio su Kafka (Producer) - Eseguito solo se l'aggiornamento è terminato
        if update_successful:
            print(f"[Collector_Worker] Aggiornamento DB completato. Invio notifica a Kafka.")
            # Chiamata alla funzione producer che invia il trigger
            send_update_completed_notification()
        else:
            print(f"[Collector_Worker] Aggiornamento fallito o non completato. Nessuna notifica Kafka inviata.")

        # 4. Metti in pausa fino al prossimo ciclo
        elapsed_time = time.time() - start_time
        sleep_time = max(0, PERIOD_SECONDS - elapsed_time)
        print(f" [Collector_Worker] Ciclo completato in {elapsed_time:.2f}s. Prossimo ciclo tra {sleep_time:.2f}s.")
        stop_event.wait(sleep_time)

    # 5. Flush del producer prima della chiusura del thread
    print(f"[Collector_Worker] Data Collector Thread terminato. Flusso Kafka in uscita...")
    flush_producer()
    print(f"[Collector_Worker] Flusso Kafka completato.")



def start_collector_thread():
    """Funzione per avviare il thread."""
    collector_thread = threading.Thread(
        target=periodic_data_collection,
        daemon=True
    )
    collector_thread.start()
    return collector_thread

def stop_collector_thread(thread):
    """Funzione per fermare il thread in modo sicuro."""
    print("Segnalazione di chiusura al thread di monitoraggio...")
    stop_event.set()
    thread.join()