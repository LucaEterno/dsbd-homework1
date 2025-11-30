import os
import time
import grpc
from concurrent import futures

import mysql.connector
from mysql.connector import Error

import user_manager_pb2, user_manager_pb2_grpc

#A CHE SERVE?
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__))) # Aggiunge la cartella corrente al path per importazioni locali


# Variabili d'ambiente
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

def _get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=MYSQL_DATABASE,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        autocommit=True
    )


class UserManagerService(user_manager_pb2_grpc.UserManagerServicer):
    """
    Implementazione del servizio gRPC UserManager.
    Gestisce gli utenti tramite un database MySQL.
    """

    def __init__(self):
        MAX_RETRIES = 10
        RETRY_DELAY = 3 # Secondi

        for attempt in range(MAX_RETRIES):
            try:
                print(f"Tentativo di connessione a MySQL (Check iniziale {attempt + 1}/{MAX_RETRIES})...")
                temp_conn = _get_db_connection()
                temp_conn.close() # Chiud la connessione di test
                print("Verifica connessione a MySQL effettuata con successo\n")
                return
            except Error as e:
                print(f"Errore di connessione a MySQL: {e}")
                if attempt < MAX_RETRIES - 1:
                    print(f"Ritentativo tra {RETRY_DELAY} secondi...")
                    time.sleep(RETRY_DELAY)
                else:
                    print("Tutti i tentativi falliti. Interruzione del server.")
                    raise ConnectionError("Impossibile connettersi al database MySQL dopo i tentativi.") from e


    def CheckUserExists(self, request, context):
        """
        Verifica se un utente esiste tramite email.

        Args:
            request: CheckUserExistsRequest con email

        Returns:
            CheckUserExistsResponse con exists=True/False
        """

        email = request.email
        print(f"[CheckUserExists] Verifica esistenza per: {email}")

        db_conn = None
        cursor = None

        try:
            # Apri una nuova connessione per questa richiesta
            with _get_db_connection() as db_conn:
                with db_conn.cursor(dictionary=True) as cursor:
                    sql = "SELECT 1 FROM users WHERE email = %s"
                    cursor.execute(sql, (email,))
                    row = cursor.fetchone()

                    exists = row is not None
                    return user_manager_pb2.CheckUserExistsResponse(
                        exists=exists
                    )

        except Error as e:
            print(f"[CheckUserExists] ERROR DB: {e}")
            context.set_details(f"Database error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return user_manager_pb2.CheckUserExistsResponse(
                exists=False
            )


    def CheckUserCredentials(self, request, context):
        """
        Verifica che email + password siano credenziali valide.

        Args:
            request: CheckUserCredentialsRequest con email e password

        Returns:
            CheckUserCredentialsResponse con valid=True/False
        """

        email = request.email
        password = request.password
        print(f"[CheckUserCredentials] Verifica credenziali per: {email}")

        try:
            # Apri una nuova connessione per questa richiesta
            with _get_db_connection() as db_conn:
                with db_conn.cursor(dictionary=True) as cursor:
                    sql = "SELECT password FROM users WHERE email = %s"
                    cursor.execute(sql, (email,))
                    row = cursor.fetchone()

                    if row is None or row["password"] != password:
                        print(f"[CheckUserCredentials] FAILED: wrong email or password")
                        return user_manager_pb2.CheckUserCredentialsResponse(valid=False)

            # Credenziali corrette
            print(f"[CheckUserCredentials] SUCCESS: credenziali valide per '{email}'")
            return user_manager_pb2.CheckUserCredentialsResponse(valid=True)

        except Error as e:
            print(f"Errore DB in CheckUserCredentials: {e}")
            context.set_details("Database error during CheckUserCredentials")
            context.set_code(grpc.StatusCode.INTERNAL)
            return user_manager_pb2.CheckUserCredentialsResponse(valid=False)


def serve():
    """
    Avvia il server gRPC e resta in ascolto sulla porta 50051.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    user_manager_pb2_grpc.add_UserManagerServicer_to_server(
        UserManagerService(), server
    )

    port = "50051"
    server.add_insecure_port(f"[::]:{port}")

    server.start()
    print(f"UserManager gRPC server avviato sulla porta {port}")
    print("In attesa di richieste dai client...\n")

    server.wait_for_termination()


if __name__ == "__main__":
    serve()
