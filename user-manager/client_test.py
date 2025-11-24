"""
gRPC Client for User Management (UserManager)
Questo client dimostra il funzionamento delle tre operazioni:
    - RegisterUser
    - CheckUserExists
    - DeleteUser
"""

import grpc
import user_manager_pb2
import user_manager_pb2_grpc


def print_response(operation, response):
    """
    Stampa leggibile della risposta del server.

    Per UserResponse:
        - response.success → True/False
        - response.message → stringa

    Per CheckUserExistsResponse:
        - response.exists → True/False
    """

    if hasattr(response, "success"):  # UserResponse
        status_text = "SUCCESS" if response.success else "ERROR"
        print(f"{operation}: [{status_text}] {response.message}")

    elif hasattr(response, "exists"):  # CheckUserExistsResponse
        status_text = "YES" if response.exists else "NO"
        print(f"{operation}: user exists? → {status_text}")

    else:
        print(f"{operation}: risposta sconosciuta → {response}")


def run():
    """
    Esegue una serie di operazioni di test.
    Scenario:
    1. RegisterUser (dovrebbe riuscire)
    2. CheckUserExists (dovrebbe essere True)
    3. RegisterUser duplicato (dovrebbe fallire)
    4. DeleteUser con password errata (errore)
    5. DeleteUser con password corretta (successo)
    6. CheckUserExists (dovrebbe essere False)
    """

    print("Connessione al server gRPC su localhost:50051...\n")

    with grpc.insecure_channel("localhost:50051") as channel:

        stub = user_manager_pb2_grpc.UserManagerStub(channel)

        print("=" * 60)
        print("STARTING TEST SCENARIO")
        print("=" * 60)

        # ------------------------------------------------------------
        print("\n[TEST 1] RegisterUser - nuovo utente 'alice'")
        response = stub.RegisterUser(
            user_manager_pb2.RegisterUserRequest(
                user=user_manager_pb2.User(
                    email="alice@example.com",
                    CF="ALC12345X",
                    password="pass123"
                )
            )
        )
        print_response("RegisterUser", response)

        # ------------------------------------------------------------
        print("\n[TEST 1.1] RegisterUser - nuovo utente 'luca'")
        response = stub.RegisterUser(
            user_manager_pb2.RegisterUserRequest(
                user=user_manager_pb2.User(
                    email="luca@example.com",
                    CF="LCA67890Y",
                    password="pass456"
                )
            )
        )
        print_response("RegisterUser", response)

        # ------------------------------------------------------------
        print("\n[TEST 2] CheckUserExists('alice@example.com')")
        response = stub.CheckUserExists(
            user_manager_pb2.CheckUserExistsRequest(
                email="alice@example.com"
            )
        )
        print_response("CheckUserExists", response)

        # ------------------------------------------------------------
        print("\n[TEST 2.1] CheckUserExists('luca@example.com')")
        response = stub.CheckUserExists(
            user_manager_pb2.CheckUserExistsRequest(
                email="luca@example.com"
            )
        )
        print_response("CheckUserExists", response)

        # ------------------------------------------------------------
        print("\n[TEST 3] RegisterUser duplicato (fallisce)")
        response = stub.RegisterUser(
            user_manager_pb2.RegisterUserRequest(
                user=user_manager_pb2.User(
                    email="alice@example.com",
                    CF="ALC12345X",
                    password="anotherPass"
                )
            )
        )
        print_response("RegisterUser", response)

        # ------------------------------------------------------------
        print("\n[TEST 4] DeleteUser con email ERRATA")
        response = stub.DeleteUser(
            user_manager_pb2.DeleteUserRequest(
                email="wrong_email@example.com",
                password="wrong_pass"
            )
        )
        print_response("DeleteUser", response)

        # ------------------------------------------------------------
        print("\n[TEST 5] DeleteUser con password ERRATA")
        response = stub.DeleteUser(
            user_manager_pb2.DeleteUserRequest(
                email="alice@example.com",
                password="wrong_pass"
            )
        )
        print_response("DeleteUser", response)

        # ------------------------------------------------------------
        print("\n[TEST 6] DeleteUser con password corretta")
        response = stub.DeleteUser(
            user_manager_pb2.DeleteUserRequest(
                email="alice@example.com",
                password="pass123"
            )
        )
        print_response("DeleteUser", response)

        # ------------------------------------------------------------
        print("\n[TEST 7] CheckUserExists (dopo cancellazione)")
        response = stub.CheckUserExists(
            user_manager_pb2.CheckUserExistsRequest(
                email="alice@example.com"
            )
        )
        print_response("CheckUserExists", response)

        print("\n" + "=" * 60)
        print("TEST SCENARIO COMPLETED")
        print("=" * 60)


if __name__ == "__main__":
    run()
