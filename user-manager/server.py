"""
gRPC Server for User Management (UserManager)
Questo server fornisce tre operazioni: RegisterUser, DeleteUser, CheckUserExists.
Gli utenti sono memorizzati in un database MySQL (persistente).
"""

import grpc
from concurrent import futures

import user_manager_pb2
import user_manager_pb2_grpc

import mysql.connector
from mysql.connector import Error


class UserManagerService(user_manager_pb2_grpc.UserManagerServicer):
    """
    Implementazione del servizio gRPC UserManager.
    Gestisce gli utenti tramite un database MySQL.
    """

    def __init__(self):
        # Connessione al database MySQL
        try:
            self.conn = mysql.connector.connect(
                host="127.0.0.1",
                port=3306,
                database="usermanager_db",
                user="usermgr",
                password="usermgrpwd",
            )
            self.conn.autocommit = True  # così non dobbiamo chiamare conn.commit() ogni volta
            self.cursor = self.conn.cursor(dictionary=True) #dictionary=True per avere dizionari come risultati anziché tuple di righe
            print("Connessione a MySQL effettuata con successo\n")
        except Error as e:
            print(f"Errore di connessione a MySQL: {e}")
            raise

    def RegisterUser(self, request, context):
        """
        Registra un nuovo utente nel sistema.

        Args:
            request: RegisterUserRequest con campo 'user'

        Returns:
            UserResponse:
                success=True, message="user added" se aggiunto
                success=False, message="user already exists" se email già presente
        """

        user = request.user  # User { email, CF, password }
        email = user.email

        print(f"[RegisterUser] Richiesta registrazione sul DB per: {email}")
        # Usiamo la email come PRIMARY KEY per garantire "at-most-once":
        try:
            sql = """
                INSERT INTO users (email, cf, password)
                VALUES (%s, %s, %s)
            """
            params = (user.email, user.CF, user.password)
            self.cursor.execute(sql, params)

            print(f"[RegisterUser] SUCCESS: '{email}' added")
            return user_manager_pb2.UserResponse(
                success=True,
                message="user added"
            )

        except Error as e:
            if e.errno == 1062: # 1062 = Duplicate entry (chiave primaria duplicata)
                print(f"[RegisterUser] FAILED: '{email}' already exists (duplicate key)")
                return user_manager_pb2.UserResponse(
                    success=False,
                    message="user already exists"
                )

            print(f"[RegisterUser] ERROR DB: {e}")
            context.set_details("Database error during RegisterUser")
            context.set_code(grpc.StatusCode.INTERNAL)
            return user_manager_pb2.UserResponse(
                success=False,
                message="internal error"
            )

    def DeleteUser(self, request, context):
        """
        Cancella un utente esistente dal sistema.

        Args:
            request: DeleteUserRequest con email e password

        Returns:
            UserResponse:
                success=True, message="user removed" se rimosso
                success=False, message="user does not exist" se non trovato
                success=False, message="invalid credentials" se password errata
        """

        email = request.email
        password = request.password

        print(f"[DeleteUser] Richiesta cancellazione dal DB per: {email}")

        try:
            # 1) Verifico se l'utente esiste e recupero la password
            sql_select = "SELECT password FROM users WHERE email = %s"
            self.cursor.execute(sql_select, (email,))
            row = self.cursor.fetchone()

            if row is None:
                print(f"[DeleteUser] FAILED: '{email}' does not exist")
                return user_manager_pb2.UserResponse(
                    success=False,
                    message="user does not exist"
                )

            # 2) Controllo la password
            if row["password"] != password:
                print(f"[DeleteUser] FAILED: wrong password for '{email}'")
                return user_manager_pb2.UserResponse(
                    success=False,
                    message="invalid credentials"
                )

            # 3) Cancello l'utente
            sql_delete = "DELETE FROM users WHERE email = %s"
            self.cursor.execute(sql_delete, (email,))
            print(f"[DeleteUser] SUCCESS: '{email}' removed")
            return user_manager_pb2.UserResponse(
                success=True,
                message="user removed"
            )

        except Error as e:
            print(f"[DeleteUser] ERROR DB: {e}")
            context.set_details("Database error during DeleteUser")
            context.set_code(grpc.StatusCode.INTERNAL)
            return user_manager_pb2.UserResponse(
                success=False,
                message="internal error"
            )

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
            print(f"[CheckUserExists] ERROR DB: {e}")
            context.set_details("Database error during CheckUserExists")
            context.set_code(grpc.StatusCode.INTERNAL)
            # In caso di errore DB consideriamo exists=False per il momento
            return user_manager_pb2.CheckUserExistsResponse(
                exists=False
            )


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
