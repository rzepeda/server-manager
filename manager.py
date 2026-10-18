import os
import time
import docker
import yaml

client = docker.from_env()
APPS_DIR = "/server/apps"
SECRETS_DIR = "/server/secrets"
CADDY_SITES_DIR = "/server/caddy/sites"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))

def load_secrets(app_name):
    secret_file = os.path.join(SECRETS_DIR, f"{app_name}.env")
    env_vars = {}
    if os.path.exists(secret_file):
        with open(secret_file, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    env_vars[key] = val
    return env_vars

def update_caddy_config(app_name, subdomain, container_name, port):
    os.makedirs(CADDY_SITES_DIR, exist_ok=True)
    caddy_file = os.path.join(CADDY_SITES_DIR, f"{app_name}.caddy")
    
    domain_base = os.getenv("DOMAIN_BASE", "agentictools.uk")
    config_content = f"""{subdomain}.{domain_base} {{
    reverse_proxy {container_name}:{port}
}}
"""
    with open(caddy_file, "w") as f:
        f.write(config_content)
    print(f"Configuración de Caddy actualizada para {subdomain}.{domain_base}")

def check_and_deploy():
    if not os.path.exists(APPS_DIR):
        return

    for app_name in os.listdir(APPS_DIR):
        app_path = os.path.join(APPS_DIR, app_name)
        deploy_file = os.path.join(app_path, "deploy.yml")

        if not os.path.exists(deploy_file):
            continue

        try:
            with open(deploy_file, "r") as f:
                config = yaml.safe_load(f)

            image = config.get("image")
            container_name = config.get("container_name", f"srv-{app_name}")
            container_port = config.get("container_port", 8000)
            
            public_cfg = config.get("public", {})
            is_public = public_cfg.get("enabled", False)
            subdomain = public_cfg.get("subdomain", app_name)

            print(f"📦 Verificando aplicación: {app_name} (Imagen: {image})")

            pulled_image = client.images.pull(image)
            new_image_id = pulled_image.id

            existing_containers = client.containers.list(all=True, filters={"name": container_name})
            needs_update = True

            if existing_containers:
                container = existing_containers[0]
                if container.image.id == new_image_id:
                    needs_update = False

            if not needs_update:
                continue

            secrets = load_secrets(app_name)
            environment = {**secrets}
            
            if existing_containers:
                container = existing_containers[0]
                print(f"🔄 Reemplazando contenedor existente: {container_name}")
                container.stop()
                container.remove()

            print(f"🚀 Iniciando contenedor {container_name}...")
            new_container = client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                network="homeserver-public",
                environment=environment
            )

            if config.get("database", {}).get("postgres", False):
                try:
                    data_net = client.networks.get("homeserver-data")
                    data_net.connect(new_container)
                    print(f"🔗 {container_name} conectado a la red de datos.")
                except docker.errors.NotFound:
                    print("⚠️ Red 'homeserver-data' no encontrada.")

            if is_public:
                update_caddy_config(app_name, subdomain, container_name, container_port)

            print(f"✅ Aplicación {app_name} desplegada exitosamente.")

        except Exception as e:
            print(f"❌ Error procesando la aplicación {app_name}: {e}")

if __name__ == "__main__":
    print("🤖 Homeserver Deployment Manager iniciado y observando repositorios...")
    while True:
        try:
            check_and_deploy()
        except Exception as e:
            print(f"❌ Error en el ciclo principal: {e}")
        time.sleep(CHECK_INTERVAL)