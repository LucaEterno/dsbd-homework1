import os
import grpc
from concurrent import futures
import mysql.connector
from mysql.connector import Error

import user_manager_pb2
import user_manager_pb2_grpc


class UserManagerService(user_manager_pb2_grpc.UserManagerServicer):
    """
    Implementazione del servizio gRPC UserManager.
    Gestisce solo la verifica delle credenziali tramite MySQL.
    """

    def __init__(self):
        try:
            self.conn = mysql.connector.connect(
                host=os.getenv("USER_DB_HOST", "127.0.0.1"),
                port=int(os.getenv("USER_DB_PORT", "3306")),
                database=os.getenv("USER_DB_NAME", "usermanager_db"),
                user=os.getenv("USER_DB_USER", "usermgr"),
                password=os.getenv("USER_DB_PASSWORD", "usermgrpwd"),
            )
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(dictionary=True)
            print("Connessione a MySQL (usermanager_db) effettuata con successo\n")
        except Error as e:
            print(f"Errore di connessione a MySQL (usermanager_db): {e}")
            raise

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

        try:
            sql = "SELECT 1 FROM users WHERE email = %s"
            self.cursor.execute(sql, (email,))
            row = self.cursor.fetchone()

            exists = row is not None
            print(f"[CheckUserExists] email='{email}' exists={exists}")
            return user_manager_pb2.CheckUserExistsResponse(
                exists=exists
            )

        except Error as e:
            print(f"Errore DB in CheckUserExists: {e}")
            context.set_details("Database error during CheckUserExists")
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
            sql = "SELECT password FROM users WHERE email = %s"
            self.cursor.execute(sql, (email,))
            row = self.cursor.fetchone()

            if row is None or row["password"] != password:
                print(f"[CheckUserCredentials] FAILED: wrong email or password")
                return user_manager_pb2.CheckUserCredentialsResponse(valid=False)

            print(f"[CheckUserCredentials] SUCCESS: credenziali valide per '{email}'")
            return user_manager_pb2.CheckUserCredentialsResponse(valid=True)

        except Error as e:
            print(f"Errore DB in CheckUserCredentials: {e}")
            context.set_details("Database error during CheckUserCredentials")
            context.set_code(grpc.StatusCode.INTERNAL)
            return user_manager_pb2.CheckUserCredentialsResponse(valid=False)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    user_manager_pb2_grpc.add_UserManagerServicer_to_server(
        UserManagerService(), server
    )

    port = "50051"
    server.add_insecure_port(f"[::]:{port}")

    server.start()
    print(f"UserManager gRPC server avviato sulla porta {port}")
    print("In attesa di richieste dal Data Collector...\n")

    server.wait_for_termination()


if __name__ == "__main__":
    serve()
