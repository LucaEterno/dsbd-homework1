#!/bin/bash

# --- Avvio dei servizi in background ---

echo "Avvio User Manager (Flask Development Server) sulla porta $LISTEN_PORT..."
# Avvia il server Flask e lo manda in background (&)
python -u app.py &

echo "Avvio Data Collector gRPC channel..."
# Avvia il server gRPC e lo manda in background (&)
python -u server.py &

# --- Mantenimento del container attivo ---

# 'wait -n' fa in modo che il container rimanga attivo finché
# tutti i processi in background non sono terminati.
# Se uno dei due fallisce, il container si ferma.
wait -n

echo "Un servizio è terminato. Uscita del container."

# Codice di uscita
exit $?