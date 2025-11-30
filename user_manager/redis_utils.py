import redis
import os
import json
import hashlib
from datetime import timedelta

# Variabile globale per il client Redis.
# Verrà inizializzata nel punto di ingresso dell'applicazione.
redis_client = None

# Legge le variabili d'ambiente per la connessione a Redis
redis_host = os.getenv("REDIS_HOST", "redis_cache")
redis_port = int(os.getenv("REDIS_PORT", 6379))

TTL_IDEMPOTENCY = timedelta(minutes=3)

# Tenta di inizializzare la connessione Redis
def initialize_redis_client():
    """
    Inizializza la variabile globale redis_client.
    """
    global redis_client
    if redis_client is not None:
        return redis_client

    try:
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        redis_client.ping() # Tenta la connessione
        print(f"[UserManagerApp] Connessione a Redis stabilita su {redis_host}:{redis_port}")
        return redis_client
    except Exception as e:
        print(f"[UserManagerApp] ERRORE: Impossibile connettersi a Redis. Dettagli: {e}")
        redis_client = None
        return None


def generate_content_hash(request_body: dict) -> str:
    """
    Genera un hash SHA256 deterministico del body della richiesta.
    """
    # Ordina le chiavi per garantire che l'hash sia lo stesso
    # anche se l'ordine degli attributi cambia nel JSON in arrivo.
    try:
        serialized = json.dumps(request_body, sort_keys=True).encode('utf-8')
        return hashlib.sha256(serialized).hexdigest()[:12] # Usiamo un hash corto
    except Exception as e:
        print(f"[Redis] Errore durante l'hashing del body: {e}")
        # In caso di errore, si ritorna un hash di fallback per evitare che la
        # logica di idempotenza venga bypassata in modo incontrollato.
        return "ERROR_HASH"


def check_idempotency(idempotency_key):
    """
    Verifica se la richiesta è già stata elaborata (Cache HIT)
    o se è in corso (409 Conflict), e tenta di acquisire il blocco "IN_PROGRESS".

    Ritorna:
    - (status, body) se l'operazione è completata o in conflitto.
    - (None, None) se il blocco è stato acquisito con successo.
    """
    if redis_client is None:
        return None, None

    # 1. Tenta di recuperare la risposta finale salvata
    cached_response = redis_client.get(idempotency_key)

    # Se la risposta esiste ed è diversa dal blocco temporaneo, è un HIT (operazione completata)
    if cached_response and cached_response != "IN_PROGRESS":
        cached_data = json.loads(cached_response)
        print(f" [UserManagerApp] : [Redis] Cache HIT per chiave {idempotency_key}. Ritorno risposta memorizzata.")
        return cached_data.get("status"), cached_data.get("body")

    # 2. Se la chiave non è presente la blocca
    if not redis_client.set(idempotency_key, "IN_PROGRESS", nx=True, ex=TTL_IDEMPOTENCY):
        # La chiave è presente ma in elaborazione. Restituisce error 409
        print(f"[UserManagerApp] : [Redis] Blocco fallito, chiave {idempotency_key} in elaborazione.")
        return 409, {"error": "Richiesta con la stessa Idempotency-Key in elaborazione."}

    # Blocco impostato con successo. Via libera.
    print(f"[UserManagerApp] : [Redis] Blocco acquisito per chiave {idempotency_key}. Via libera all'elaborazione.")
    return None, None


def save_idempotent_response(idempotency_key, status, body):
    """
    Salva lo stato e il corpo della risposta finale in Redis con un TTL,
    sovrascrivendo l'eventuale blocco "IN_PROGRESS".
    """
    if redis_client is None:
        return

    # Serializza la risposta (stato + body) in JSON
    response_data = json.dumps({"status": status, "body": body})

    # Sovrascrive il valore con la risposta finale
    redis_client.set(idempotency_key, response_data, ex=TTL_IDEMPOTENCY)