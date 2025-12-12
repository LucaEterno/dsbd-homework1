from confluent_kafka import Producer
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

def send_update_completed_notification():
    """
    Invia un messaggio di notifica sul topic 'to-alert-system'.
    Il payload contiene solo il timestamp dell'aggiornamento completato.
    """
    if producer is None:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Producer non inizializzato. Impossibile inviare il messaggio.")
        return

    try:
        kafka_message_payload = {
            'timestamp': datetime.now().isoformat(),
            'status': 'update_completed',
        }

        message_key = "data_update_trigger"
        message_value = json.dumps(kafka_message_payload).encode('utf-8')

        producer.produce(
            TOPIC_TO_ALERT_SYSTEM,
            key=message_key,
            value=message_value,
            callback=delivery_report
        )

        producer.poll(0)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][Kafka_Producer] Notifica di completamento inviata a '{TOPIC_TO_ALERT_SYSTEM}'.")

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][Kafka_Producer] Errore durante l'invio del messaggio: {e}")

def flush_producer():
    """Garantisce che tutti i messaggi in sospeso vengano inviati."""
    if producer is not None:
        remaining = producer.flush(timeout=10)
        if remaining > 0:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Attenzione: {remaining} messaggi non inviati prima dell'uscita.")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Kafka_Producer] Tutti i messaggi in sospeso sono stati inviati.")