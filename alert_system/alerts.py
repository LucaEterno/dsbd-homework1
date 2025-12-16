from confluent_kafka import Consumer, Producer, KafkaException, KafkaError # type: ignore
from confluent_kafka.admin import AdminClient # type: ignore
import os
import json
from notification_logic import verification_logic
import time
from typing import List, Dict, Any
from datetime import datetime

# Configurazione Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_TO_ALERT_SYSTEM="to-alert-system"
TOPIC_TO_NOTIFIER="to-notifier"

consumer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'group1',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
    'max.poll.interval.ms': 300000,
    'session.timeout.ms': 60000,
    "log_level": 3,
}

producer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'retries': 5,
    'linger.ms': 0,
}


def wait_for_kafka_and_topic():
    admin_conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    }

    admin = AdminClient(admin_conf)

    # PARTE 1: Attesa che il broker sia online
    print("Waiting for Kafka Broker to be ready...", flush=True)
    while True:
        try:
            admin.list_topics(timeout=5)
            print("Kafka Broker is ready.", flush=True)
            break
        except Exception:
            print("Kafka Broker not ready, retrying in 5s...", flush=True)
            time.sleep(5)

    # PARTE 2: Attesa che il topic sia pronto
    print(f"Waiting for topic '{TOPIC_TO_ALERT_SYSTEM}' to be available (waiting for topic creator)...", flush=True)
    while True:
        try:
            metadata = admin.list_topics(topic=TOPIC_TO_ALERT_SYSTEM, timeout=5)

            if TOPIC_TO_ALERT_SYSTEM in metadata.topics:
                print(f"Topic '{TOPIC_TO_ALERT_SYSTEM}' is available.", flush=True)
                return
            else:
                print(f"Topic '{TOPIC_TO_ALERT_SYSTEM}' not yet available. Retrying in 5s...", flush=True)
                time.sleep(5)

        except Exception as e:
            print(f"Error checking topic status: {e}. Retrying in 5s...", flush=True)
            time.sleep(5)

def delivery_report(err, msg):
    if err:
        print(f"Failed to produce to {TOPIC_TO_NOTIFIER}: {err}")
    else:
        print(f"Info sent to {TOPIC_TO_NOTIFIER} at offset {msg.offset()}")

def format_notification(notification: Dict[str, Any]) -> str:
    """
    Formatta una singola notifica in una stringa leggibile.
    """
    ap_code = notification["airport_code"]
    user_email = notification["user_email"]
    condition = notification["condition"]
    current_count = notification["current_count"]
    threshold_max = notification["threshold_max"]
    threshold_min = notification["threshold_min"]

    # Formatta le soglie per la visualizzazione
    max_str = f"MAX: {threshold_max}" if threshold_max is not None else "N/A"
    min_str = f"MIN: {threshold_min}" if threshold_min is not None else "N/A"

    return (
        f"************************\n"
        f"  Utente: {user_email}\n"
        f"  Aeroporto: {ap_code}\n"
        f"  Condizione: {condition}\n"
        f"  Voli Attuali: {current_count}\n"
        f"  Soglie Monitorate: ({min_str} | {max_str})\n"
        f"  Timestamp: {notification['timestamp']}\n"
        f"************************"
    )

def print_notifications(notifications: List[Dict[str, Any]]):
    """
    Stampa la lista di risultati di notifica in un formato leggibile.
    """
    if not notifications:
        print(f"\n[{datetime.now().isoformat()}] Nessuna notifica da inviare. Le soglie non sono state superate.")
        return

    print(f"\n[{datetime.now().isoformat()}] Rilevate {len(notifications)} condizioni di allerta da notificare:\n")

    for i, notification in enumerate(notifications):
        print("="*40)
        print(f"NOTIFICA {i+1} DI {len(notifications)}")
        print(format_notification(notification))

    print("="*40)

def notification_producer(producer, results_to_notify):
    """
    Invia l'elenco dei risultati di notifica al topic TOPIC_TO_NOTIFIER.
    """
    if not results_to_notify:
        print("Nessuna notifica da inviare.")
        return

    print(f"Trovate {len(results_to_notify)} notifiche da inviare.")
    print_notifications(results_to_notify)

    for result in results_to_notify:
        try:
            producer.produce(
                TOPIC_TO_NOTIFIER,
                key=result.get("user_email", "default_key").encode('utf-8'),
                value=json.dumps(result).encode('utf-8'),
                callback=delivery_report
            )
            producer.poll(0)
        except Exception as e:
            print(f"Errore durante la produzione del messaggio: {e}")

def main():
    wait_for_kafka_and_topic()
    consumer = Consumer(consumer_config)
    producer = Producer(producer_config)
    consumer.subscribe([TOPIC_TO_ALERT_SYSTEM])
    print(f"Alert System started")
    try:
        while True:
            msg = consumer.poll(5.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    print(f"End of partition {msg.partition()}")
                else:
                    print(f"Consumer error: {msg.error()}")
                continue

            try:
                #1. Messaggio ricevuto
                data = json.loads(msg.value().decode('utf-8'))
                ts = data['timestamp']
                status = data['status']
                airports_data = data.get('airports_data', {})

                print(f"Received message in to-alert-system topic. Timestamp = {ts}, Status = {status}, Airports={len(airports_data)}\n"
                      f"Start verifying..")

                # 2. Logica di verifica
                results_to_notify = verification_logic(airports_data)

                #3. Invio delle notifiche
                notification_producer(producer, results_to_notify)

                # 4. Commit Manuale
                consumer.commit(message=msg, asynchronous=False)
                print(f"Committed offset {msg.offset()}")

            except json.JSONDecodeError as e:
                print(f"Errore JSON decode: {e}. Messaggio skippato.")
                # Non committiamo, il messaggio verrà riletto

            except Exception as e:
                print(f"Errore durante l'elaborazione: {e}")
                # In questo caso committiamo (avremo una dead letter in produzione)
                consumer.commit(message=msg, asynchronous=False)
                

    except KeyboardInterrupt:
        print("\nConsumer-Producer interrupted by user.")
    finally:
        # Final cleanup
        print("Flushing producer...")
        producer.flush(timeout=10)
        print("Closing consumer...")
        consumer.close()
        print("Shutdown complete")

if __name__ == "__main__":
    main()
