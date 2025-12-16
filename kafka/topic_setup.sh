#!/bin/bash
set -e

echo "Waiting for Kafka to be ready..."
until /usr/bin/kafka-broker-api-versions --bootstrap-server kafka:9092 >/dev/null 2>&1; do
  echo "Kafka not ready yet... retrying in 2s"
  sleep 2
done

echo "Kafka is ready. Creating topics..."
TOPIC_ALERT="to-alert-system"
TOPIC_NOTIFIER="to-notifier"
PARTITIONS=1
REPLICAS=1

/usr/bin/kafka-topics --create --topic $TOPIC_ALERT --if-not-exists --bootstrap-server kafka:9092 --partitions $PARTITIONS --replication-factor $REPLICAS
if [ $? -eq 0 ]; then
    echo "Topic $TOPIC_ALERT created or already exists."
fi

/usr/bin/kafka-topics --create --topic $TOPIC_NOTIFIER --if-not-exists --bootstrap-server kafka:9092 --partitions $PARTITIONS --replication-factor $REPLICAS
if [ $? -eq 0 ]; then
    echo "Topic $TOPIC_NOTIFIER created or already exists."
fi

echo "Topic setup completed."