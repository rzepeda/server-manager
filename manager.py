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
    """Carga los secretos desde un archivo .env ubicado en disco separado."""
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
    """Genera o actualiza el archivo de configuración para Caddy."""
    os.makedirs(CADDY_SITES_DIR, exist_ok=True)
    caddy_file = os.path.join(CADDY_SITES_DIR, f"{app_name}.caddy")
    
    domain_base = os.getenv("DOMAIN_BASE", "tudominio.cl")
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

            # 1. Hacer pull de la imagen más reciente desde GHCR
            print(f"⬇️ Descargando última versión de {image}...")
            client.images.pull(image)

            # 2. Cargar secretos desde disco
            secrets = load_secrets(app_name)

            # 3. Preparar variables de entorno para el contenedor
            environment = {**secrets}

            # 4. Verificar si el contenedor ya existe y recrearlo si hay cambios
            existing_containers = client.containers.list(all=True, filters={"name": container_name})
            
            if existing_containers:
                container = existing_containers[0]
                print(f"🔄 Reemplazando contenedor existente: {container_name}")
                container.stop()
                container.remove()
            # 5. Levantar el nuevo contenedor conectado a las redes del homeserver

            print(f"🚀 Iniciando contenedor {container_name}...")
            # 1. Creamos el contenedor con una sola red principal (network en singular)
            new_container = client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                network="homeserver-public",
                environment=environment
            )
            # 2. Conectamos la red de base de datos secundaria si la app lo requiere
            if config.get("database", {}).get("postgres", False):
                try:
                    data_net = client.networks.get("homeserver-data")
                    data_net.connect(new_container)
                    print(f"🔗 {container_name} conectado a la red de datos.")
                except docker.errors.NotFound:
                    print("⚠️ Red 'homeserver-data' no encontrada.")
            # 6. Configurar Caddy si es público
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






            print(f"🚀 Iniciando contenedor {container_name}...")
            # 1. Creamos el contenedor con una sola red principal (network en singular)
            new_container = client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                network="homeserver-public",
                environment=environment
            )
            # 2. Conectamos la red de base de datos secundaria si la app lo requiere
            if config.get("database", {}).get("postgres", False):
                try:
                    data_net = client.networks.get("homeserver-data")
                    data_net.connect(new_container)
                    print(f"🔗 {container_name} conectado a la red de datos.")
                except docker.errors.NotFound:
                    print("⚠️ Red 'homeserver-data' no encontrada.")
