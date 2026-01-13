import subprocess
import sys
import os
import time

CLUSTER_NAME = "myapp"
BASE_PATH = "."
K8S_PATH = f"{BASE_PATH}/kubernetes"
KIND_CONFIG = f"{BASE_PATH}/kind/config.yaml"

IMAGES = [
    ("user-manager", f"{BASE_PATH}/user_manager"),
    ("data-collector", f"{BASE_PATH}/data_collector"),
    ("alert-system", f"{BASE_PATH}/alert_system"),
    ("alert-notifier", f"{BASE_PATH}/alert_notifier_system")
]

# --- MANIFEST DIVISI PER FASI ---

# FASE 1: Ingress Controller (Deve essere pronto per primo)
INGRESS_SETUP = [
    f"{K8S_PATH}/ingress-controller.yaml"
]

# FASE 2: Infrastruttura (Secret, DB, Code, Cache)
INFRASTRUCTURE = [
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
]

# FASE 3: Microservizi e Monitoraggio (Dipendono dai DB/Kafka)
APP_AND_INGRESS_RULES = [
    f"{K8S_PATH}/user_manager.yaml",
    f"{K8S_PATH}/data_collector.yaml",
    f"{K8S_PATH}/alert_system.yaml",
    f"{K8S_PATH}/alert_notifier_system.yaml",
    f"{K8S_PATH}/prometheus.yaml",
    f"{K8S_PATH}/ingress.yaml"  # Le regole di routing
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
    print("\n[ATTESA] Controllo Ingress Controller (NGINX)...")
    # Aumentiamo leggermente il timeout a 300s dato lo stress del PC
    wait_cmd = (
        "kubectl wait --namespace ingress-nginx "
        "--for=condition=ready pod "
        "--selector=app.kubernetes.io/component=controller "
        "--timeout=300s"
    )
    try:
        subprocess.run(wait_cmd, shell=True, check=True)
        print("--- Ingress Controller PRONTO! ---")
        time.sleep(2) # Pausa di respiro per il sistema
    except subprocess.CalledProcessError:
        print("\n[ERRORE] L'Ingress Controller non è partito in tempo. \nVerifica stato: kubectl get pods")
        sys.exit(1)

def apply_manifests(manifest_list):
    for path in manifest_list:
        if os.path.exists(path):
            run_cmd(f"kubectl apply -f {path}")
        else:
            print(f"(!) File saltato: {path}")

def wait_for_deployments_ready(timeout="480s"):
    print("\nAttendo che tutti i Deployment siano Ready...")
    cmd = (
        f"kubectl wait "
        f"--for=condition=available "
        f"--all deployments "
        f"--timeout={timeout}"
    )
    try:
        subprocess.run(cmd, shell=True, check=True)
        print("--- Tutti i Deployment sono READY ---")
    except subprocess.CalledProcessError:
        print("\n[ERRORE] Timeout: alcuni Deployment non sono pronti. \nVerifica stato: kubectl get pods")
        sys.exit(1)

def wait_for_kafka_job_completed(timeout="300s"):
    print("\nAttendo completamento Job kafka-setup-topics...")
    cmd = (
        f"kubectl wait "
        f"--for=condition=complete "
        f"job/kafka-setup-topics "
        f"--timeout={timeout}"
    )
    try:
        subprocess.run(cmd, shell=True, check=True)
        print("--- Job kafka-setup-topics COMPLETATO ---")
    except subprocess.CalledProcessError:
        print("\n[ERRORE] Il Job kafka-setup-topics non è terminato. \nVerifica stato: kubectl get pods")
        sys.exit(1)

def print_pods_status():
    print("\n STAMPA STATO POD KUBERNETES")

    cmd = "kubectl get pods"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except subprocess.CalledProcessError:
        print("[ERRORE] Impossibile ottenere lo stato dei pod. \nVerifica stato: kubectl get pods")

def main():
    # 1. Cluster KIND
    print(f"--- 1. Creazione Cluster KIND --- Tempo: {time.strftime('%H:%M:%S', time.gmtime(time.time()))}")
    result = subprocess.run("kind get clusters", shell=True, capture_output=True, text=True)
    if CLUSTER_NAME not in result.stdout:
        run_cmd(f"kind create cluster --config {KIND_CONFIG} --name {CLUSTER_NAME}")

    # 2. Build & Load Immagini
    print("--- 2. Build & Load Immagini ---")
    for tag, path in IMAGES:
        if os.path.exists(path):
            run_cmd(f"docker build -t {tag}:latest {path}")
            run_cmd(f"kind load docker-image {tag}:latest --name {CLUSTER_NAME}")

    # 3. FASE 1: Ingress Controller
    print("\n--- 3. Applicazione Manifest ---")
    print("\n--- 3.1 Setup Ingress ---")
    apply_manifests(INGRESS_SETUP)
    wait_for_ingress_ready()

    # 4. FASE 2: Infrastruttura (DB/Kafka)
    print("\n--- 3.2 Avvio Infrastruttura ---")
    apply_manifests(INFRASTRUCTURE)

    # 5. FASE 3: Applicazione
    print("\n--- 3.3 Avvio Microservizi ---")
    apply_manifests(APP_AND_INGRESS_RULES)

    print("\nCluster configurato con successo!")

    # 6. ATTESA COMPLETA SISTEMA
    print("\n--- 4. Attesa Sistema Pronto ---")
    wait_for_deployments_ready()
    wait_for_kafka_job_completed()

    print("\n" + "="*60)
    print(f"SISTEMA PRONTO! Tempo: {time.strftime('%H:%M:%S', time.gmtime(time.time()))}")
    print("="*60)

    print_pods_status()

    print("\nAccedi a:")
    print("  - Prometheus: http://localhost:9090")
    print("  - MailHog:    http://localhost:8025")
    print("\nVerifica stato: kubectl get pods")

if __name__ == "__main__":
    main()
