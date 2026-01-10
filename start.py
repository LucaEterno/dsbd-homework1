import subprocess
import sys
import os
import time

CLUSTER_NAME = "myapp"
BASE_PATH = "."
K8S_PATH = f"{BASE_PATH}/kubernetes"
KIND_CONFIG = f"{BASE_PATH}/kind/config.yaml"

# 1. Lista immagini (Tag, Percorso)
# I nomi dei tag devono corrispondere a quelli usati nei file .yaml (image: nome:latest)
IMAGES = [
    ("user-manager", f"{BASE_PATH}/user_manager"),
    ("data-collector", f"{BASE_PATH}/data_collector"),
    ("alert-system", f"{BASE_PATH}/alert_system"),
    ("alert-notifier", f"{BASE_PATH}/alert_notifier_system")
]

# 2. Lista manifest ordinata per dipendenze
MANIFESTS = [
    f"{K8S_PATH}/ingress-controller.yaml",
    f"{K8S_PATH}/tls-secrets.yaml",
    f"{K8S_PATH}/user_db_secrets.yaml",
    f"{K8S_PATH}/data_db_secrets.yaml",
    f"{K8S_PATH}/opensky_credentials.yaml",
    f"{K8S_PATH}/user_db_init.yaml",
    f"{K8S_PATH}/data_db_init.yaml",
    f"{K8S_PATH}/kafka_init.yaml",
    f"{K8S_PATH}/prometheus_init.yaml",
    f"{K8S_PATH}/user_db_pvc.yaml",
    f"{K8S_PATH}/data_db_pvc.yaml",
    f"{K8S_PATH}/kafka-pvc.yaml",
    f"{K8S_PATH}/prometheus_pvc.yaml",
    f"{K8S_PATH}/user_db.yaml",
    f"{K8S_PATH}/data_db.yaml",
    f"{K8S_PATH}/redis.yaml",
    f"{K8S_PATH}/kafka.yaml",
    f"{K8S_PATH}/mailhog.yaml",
    f"{K8S_PATH}/user_manager.yaml",
    f"{K8S_PATH}/data_collector.yaml",
    f"{K8S_PATH}/alert_system.yaml",
    f"{K8S_PATH}/alert_notifier_system.yaml",
    f"{K8S_PATH}/prometheus.yaml",
    f"{K8S_PATH}/ingress.yaml"
]

def run_cmd(command, ignore_error=False):
    print(f"\n> Esecuzione: {command}")
    try:
        subprocess.run(command, shell=True, check=not ignore_error)
        return True
    except subprocess.CalledProcessError:
        if not ignore_error:
            print(f"\n Errore critico durante: {command}")
            sys.exit(1)
        return False

def wait_for_ingress_ready():
    print("\n Attesa che l'Ingress Controller sia pronto...")
    wait_cmd = (
        "kubectl wait --namespace ingress-nginx "
        "--for=condition=ready pod "
        "--selector=app.kubernetes.io/component=controller "
        "--timeout=120s"
    )
    try:
        subprocess.run(wait_cmd, shell=True, check=True)
        time.sleep(5)
        print(" Ingress Controller pronto!")
    except subprocess.CalledProcessError:
        print(" L'Ingress Controller non è partito. Verifica con 'kubectl get pods -n ingress-nginx'")
        sys.exit(1)

def main():
    # 1. Creazione Cluster KIND
    print(f"Verifica cluster KIND '{CLUSTER_NAME}'...")
    result = subprocess.run("kind get clusters", shell=True, capture_output=True, text=True)

    if CLUSTER_NAME in result.stdout:
        print(f"Il cluster '{CLUSTER_NAME}' esiste già.")
    else:
        print(f"Creazione cluster '{CLUSTER_NAME}'...")
        run_cmd(f"kind create cluster --config {KIND_CONFIG} --name {CLUSTER_NAME}")

    # 2. Build delle immagini (Docker)
    print("\n Build delle immagini Docker...")
    for tag, path in IMAGES:
        if os.path.exists(path):
            run_cmd(f"docker build -t {tag}:latest {path}")
        else:
            print(f" Cartella non trovata per la build: {path}")

    # 3. Caricamento immagini in KIND
    print("\n Caricamento immagini nel cluster KIND...")
    for tag, _ in IMAGES:
        run_cmd(f"kind load docker-image {tag}:latest --name {CLUSTER_NAME}")

    # 4. Applicazione dei Manifests
    print("\n Applicazione dei manifest Kubernetes...")
    for path in MANIFESTS:
        if "ingress.yaml" in path:
            wait_for_ingress_ready()

        if os.path.exists(path):
            run_cmd(f"kubectl apply -f {path}")
        else:
            print(f" File saltato (non trovato): {path}")

    print("\n Progetto distribuito con successo su Kubernetes!")
    print("Accedi a Prometheus su http://localhost:9090")
    print("Accedi a Mailhog su http://localhost:8025")

if __name__ == "__main__":
    main()

