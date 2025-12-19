from confluent_kafka import Consumer, KafkaException, KafkaError # type: ignore
from confluent_kafka.admin import AdminClient # type: ignore
import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Configurazione Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_TO_NOTIFIER="to-notifier"

# Configurazione mailhog
SMTP_SERVER = os.getenv("SMTP_SERVER", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))


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

def sending_email(notification: Dict[str, Any]):
    """
    Invia la email
    """
    if not notification:
        print("Nessuna email da inviare.")
        return

    # Estrazione dati
    ap_code = notification["airport_code"]
    user_email = notification["user_email"]
    condition = notification["condition"]

    # Riempimento campi email
    msg = EmailMessage()
    msg.set_content(condition)
    msg['Subject'] = ap_code
    msg['To'] = user_email
    msg['From'] = 'alert-system@your-app.com'

    # Invio dell'email a MailHog
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.send_message(msg)
        print(f"Email inviata con successo a {user_email} (Aeroporto: {ap_code})..")
        return True
    except Exception as e:
        print(f"Errore durante l'invio dell'email: {e}")
        return False



def main():
    wait_for_kafka_and_topic()
    consumer = Consumer(consumer_config)
    consumer.subscribe([TOPIC_TO_NOTIFIER])
    print(f"Alert Notifier System started")

    try:
        while True:
            # Poll con timeout per reattività
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    print(f"End of partition {msg.partition()}")
                else:
                    # Errore grave nel consumer, ma prosegui
                    print(f"Consumer error: {msg.error()}")
                continue

            try:
                # 1. Messaggio ricevuto e deserializzato
                data = json.loads(msg.value().decode('utf-8'))

                # 2. Invio mail
                ok = sending_email(data)

                # 3. Commit Manuale SOLO dopo l'invio riuscito
                if ok:
                    consumer.commit(message=msg, asynchronous=False)
                    print(f"Committed offset {msg.offset()}")
                else:
                    print("Email failed -> not committing")

            except json.JSONDecodeError as e:
                print(f"Errore JSON decode: {e}. Messaggio skippato. Committing.")
                consumer.commit(message=msg, asynchronous=False)

            except Exception as e:
                print(f"Errore durante l'invio dell'email per {data.get('user_email', 'unknown')}: {e}")
                consumer.commit(message=msg, asynchronous=False)


    except KeyboardInterrupt:
        print("\nConsumer interrupted by user.")
    finally:
        print("Closing consumer...")
        consumer.close()
        print("Shutdown complete")

if __name__ == "__main__":
    main()