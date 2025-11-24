"""
gRPC Server for User Management (UserManager)
Questo server fornisce tre operazioni: RegisterUser, DeleteUser, CheckUserExists.
Gli utenti sono memorizzati in memoria (non persistente).
"""

import grpc
from concurrent import futures

import user_manager_pb2
import user_manager_pb2_grpc


class UserManagerService(user_manager_pb2_grpc.UserManagerServicer):
    """
    Implementazione del servizio gRPC UserManager.
    Gestisce gli utenti tramite un dizionario in memoria.
    """

    def __init__(self):
        # In-memory storage: { email: {"CF": ..., "password": ...} }
        # I dati vengono persi quando il server si ferma.
        self.users = {}
        print("UserManagerService inizializzato con database utenti vuoto\n")

    def RegisterUser(self, request, context):
        """
        Registra un nuovo utente nel sistema.

        Args:
            request: RegisterUserRequest con campo 'user'
            context: gRPC context

        Returns:
            UserResponse con:
            - success=True, message="user added" se aggiunto
            - success=False, message="user already exists" se email già presente
        """
        user = request.user  # User { email, CF, password }
        email = user.email

        # Controllo se l'utente esiste già (at-most-once a livello logico)
        if email in self.users:
            print(f"[RegisterUser] FAILED: '{email}' already exists")
            return user_manager_pb2.UserResponse(
                success=False,
                message="user already exists"
            )

        # Aggiungo nuovo utente
        self.users[email] = {
            "CF": user.CF,
            "password": user.password,
        }
        print(f"[RegisterUser] SUCCESS: '{email}' added (total users: {len(self.users)})")
        return user_manager_pb2.UserResponse(
            success=True,
            message="user added"
        )

    def DeleteUser(self, request, context):
        """
        Cancella un utente esistente dal sistema.

        Args:
            request: DeleteUserRequest con email e password
            context: gRPC context

        Returns:
            UserResponse con:
            - success=True, message="user removed" se rimosso correttamente
            - success=False, message="user does not exist" se email non trovata
            - success=False, message="invalid credentials" se password errata
        """
        email = request.email
        password = request.password

        # Controllo se l'utente esiste
        if email not in self.users:
            print(f"[DeleteUser] FAILED: '{email}' does not exist")
            return user_manager_pb2.UserResponse(
                success=False,
                message="user does not exist"
            )

        # Verifico la password
        if self.users[email]["password"] != password:
            print(f"[DeleteUser] FAILED: wrong password for '{email}'")
            return user_manager_pb2.UserResponse(
                success=False,
                message="invalid credentials"
            )

        # Cancello utente
        del self.users[email]
        print(f"[DeleteUser] SUCCESS: '{email}' removed (remaining users: {len(self.users)})")
        return user_manager_pb2.UserResponse(
            success=True,
            message="user removed"
        )

    def CheckUserExists(self, request, context):
        """
        Verifica se un utente esiste tramite email.

        Args:
            request: CheckUserExistsRequest con email
            context: gRPC context

        Returns:
            CheckUserExistsResponse con exists=True/False
        """
        email = request.email

        exists = email in self.users
        print(f"[CheckUserExists] email='{email}' exists={exists}")
        return user_manager_pb2.CheckUserExistsResponse(
            exists=exists
        )


def serve():
    """
    Avvia il server gRPC e resta in ascolto sulla porta 50051.
    """
    # Creo il server gRPC con un pool di thread
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Registro la nostra implementazione del servizio
    user_manager_pb2_grpc.add_UserManagerServicer_to_server(
        UserManagerService(), server
    )

    # Ascolto sulla porta 50051 su tutte le interfacce
    port = "50051"
    server.add_insecure_port(f"[::]:{port}")

    # Avvio il server
    server.start()
    print(f"UserManager gRPC server avviato sulla porta {port}")
    print("In attesa di richieste dai client...\n")

    # Mantiene il server in esecuzione
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
