from confluent_kafka import Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient
import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Configurazione Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
TOPIC_TO_NOTIFIER="to-notifier"

# Configurazione mailhog
SMTP_SERVER = os.getenv("SMTP_SERVER", "mailhog")
SMTP_PORT = os.getenv("SMTP_PORT", "1025")


consumer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'group2',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
    'max.poll.interval.ms': 300000,
    'session.timeout.ms': 60000,
    "log_level": 3,
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

    # PARTE 2: Attesa che il Topic Creator abbia completato la creazione
    print(f"Waiting for topic '{TOPIC_TO_NOTIFIER}' to be available (waiting for topic creator)...", flush=True)
    while True:
        try:
            metadata = admin.list_topics(topic=TOPIC_TO_NOTIFIER, timeout=5)

            if TOPIC_TO_NOTIFIER in metadata.topics:
                print(f"Topic '{TOPIC_TO_NOTIFIER}' is available.", flush=True)
                return
            else:
                print(f"Topic '{TOPIC_TO_NOTIFIER}' not yet available. Retrying in 5s...", flush=True)
                time.sleep(5)

        except Exception as e:
            print(f"Error checking topic status: {e}. Retrying in 5s...", flush=True)
            time.sleep(5)

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

def sending_email(notifications):
    """
    Invia le email
    """
    # Stampa
    if not notifications:
        print("Nessuna notifica da inviare.")
        return

    print(f"Trovate {len(notifications)} notifiche da inviare.")
    print_notifications(notifications)

    # Dati ricevuti da Kafka
    for i, notification in enumerate(notifications):
        ap_code = notification["airport_code"]
        user_email = notification["user_email"]
        condition = notification["condition"]

        msg = EmailMessage()
        msg.set_content(condition)
        msg['Subject'] = ap_code
        msg['To'] = user_email
        msg['From'] = 'alert-system@your-app.com'

        # Invio dell'email a MailHog
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.send_message(msg)
            print("Email inviata con successo a MailHog.")
        except Exception as e:
            print(f"Errore durante l'invio dell'email: {e}")


def main():
    wait_for_kafka_and_topic()
    consumer = Consumer(consumer_config)
    consumer.subscribe([TOPIC_TO_NOTIFIER])
    message_count = 0
    BATCH_SIZE = 1
    received_messages = []
    print(f"Alert Notifier System started")
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
                received_messages.append(data)
                message_count += 1

                print(f"Received message in to-notifier topic.\n"
                      f"Received message #{message_count} (batch progress: {message_count}/{BATCH_SIZE})")

                # 2. Logica di invio mail
                if message_count >= BATCH_SIZE:
                    # Chiamata funzione che invia ogni mail con un for.
                    sending_email(received_messages)

                    consumer.commit(asynchronous=False)
                    print(f"Committed offset: {msg.offset()}\n")

                    # Reset for next batch
                    received_messages = []
                    message_count = 0

            except Exception as e:
                print(f"Errore durante l'elaborazione: {e}")
                consumer.commit(asynchronous=False)
                continue

    except KeyboardInterrupt:
        print("\nConsumer-Producer interrupted by user.")
    finally:
        # Final cleanup
        # Processa i messaggi rimanenti in buffer
        if received_messages:
            print("\nProcessing remaining messages before shutdown...")
            # Chiamata alla funzione che invia mail con for
            sending_email(received_messages)
            consumer.commit(asynchronous=False)

        print("Closing consumer...")
        consumer.close()
        print("Shutdown complete")

if __name__ == "__main__":
    main()