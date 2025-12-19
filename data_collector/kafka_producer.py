from confluent_kafka import Producer # type: ignore
import json
import os
from datetime import datetime

# Configurazione Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_TO_ALERT_SYSTEM = "to-alert-system" # Nome del topic specificato

producer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'acks': 'all',
    'retries': 3,
    "log_level": 3,
}

# Inizializzazione del Producer
try:
    producer = Producer(producer_config)
except Exception as e:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Errore durante l'inizializzazione del Kafka Producer: {e}")
    producer = None


def delivery_report(err, msg):
    """
    Callback asincrona per verificare l'invio del messaggio.
    """
    if err:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Fallimento nell'invio: {err}")
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Messaggio inviato a {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")


def send_update_completed_notification(airport_data: dict):
    """
    Invia un messaggio di notifica sul topic 'to-alert-system'.
    Il payload contiene un timestamp e un dizionario con i dati dell'aeroporto aggiornato, ad esempio:
    airport_data = {
        'airport_code' : 'LICC',
        'flight_count': 45,
        'updated_at': '2025-12-14T10:30:00'
    }
    """
    if producer is None:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Producer non inizializzato. Impossibile inviare il messaggio.")
        return

    try:
        kafka_message_payload = {
            'timestamp': datetime.now().isoformat(),
            'airport_data': airport_data,
        }

        message_key = f"data_collector_notification_for_{airport_data['airport_code']}".encode("utf-8")
        message_value = json.dumps(kafka_message_payload).encode('utf-8')

        producer.produce(
            TOPIC_TO_ALERT_SYSTEM,
            key=message_key,
            value=message_value,
            callback=delivery_report
        )

        producer.poll(0)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][Kafka_Producer] Notifica per {airport_data['airport_code']}, con {airport_data['flight_count']} voli inviata a '{TOPIC_TO_ALERT_SYSTEM}'.")

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][Kafka_Producer] Errore durante l'invio dell messaggio per {airport_data['airport_code']}: {e}")

def flush_producer():
    """Garantisce che tutti i messaggi in sospeso vengano inviati."""
    if producer is not None:
        remaining = producer.flush(timeout=10)
        if remaining > 0:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Attenzione: {remaining} messaggi non inviati prima dell'uscita.")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Tutti i messaggi in sospeso sono stati inviati.")