import os
import time
import requests

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

# Variabili per caching del token
_CACHED_TOKEN: str | None = None
_TOKEN_EXPIRY: float = 0.0


def _request_new_token(client_id: str, client_secret: str) -> tuple[str | None, float]:
    """
    Richiede un nuovo token a OpenSky e restituisce (token, expiry_timestamp).

    expiry_timestamp è il momento (UNIX time) in cui il token scade.
    """
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    print("[OpenSkyAuth] Richiesta di un nuovo token...")

    try:
        response = requests.post(TOKEN_URL, headers=headers, data=payload)

        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 300)  # secondi, default 5 minuti

            if access_token:
                now = time.time()
                expiry = now + expires_in
                print(f"[OpenSkyAuth] Nuovo token ricevuto. Scade tra {expires_in} secondi.")
                return access_token, expiry
            else:
                print("[OpenSkyAuth] Errore: risposta 200 ma 'access_token' mancante.")
                return None, 0.0
        else:
            print(f"[OpenSkyAuth] Errore di richiesta: HTTP {response.status_code}")
            print(f"[OpenSkyAuth] Dettagli errore: {response.text}")
            return None, 0.0

    except requests.exceptions.RequestException as e:
        print(f"[OpenSkyAuth] Errore di connessione: {e}")
        return None, 0.0


def get_opensky_token() -> str | None:
    """
    Restituisce un token OpenSky valido, usando caching in memoria.

    - Legge CLIENT_ID e CLIENT_SECRET dalle variabili d'ambiente.
    - Se esiste un token ancora valido in cache, lo riusa.
    - Altrimenti ne richiede uno nuovo e aggiorna la cache.
    """

    global _CACHED_TOKEN, _TOKEN_EXPIRY

    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[OpenSkyAuth] ERRORE: CLIENT_ID o CLIENT_SECRET non impostati nelle variabili d'ambiente.")
        return None

    now = time.time()

    # Se abbiamo un token in cache e non è quasi scaduto, lo riusiamo
    if _CACHED_TOKEN is not None and now < _TOKEN_EXPIRY - 60: # margine di 60 secondi
        return _CACHED_TOKEN # Token ancora valido

    # Altrimenti richiediamo un token nuovo
    token, expiry = _request_new_token(client_id, client_secret)
    if token:
        _CACHED_TOKEN = token
        _TOKEN_EXPIRY = expiry
        return token

    return None
